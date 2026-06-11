#!/usr/bin/env python3
"""Patch SYSTEM.BIN menu/UI strings using the decoded-run dictionary.

Strings are FFFF-terminated token runs at fixed offsets, so an EN
replacement must fit into the run's printable slots. The EN table includes
pair glyphs (two letters per cell), which makes most labels fit. Runs whose
translation does not fit are reported and left untouched.
"""
import argparse
import csv
import json
import struct
from pathlib import Path

from lang5_scen import Codec, load_charmap_csv, load_charmap_tbl

ASCII_NORMALIZE = str.maketrans({"?": "？", "!": "！", "’": "'", "‘": "'"})


def decode_run(words: list[int], tok2ch: dict[int, str]) -> str:
    out = []
    for w in words:
        if w in tok2ch:
            out.append(tok2ch[w])
        elif w >= 0xFF00:
            out.append("{%04X}" % w)
        else:
            out.append("[%04X]" % w)
    return "".join(out)


def split_ffff_runs(words: list[int], min_len: int = 2, max_len: int = 80):
    runs = []
    start = 0
    for i, w in enumerate(words):
        if w != 0xFFFF:
            continue
        if min_len <= i + 1 - start <= max_len:
            runs.append((start, i + 1))
        start = i + 1
    return runs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--system-in", default="work/extracted/SYSTEM.BIN")
    ap.add_argument("--system-out", default="work/build/SYSTEM.BIN.menu")
    ap.add_argument("--groups-report", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--tbl", default="work/tables/lang5_en.tbl")
    ap.add_argument("--menu-map", default="data/translation/system_menu_map.json")
    ap.add_argument("--report-csv", default="work/scen_analysis/system_menu_occurrences.csv")
    args = ap.parse_args()

    tok2ch = load_charmap_csv(Path(args.groups_report))
    codec = Codec(load_charmap_tbl(Path(args.tbl)))
    menu_map: dict[str, str] = json.loads(Path(args.menu_map).read_text(encoding="utf-8"))

    src = Path(args.system_in).read_bytes()
    words = list(struct.unpack(f"<{len(src)//2}H", src[: len(src) & ~1]))

    patched = misfit = 0
    rows = []
    for a, b in split_ffff_runs(words):
        if a * 2 < 0x8100:
            continue  # font plane + offset tables; never patch there
        seg = words[a:b]
        dec = decode_run(seg, tok2ch)
        en = menu_map.get(dec)
        status = ""
        if en:
            slots = [i for i, w in enumerate(seg) if w < 0xE000]
            try:
                toks = codec.encode(en.translate(ASCII_NORMALIZE))
            except ValueError as exc:
                rows.append({"offset_hex": f"0x{a*2:05X}", "word_count": str(len(seg)),
                             "decoded_jp": dec, "mapped_en": en,
                             "status": f"UNENCODABLE {exc}"})
                misfit += 1
                continue
            if len(toks) > len(slots):
                status = f"MISFIT {len(toks)}>{len(slots)}"
                misfit += 1
            else:
                out = list(seg)
                space = codec.char2tok.get(" ", 0)
                for k, idx in enumerate(slots):
                    out[idx] = toks[k] if k < len(toks) else space
                words[a:b] = out
                patched += 1
                status = "ok"
        rows.append({"offset_hex": f"0x{a*2:05X}", "word_count": str(len(seg)),
                     "decoded_jp": dec, "mapped_en": en or "", "status": status})

    out_path = Path(args.system_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(struct.pack(f"<{len(words)}H", *words) + src[len(words) * 2 :])

    rep = Path(args.report_csv)
    rep.parent.mkdir(parents=True, exist_ok=True)
    with rep.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["offset_hex", "word_count", "decoded_jp", "mapped_en", "status"])
        w.writeheader()
        w.writerows(rows)

    print(f"patched_runs={patched} misfits={misfit} out={out_path} report={rep}")


if __name__ == "__main__":
    main()
