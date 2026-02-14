#!/usr/bin/env python3
import argparse
import csv
import json
import re
import struct
from pathlib import Path
from typing import Dict, List


def load_map(path: Path) -> Dict[int, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[int, str] = {}
    for k, v in raw.items():
        try:
            t = int(k, 16)
        except Exception:
            continue
        if isinstance(v, str) and v:
            out[t] = v[0]
    return out


def decode_words(words: List[int], mp: Dict[int, str]) -> str:
    out: List[str] = []
    for w in words:
        if w in mp:
            out.append(mp[w])
        elif 0xFF00 <= w <= 0xFFFF:
            out.append("{" + f"{w:04X}" + "}")
        else:
            out.append("[" + f"{w:04X}" + "]")
    return "".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract readable token runs from PS1 RAM dump.")
    ap.add_argument("--ram", default="work/ram.bin")
    ap.add_argument("--token-map", default="scripts/lang5_token_map_manual.json")
    ap.add_argument("--out-csv", default="work/scen_analysis/ram_token_runs.csv")
    ap.add_argument("--min-len", type=int, default=6)
    ap.add_argument("--max-len", type=int, default=120)
    ap.add_argument("--min-mapped", type=int, default=5)
    ap.add_argument("--min-ratio", type=float, default=0.35)
    args = ap.parse_args()

    ram = Path(args.ram).read_bytes()
    mp = load_map(Path(args.token_map))
    words = [struct.unpack_from("<H", ram, i)[0] for i in range(0, len(ram), 2)]

    rows: List[dict] = []
    start = 0
    for i, w in enumerate(words):
        if w != 0xFFFF:
            continue
        seg = words[start : i + 1]
        start = i + 1
        if not (args.min_len <= len(seg) <= args.max_len):
            continue
        mapped = sum(1 for x in seg if x in mp)
        ctrl = sum(1 for x in seg if 0xFF00 <= x <= 0xFFFF)
        denom = max(1, len(seg) - ctrl)
        ratio = mapped / denom
        if mapped < args.min_mapped or ratio < args.min_ratio:
            continue
        rows.append(
            {
                "offset": f"0x{(start - len(seg)) * 2:06X}",
                "word_count": len(seg),
                "mapped_count": mapped,
                "mapped_ratio": f"{ratio:.3f}",
                "decoded_manual": decode_words(seg, mp),
                "words_hex": " ".join(f"{x:04X}" for x in seg),
            }
        )

    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["offset", "word_count", "mapped_count", "mapped_ratio", "decoded_manual", "words_hex"],
        )
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
