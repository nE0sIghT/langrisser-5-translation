#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(description="Build a canonical tokenized source dump from alignment CSV.")
    p.add_argument("--alignment", default="work/scen_analysis/story_alignment_partial_decode.csv")
    p.add_argument("--out-txt", default="work/scen_analysis/source_script_tokenized.txt")
    p.add_argument("--out-csv", default="work/scen_analysis/source_script_tokenized.csv")
    args = p.parse_args()

    rows = []
    with Path(args.alignment).open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            if not r.get("jp_tokenized"):
                continue
            rows.append(r)

    # stable order
    rows.sort(key=lambda r: (r["scenario"], int(r["seq"] or 0)))

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "scenario",
                "chunk_index",
                "seq",
                "jp_record_index",
                "jp_tokenized",
                "jp_partially_decoded",
                "en_line",
            ],
        )
        w.writeheader()
        w.writerows(rows)

    out_txt = Path(args.out_txt)
    with out_txt.open("w", encoding="utf-8") as fh:
        current = None
        for r in rows:
            scenario = r["scenario"]
            if scenario != current:
                current = scenario
                fh.write(f"\n=== {scenario} (chunk {r['chunk_index']}) ===\n")
            seq = r["seq"]
            ridx = r["jp_record_index"]
            jp = r["jp_partially_decoded"] or r["jp_tokenized"]
            en = r["en_line"]
            fh.write(f"[{seq:>4}] rec={ridx:>4} JP: {jp}\n")
            if en:
                fh.write(f"       EN: {en}\n")

    print(f"wrote {out_csv}")
    print(f"wrote {out_txt}")


if __name__ == "__main__":
    main()
