#!/usr/bin/env python3
import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List


SEED_MAP = {
    0x00C6: "ラ",
    0x00CD: "ン",
    0x00B2: "フ",
    0x0086: "ォ",
    0x00D1: "ー",
    0x00A6: "ド",
    0x020E: "元",
    0x020F: "帥",
}


def load_font_map(path: Path, min_conf: float) -> Dict[int, str]:
    out: Dict[int, str] = {}
    with path.open("r", encoding="utf-8") as fh:
        r = csv.DictReader(fh)
        for row in r:
            try:
                idx = int(row["index"])
                conf = float(row["conf"])
            except Exception:
                continue
            if conf < min_conf:
                continue
            ch = (row.get("ocr_char") or "").strip()
            if not ch:
                continue
            out[idx] = ch[-1]
    out.update(SEED_MAP)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Extract token-like text runs from SYSTEM.BIN with OCR-derived token map.")
    p.add_argument("--bin", default="work/extracted/SYSTEM.BIN")
    p.add_argument("--font-map", default="work/scen_analysis/font_sheet_ocr_map.csv")
    p.add_argument("--min-conf", type=float, default=35.0)
    p.add_argument("--min-len", type=int, default=20)
    p.add_argument("--out-csv", default="work/scen_analysis/system_token_runs.csv")
    p.add_argument("--out-txt", default="work/scen_analysis/system_token_runs.txt")
    args = p.parse_args()

    mp = load_font_map(Path(args.font_map), args.min_conf)
    b = Path(args.bin).read_bytes()
    words = [b[i] | (b[i + 1] << 8) for i in range(0, len(b) - 1, 2)]

    rows: List[dict] = []
    i = 0
    while i < len(words):
        if words[i] not in mp and words[i] != 0xFFFF:
            i += 1
            continue
        j = i
        toks = []
        dec = []
        mapped = 0
        while j < len(words):
            w = words[j]
            toks.append(f"{w:04X}")
            if w in mp:
                dec.append(mp[w])
                mapped += 1
            elif w == 0xFFFF:
                dec.append("⌁")
            elif w < 0x0100:
                dec.append(" ")
            else:
                dec.append(f"[{w:04X}]")
            if len(toks) >= 8 and mapped / len(toks) < 0.35:
                break
            if len(toks) > 240:
                break
            j += 1
        if len(toks) >= args.min_len and mapped >= 8:
            rows.append(
                {
                    "offset": f"0x{i * 2:06X}",
                    "word_count": len(toks),
                    "mapped_ratio": f"{mapped / max(1, len(toks)):.3f}",
                    "decoded": "".join(dec),
                    "tokens_hex": " ".join(toks),
                }
            )
        i = max(i + 1, j)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["offset", "word_count", "mapped_ratio", "decoded", "tokens_hex"])
        w.writeheader()
        w.writerows(rows)

    out_txt = Path(args.out_txt)
    with out_txt.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(f"{r['offset']} words={r['word_count']} ratio={r['mapped_ratio']}\n")
            fh.write(f"DEC: {r['decoded']}\n")
            fh.write(f"TOK: {r['tokens_hex']}\n\n")

    print(f"map size: {len(mp)}")
    print(f"runs: {len(rows)}")
    print(f"wrote {out_csv}")
    print(f"wrote {out_txt}")


if __name__ == "__main__":
    main()
