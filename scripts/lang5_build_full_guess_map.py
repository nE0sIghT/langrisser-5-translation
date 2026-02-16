#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Iterator, List, Tuple


def load_map(path: Path) -> Dict[int, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[int, str] = {}
    for k, v in raw.items():
        try:
            idx = int(k, 16)
        except Exception:
            continue
        if isinstance(v, str) and v:
            out[idx] = v
    return out


def sjis_stream() -> Iterator[Tuple[int, str]]:
    # Ordered by Shift-JIS code-space.
    for lead in range(0x81, 0xFD):
        if lead == 0xA0:
            continue
        for trail in range(0x40, 0xFD):
            if trail == 0x7F:
                continue
            code = (lead << 8) | trail
            b = bytes([lead, trail])
            try:
                ch = b.decode("cp932")
            except Exception:
                continue
            if len(ch) != 1:
                continue
            o = ord(ch)
            if o < 0x20:
                continue
            yield code, ch


def main() -> None:
    ap = argparse.ArgumentParser(description="Build full no-OCR token map from SJIS order with anchors.")
    ap.add_argument("--seed-map", default="work/font_export/token_map_guess_round3.json")
    ap.add_argument("--out-map", default="work/font_export/token_map_guess_full_noocr.json")
    ap.add_argument("--out-csv", default="work/font_export/token_map_guess_full_noocr.csv")
    ap.add_argument("--start-index", type=int, default=232)
    ap.add_argument("--max-index", type=int, default=1823)
    ap.add_argument(
        "--seed-max-index",
        type=int,
        default=232,
        help="Use seed anchors only up to this index (inclusive) for continuous full-range inference.",
    )
    args = ap.parse_args()

    seed_all = load_map(Path(args.seed_map))
    seed: Dict[int, str] = {k: v for k, v in seed_all.items() if k <= args.seed_max_index}
    stream = sjis_stream()

    mapped: Dict[int, str] = dict(seed)
    meta: List[Tuple[int, str, str, str]] = []

    cur_code, cur_ch = next(stream)
    for idx in range(args.start_index, args.max_index + 1):
        if idx in mapped and mapped[idx]:
            want = mapped[idx]
            if cur_ch != want:
                # Resync stream to anchor symbol.
                for code, ch in stream:
                    cur_code, cur_ch = code, ch
                    if ch == want:
                        break
            meta.append((idx, mapped[idx], "anchor_or_seed", f"{cur_code:04X}"))
            try:
                cur_code, cur_ch = next(stream)
            except StopIteration:
                break
            continue

        mapped[idx] = cur_ch
        meta.append((idx, cur_ch, "inferred_sjis_order", f"{cur_code:04X}"))
        try:
            cur_code, cur_ch = next(stream)
        except StopIteration:
            break

    out_map = Path(args.out_map)
    out_map.parent.mkdir(parents=True, exist_ok=True)
    out_json = {f"{k:04X}": mapped[k] for k in sorted(mapped) if mapped[k]}
    out_map.write_text(json.dumps(out_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out_csv = Path(args.out_csv)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["index_dec", "index_hex", "char", "source", "sjis_hex"])
        for idx in sorted(mapped):
            ch = mapped[idx]
            if not ch:
                continue
            src = "seed_only"
            sj = ""
            for m_idx, m_ch, m_src, m_sj in meta:
                if m_idx == idx and m_ch == ch:
                    src = m_src
                    sj = m_sj
                    break
            if not sj:
                try:
                    b = ch.encode("cp932")
                    if len(b) == 2:
                        sj = f"{(b[0]<<8)|b[1]:04X}"
                except Exception:
                    sj = ""
            w.writerow([idx, f"{idx:04X}", ch, src, sj])

    print(f"seed_map={args.seed_map}")
    print(f"out_map={out_map}")
    print(f"out_csv={out_csv}")
    print(f"mapped_entries={len(out_json)}")


if __name__ == "__main__":
    main()
