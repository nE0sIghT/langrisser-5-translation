#!/usr/bin/env python3
"""Maintain EN glyph slot assignments (singles, punctuation, letter pairs).

Collects every single char and lowercase pair needed by the current EN
texts (script dump translations + menu map values), keeps all existing
assignments stable, and assigns new needs to the cheapest sacrificial
kanji slots: confirmed kanji, unused in chunk 0, unused in menu/UI string
runs, rarest in the script (those lines will be translated eventually).
"""
import argparse
import collections
import csv
import json
import re
import struct
from pathlib import Path

from lang5_scen import consumes_argument, find_text_block, read_chunk_spans, words_from_bytes

TAG_RE = re.compile(r"<\$[0-9A-Fa-f]{4}>")
WORD_RE = re.compile(r"[A-Za-z'.,0-9]+")
SINGLES = "abcdefghijklmnopqrstuvwxyz'.,"
PAIR_TAIL = set("abcdefghijklmnopqrstuvwxyz'.,0123456789")


def word_pairs(w: str):
    """Greedy pairing exactly as Codec.encode will see it: a capital is
    allowed only as the first char of a word-initial pair; all-caps words
    stay native full-width singles."""
    i = 0
    while i + 1 < len(w):
        a, b = w[i], w[i + 1]
        ok = b in PAIR_TAIL and (a in PAIR_TAIL or (a.isupper() and i == 0))
        if ok:
            yield w[i : i + 2]
            i += 2
        else:
            i += 1


def needed_units(en_dump_dir: Path, menu_map: Path):
    """Return (singles, menu_pairs, script_pairs).

    Menu labels must fit fixed slot counts, so they get the full pairing
    rules (capital-initial, digits, punctuation) and absolute priority.
    Script dialogs have room: lowercase pairs only, prioritized by
    frequency, assigned while the sacrificial pool lasts.
    """
    script_texts: list[str] = []
    for fp in sorted(en_dump_dir.glob("*/chunk_*.txt")):
        for raw in fp.read_text(encoding="utf-8").splitlines():
            if "\t" in raw and not raw.startswith("#"):
                script_texts.append(TAG_RE.sub("", raw.split("\t", 1)[1]))
    menu_texts: list[str] = []
    if menu_map.exists():
        menu_texts = list(json.loads(menu_map.read_text(encoding="utf-8")).values())

    singles: set[str] = set()
    menu_pairs: collections.Counter = collections.Counter()
    script_pairs: collections.Counter = collections.Counter()
    for t in script_texts + menu_texts:
        for ch in t:
            if ch in SINGLES:
                singles.add(ch)
    for t in menu_texts:
        for m in WORD_RE.finditer(t):
            for p in word_pairs(m.group(0)):
                menu_pairs[p] += 1
    for t in script_texts:
        for m in WORD_RE.finditer(t):
            for p in word_pairs(m.group(0)):
                script_pairs[p] += 1
    return singles, menu_pairs, script_pairs


def decode_run_key(words: list[int], tok2char: dict[int, str]) -> str:
    out = []
    for w in words:
        if w in tok2char:
            out.append(tok2char[w])
        elif w >= 0xFF00:
            out.append("{%04X}" % w)
        else:
            out.append("[%04X]" % w)
    return "".join(out)


def sacrificial_pool(groups_report: Path, scen: Path, scen2: Path,
                     other_files: list[Path], translated_keys: set[str]) -> list[int]:
    tok2char: dict[int, str] = {}
    rows = list(csv.DictReader(open(groups_report, encoding="utf-8")))
    for r in rows:
        if r["index_dec"].isdigit() and r["char"]:
            tok2char[int(r["index_dec"])] = r["char"]

    usage: collections.Counter = collections.Counter()
    chunk0: set[int] = set()
    for f in (scen, scen2):
        data = f.read_bytes()
        for ci, (s, e) in enumerate(read_chunk_spans(data)):
            chunk = data[s:e]
            block = find_text_block(chunk)
            for ri in range(1, block.record_count + 1):
                a, b = block.record_span(ri)
                prev = None
                for w in words_from_bytes(chunk[a:b]):
                    if w < 0xE000 and not (prev is not None and consumes_argument(prev)):
                        usage[w] += 1
                        if ci == 0:
                            chunk0.add(w)
                    prev = w

    ui_used: collections.Counter = collections.Counter()
    for f in other_files:
        data = f.read_bytes()
        if f.name == "SYSTEM.BIN":
            data = data[0x8100:]  # skip font plane and offset tables
        ws = list(struct.unpack(f"<{len(data)//2}H", data[: len(data) & ~1]))
        run: list[int] = []
        for w in ws:
            if w == 0xFFFF:
                pr = [x for x in run if x < 0xE000]
                if len(pr) >= 3 and sum(1 for x in pr if x in tok2char) / len(pr) >= 0.8:
                    # Runs we already translate stop displaying their JP
                    # glyphs once patched, so they do not block slots.
                    if decode_run_key(run + [0xFFFF], tok2char) not in translated_keys:
                        ui_used.update(pr)
                run = []
            elif w < 0xE000 or 0xF000 <= w < 0xFFFF:
                run.append(w)
            else:
                run = []

    tier1: list[tuple[int, int]] = []
    tier2: list[tuple[int, int]] = []  # used in untranslated UI text: a
    # sacrifice costs one wrong glyph there until that text is translated
    for r in rows:
        if not r["index_dec"].isdigit() or r["group"] != "confirmed":
            continue
        idx = int(r["index_dec"])
        ch = r["char"]
        if len(ch) != 1 or not (0x4E00 <= ord(ch) <= 0x9FFF):
            continue
        if idx in chunk0 or idx > 1820:
            continue
        if idx in ui_used:
            tier2.append((ui_used[idx] + usage.get(idx, 0), idx))
        else:
            tier1.append((usage.get(idx, 0), idx))
    tier1.sort()
    tier2.sort()
    return [idx for _, idx in tier1] + [idx for _, idx in tier2]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--groups-report", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--assignments", default="data/font_mapping/en_slot_assignments.csv")
    ap.add_argument("--en-dump", default="data/translation/en")
    ap.add_argument("--menu-map", default="data/translation/system_menu_map.json")
    ap.add_argument("--scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--scen2", default="work/extracted/SCEN2.DAT")
    args = ap.parse_args()

    existing: dict[str, int] = {}
    rows = []
    apath = Path(args.assignments)
    if apath.exists():
        rows = list(csv.DictReader(open(apath, encoding="utf-8")))
        for r in rows:
            existing[r["en_char"]] = int(r["index_dec"])

    singles, menu_pairs, script_pairs = needed_units(Path(args.en_dump), Path(args.menu_map))
    must = [c for c in sorted(singles) if c not in existing]
    must += [p for p, _ in menu_pairs.most_common() if p not in existing]
    optional = [p for p, _ in script_pairs.most_common()
                if p not in existing and p not in must]

    taken = set(existing.values())
    # BTLDAT/MRCUSW/SLPS are mostly code/data whose pseudo-runs would
    # inflate the "used in UI" set; real UI strings live in SYSTEM/ALLUS*.
    translated_keys = set()
    if Path(args.menu_map).exists():
        translated_keys = set(json.loads(Path(args.menu_map).read_text(encoding="utf-8")))
    pool = [i for i in sacrificial_pool(
        Path(args.groups_report), Path(args.scen), Path(args.scen2),
        [Path(p) for p in ("work/extracted/SYSTEM.BIN", "work/extracted/ALLUSB.BIN",
                           "work/extracted/ALLUSW.BIN")],
        translated_keys,
    ) if i not in taken]
    if len(pool) < len(must):
        raise SystemExit(f"not enough sacrificial slots: need {len(must)}, have {len(pool)}")
    dropped = max(0, len(must) + len(optional) - len(pool))
    need = (must + optional)[: len(pool)]
    if dropped:
        print(f"pool limit: {dropped} least-frequent dialog pairs fall back to single letters")
    if not need:
        print("assignments up to date")
        return

    src = {int(r["index_dec"]): r["replaced_char"] for r in rows} if rows else {}
    gmap = {}
    for r in csv.DictReader(open(args.groups_report, encoding="utf-8")):
        if r["index_dec"].isdigit():
            gmap[int(r["index_dec"])] = r["char"]

    for unit in need:
        slot = pool.pop(0)
        rows.append({"index_dec": str(slot), "en_char": unit,
                     "replaced_char": gmap.get(slot, "")})

    with apath.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["index_dec", "en_char", "replaced_char"])
        w.writeheader()
        w.writerows(rows)
    print(f"added {len(need)} assignments (total {len(rows)})")


if __name__ == "__main__":
    main()
