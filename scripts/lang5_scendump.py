#!/usr/bin/env python3
"""Dump SCEN.DAT/SCEN2.DAT script text to per-chunk editable files.

Output layout (lang3 toolkit style):
    <out>/<STEM>/chunk_NNN.txt   lines: "<record_index>\t<text>"
    <out>/all_records.csv        flat list for analysis
    <out>/summary.txt
"""
import argparse
import csv
from pathlib import Path

from lang5_scen import (
    Codec,
    find_text_block,
    load_charmap_csv,
    read_chunk_spans,
    words_from_bytes,
)


def dump_file(src: Path, out_dir: Path, codec: Codec) -> list[dict[str, str]]:
    data = src.read_bytes()
    root = out_dir / src.stem
    root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []

    for cidx, (s, e) in enumerate(read_chunk_spans(data)):
        chunk = data[s:e]
        block = find_text_block(chunk)
        lines = [
            f"# file={src.name} chunk={cidx} chunk_start=0x{s:06X}",
            f"# block_base=0x{block.base:04X} block_size=0x{block.size:04X} records={block.record_count}",
        ]
        for ridx in range(1, block.record_count + 1):
            a, b = block.record_span(ridx)
            words = words_from_bytes(chunk[a:b])
            text = codec.decode(words)
            lines.append(f"{ridx}\t{text}")
            rows.append(
                {
                    "source_file": src.name,
                    "chunk_index": str(cidx),
                    "record_index": str(ridx),
                    "word_count": str(len(words)),
                    "text": text,
                }
            )
        (root / f"chunk_{cidx:03d}.txt").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--scen2", default="work/extracted/SCEN2.DAT")
    ap.add_argument("--charmap", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--out-dir", default="work/scriptdump")
    args = ap.parse_args()

    codec = Codec(load_charmap_csv(Path(args.charmap)))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    for src in (Path(args.scen), Path(args.scen2)):
        rows.extend(dump_file(src, out_dir, codec))

    csv_path = out_dir / "all_records.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["source_file", "chunk_index", "record_index", "word_count", "text"]
        )
        writer.writeheader()
        writer.writerows(rows)

    unknown = sum(r["text"].count("<$") for r in rows)
    (out_dir / "summary.txt").write_text(
        f"records={len(rows)}\ntagged_tokens={unknown}\ncharmap={args.charmap}\n",
        encoding="utf-8",
    )
    print(f"records={len(rows)} out={out_dir}")


if __name__ == "__main__":
    main()
