#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(description="Export rows that contain decoded JP seed glyphs.")
    p.add_argument("--alignment", default="work/scen_analysis/story_alignment_partial_decode.csv")
    p.add_argument("--out", default="work/scen_analysis/seed_decode_examples.csv")
    args = p.parse_args()

    keep_chars = set("ランフォード元帥")
    rows = []

    with Path(args.alignment).open("r", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            jp = r.get("jp_partially_decoded", "")
            if any(ch in jp for ch in keep_chars):
                rows.append(
                    {
                        "scenario": r.get("scenario", ""),
                        "seq": r.get("seq", ""),
                        "jp_partially_decoded": jp,
                        "en_line": r.get("en_line", ""),
                    }
                )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["scenario", "seq", "jp_partially_decoded", "en_line"],
        )
        w.writeheader()
        w.writerows(rows)

    print(f"wrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
