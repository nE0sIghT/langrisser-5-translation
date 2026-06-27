#!/usr/bin/env python3
"""Maintain target-language glyph slot assignments.

Collects every single char and lowercase pair needed by the current target
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

from lang5_project import COMMON_FONT_MAP, add_language_args, language_from_args
from lang5_scen import consumes_argument, find_text_block, read_chunk_spans, words_from_bytes

TAG_RE = re.compile(r"<\$[0-9A-Fa-f]{4}>")
WORD_RE = re.compile(r"[\w'.,]+", re.UNICODE)
SPACE_LETTER_RE = re.compile(r" ([^\W_])", re.UNICODE)
LETTER_SPACE_RE = re.compile(r"([^\W_]) (?=[^\W_])", re.UNICODE)
PUNCT_SPACE_RE = re.compile(r"([,\.…？！:]) ")
LETTER_COLON_RE = re.compile(r"([^\W_]):", re.UNICODE)
SINGLE_PUNCTUATION = "'.,…"
PAIR_PUNCTUATION = "'.,"
PUNCT_PAIRS = ("！？", "？！")


def is_pair_tail(ch: str) -> bool:
    return ch.islower() or ch.isdigit() or ch in PAIR_PUNCTUATION


def word_pairs(w: str):
    """Every usable adjacent pair in a word.

    Codec.encode chooses the globally cheapest tiling. Supplying only one
    greedy tiling prevents it from shifting pair boundaries to avoid an
    interior single glyph or to combine the preceding space with the first
    letter. A capital is still allowed only at the start of a word; all-caps
    words stay native full-width singles.
    """
    for i in range(len(w) - 1):
        a, b = w[i], w[i + 1]
        ok = is_pair_tail(b) and (
            is_pair_tail(a) or (a.isupper() and i == 0)
        )
        if ok:
            yield w[i : i + 2]


def map_target_texts(mp: Path) -> list[str]:
    """Target strings from a translation map or unified string list."""
    data = json.loads(mp.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return list(data.values())
    return [e["text"] for e in data
            if (e.get("text") or "").strip() and e["text"] != "{BLANK}"]


def map_jp_keys(mp: Path, source_by_id: dict[str, dict]) -> set[str]:
    """JP source strings from a translation map (used to mark UI glyph slots)."""
    data = json.loads(mp.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        overlay_ids = {
            key for key in data
            if key.startswith("table:") or key.startswith("offset:")
        }
        unknown = overlay_ids - set(source_by_id)
        if unknown:
            raise SystemExit(
                f"{mp}: SYSTEM overlay ids require a current source dump; "
                f"unknown ids: {sorted(unknown)[:5]}"
            )
        if data and set(data).issubset(source_by_id):
            return {
                source_by_id[entry_id]["jp"]
                for entry_id, text in data.items()
                if text and source_by_id[entry_id].get("jp")
            }
        return set(data)
    return {e["jp"] for e in data if e.get("jp")}


def needed_units(translation_root: Path, menu_maps: list[Path],
                 extra_singles: str = ""):
    """Return (singles, menu_pairs, spacing_pairs, script_pairs).

    Menu labels must fit fixed slot counts, so they get the full pairing
    rules (capital-initial, digits, punctuation) and absolute priority.
    Spacing pairs are optional encodings that improve readability and save
    tokens: leading/trailing space pairs keep half-width word edges from
    visually doubling the inter-word gap, punctuation-space pairs render
    punctuation plus a narrow trailing gap, and letter-colon pairs avoid a
    visible gap after narrow word tails like "Earth:".
    Script dialogs have room: lowercase pairs only, prioritized by frequency,
    assigned while the sacrificial pool lasts.
    """
    script_texts: list[str] = []
    for fp in sorted(translation_root.glob("*/chunk_*.txt")):
        for raw in fp.read_text(encoding="utf-8").splitlines():
            if "\t" in raw and not raw.startswith("#"):
                script_texts.append(TAG_RE.sub("", raw.split("\t", 1)[1]))
    menu_texts: list[str] = []
    for mp in menu_maps:
        if mp.exists():
            menu_texts.extend(map_target_texts(mp))

    singles: set[str] = set()
    menu_pairs: collections.Counter = collections.Counter()
    spacing_pairs: collections.Counter = collections.Counter()
    script_pairs: collections.Counter = collections.Counter()
    singles.update(extra_singles)
    for t in script_texts + menu_texts:
        for ch in t:
            if ch.islower() or ch in SINGLE_PUNCTUATION:
                singles.add(ch)
        spacing_pairs.update(" " + m.group(1) for m in SPACE_LETTER_RE.finditer(t))
        spacing_pairs.update(m.group(1) + " " for m in LETTER_SPACE_RE.finditer(t))
        spacing_pairs.update(m.group(1) + " " for m in PUNCT_SPACE_RE.finditer(t))
        spacing_pairs.update(m.group(1) + ":" for m in LETTER_COLON_RE.finditer(t))
    for p in PUNCT_PAIRS:
        spacing_pairs[p] += 1_000_000
    for t in menu_texts:
        for m in WORD_RE.finditer(t):
            for p in word_pairs(m.group(0)):
                menu_pairs[p] += 1
    for t in script_texts:
        for m in WORD_RE.finditer(t):
            for p in word_pairs(m.group(0)):
                script_pairs[p] += 1
    return singles, menu_pairs, spacing_pairs, script_pairs


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
    add_language_args(ap)
    ap.add_argument("--groups-report", default=None)
    ap.add_argument("--assignments", default=None)
    ap.add_argument("--out-assignments", default=None,
                    help="Write the completed assignment set here instead of "
                         "modifying the language pack CSV.")
    ap.add_argument("--translation-root", default=None,
                    help="Override the language pack's translated-text root.")
    ap.add_argument("--menu-map", action="append",
                    default=None,
                    help="Translation maps (repeatable); defaults to menu+names maps.")
    ap.add_argument("--system-source",
                    default="work/systemdump/system_strings.json",
                    help="Generated SYSTEM source dump used to resolve overlay ids.")
    ap.add_argument("--scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--scen2", default="work/extracted/SCEN2.DAT")
    args = ap.parse_args()

    lang = language_from_args(args)
    groups_report = Path(args.groups_report) if args.groups_report else COMMON_FONT_MAP
    assignments = Path(args.assignments) if args.assignments else lang.font_assignments
    out_assignments = (Path(args.out_assignments)
                       if args.out_assignments else assignments)
    translation_root = (Path(args.translation_root)
                        if args.translation_root else lang.dump_root)

    existing: dict[str, int] = {}
    rows = []
    apath = assignments
    if apath.exists():
        rows = list(csv.DictReader(open(apath, encoding="utf-8")))
        for r in rows:
            existing[r["char"]] = int(r["index_dec"])

    maps = [Path(p) for p in (args.menu_map or [str(lang.system_strings)])]
    singles, menu_pairs, spacing_pairs, script_pairs = needed_units(
        translation_root, maps, lang.single_chars
    )
    must = [c for c in sorted(singles) if c not in existing]
    must += [p for p, _ in menu_pairs.most_common() if p not in existing]
    optional = [p for p, _ in spacing_pairs.most_common()
                if p not in existing and p not in must]
    optional += [p for p, _ in script_pairs.most_common()
                 if p not in existing and p not in must and p not in optional]

    taken = set(existing.values())
    # BTLDAT/MRCUSW/SLPS are mostly code/data whose pseudo-runs would
    # inflate the "used in UI" set; real UI strings live in SYSTEM/ALLUS*.
    translated_keys = set()
    source_by_id: dict[str, dict] = {}
    source_path = Path(args.system_source)
    if source_path.exists():
        source_by_id = {
            entry["id"]: entry
            for entry in json.loads(source_path.read_text(encoding="utf-8"))
        }
    for mp in maps:
        if mp.exists():
            translated_keys |= map_jp_keys(mp, source_by_id)
    pool = [i for i in sacrificial_pool(
        groups_report, Path(args.scen), Path(args.scen2),
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
    def write_rows() -> None:
        out_assignments.parent.mkdir(parents=True, exist_ok=True)
        with out_assignments.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=["index_dec", "char", "replaced_char"],
                lineterminator="\n",
            )
            w.writeheader()
            w.writerows(rows)

    if not need:
        if out_assignments != assignments:
            write_rows()
        print("assignments up to date")
        return

    src = {int(r["index_dec"]): r["replaced_char"] for r in rows} if rows else {}
    gmap = {}
    for r in csv.DictReader(open(groups_report, encoding="utf-8")):
        if r["index_dec"].isdigit():
            gmap[int(r["index_dec"])] = r["char"]

    for unit in need:
        slot = pool.pop(0)
        rows.append({"index_dec": str(slot), "char": unit,
                     "replaced_char": gmap.get(slot, "")})

    write_rows()
    print(f"added {len(need)} assignments (total {len(rows)})")


if __name__ == "__main__":
    main()
