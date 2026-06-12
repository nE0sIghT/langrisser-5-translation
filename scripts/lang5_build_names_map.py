#!/usr/bin/env python3
"""Generate the name-string translation map from names_base.csv.

Scans FFFF-terminated runs in SYSTEM.BIN/ALLUSW/ALLUSB, matches each
decoded string against the base dictionary (directly or as base+number),
picks the longest EN candidate that fits the run's printable slots and
writes data/translation/names_map.json. Unmatched JP-looking runs and
entries that do not fit are reported.
"""
import argparse
import csv
import json
import re
import struct
from pathlib import Path

from lang5_scen import load_charmap_csv

JP_RE = re.compile(r"[぀-ヿ一-鿿]")
NUM_RE = re.compile(r"^(.*?)([0-9]+)$")
PAIR_TAIL = set("abcdefghijklmnopqrstuvwxyz'.,0123456789")


def est_cells(text: str) -> int:
    cells = 0
    for part in re.findall(r"[A-Za-z'.,0-9]+|.", text):
        if re.fullmatch(r"[A-Za-z'.,0-9]+", part):
            i = 0
            while i < len(part):
                a = part[i]
                b = part[i + 1] if i + 1 < len(part) else ""
                if b and b in PAIR_TAIL and (a in PAIR_TAIL or (a.isupper() and i == 0)):
                    i += 2
                else:
                    i += 1
                cells += 1
        else:
            cells += 1
    return cells


def decode_run(words, tok2ch):
    out = []
    for w in words:
        if w in tok2ch:
            out.append(tok2ch[w])
        elif w >= 0xFF00:
            out.append("{%04X}" % w)
        else:
            out.append("[%04X]" % w)
    return "".join(out)


def runs_of(data: bytes, min_off: int):
    ws = list(struct.unpack(f"<{len(data)//2}H", data[: len(data) & ~1]))
    out = []
    start = 0
    for i, w in enumerate(ws):
        if w == 0xFFFF:
            if 2 <= i + 1 - start <= 80 and start * 2 >= min_off:
                out.append(ws[start : i + 1])
            start = i + 1
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="data/translation/names_base.csv")
    ap.add_argument("--groups-report", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--out", default="data/translation/names_map.json")
    args = ap.parse_args()

    tok2ch = load_charmap_csv(Path(args.groups_report))
    base: dict[str, list[str]] = {}
    for row in csv.DictReader(open(args.base, encoding="utf-8")):
        cands = [row["en"]] + ([row["alt"]] if row["alt"] else [])
        base[row["jp"]] = cands

    out: dict[str, str] = {}
    misfits: list[str] = []
    unmatched: dict[str, int] = {}

    for fname, min_off in (("SYSTEM.BIN", 0x9560), ("ALLUSW.BIN", 0), ("ALLUSB.BIN", 0)):
        data = Path("work/extracted", fname).read_bytes()
        for seg in runs_of(data, min_off):
            key = decode_run(seg, tok2ch)
            core = key[:-6] if key.endswith("{FFFF}") else key
            if key in out or not JP_RE.search(core):
                continue
            cands = None
            if core in base:
                cands = list(base[core])
            else:
                m = NUM_RE.match(core)
                if m and m.group(1) in base:
                    bs, num = base[m.group(1)], m.group(2)
                    cands = [f"{c} {num}" for c in bs] + [f"{c}{num}" for c in bs]
            if cands is None:
                if "[" not in core and "␣" not in core:
                    unmatched[core] = unmatched.get(core, 0) + 1
                continue
            slots = sum(1 for w in seg if w < 0xE000)
            chosen = next((c for c in cands if est_cells(c) <= slots), None)
            if chosen is None:
                misfits.append(f"{core} -> {cands[0]} ({est_cells(cands[0])}>{slots})")
            else:
                out[key] = chosen

    # Emit every remaining glossary entry as a speculative key: strings
    # hidden behind offset tables never appear as clean runs, but the
    # verbatim-scan pass of the menu patcher can still find and patch
    # them as long as a key exists. Budget: one slot per JP char (the
    # scan re-checks the exact fit with the real encoder).
    for core, cands in base.items():
        key = core + "{FFFF}"
        if key in out:
            continue
        chosen = next((c for c in cands if est_cells(c) <= len(core)), None)
        if chosen:
            out[key] = chosen

    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"mapped={len(out)} misfits={len(misfits)} unmatched_jp={len(unmatched)}")
    for m in misfits[:30]:
        print("  MISFIT", m)
    rep = Path("work/scen_analysis/names_unmatched.txt")
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text("\n".join(sorted(unmatched)), encoding="utf-8")
    print(f"unmatched list: {rep}")


if __name__ == "__main__":
    main()
