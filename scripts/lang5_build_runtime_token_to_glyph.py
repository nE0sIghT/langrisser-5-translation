#!/usr/bin/env python3
import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build runtime token->glyph candidate map from runtime_cache_dump.csv."
    )
    p.add_argument(
        "--in-csv",
        default="work/scen_analysis/runtime_cache_dump.csv",
        help="Input produced by scripts/lang5_runtime_cache_dump.py",
    )
    p.add_argument(
        "--out-csv",
        default="work/scen_analysis/token_to_glyph_runtime_candidates.csv",
        help="Output token->glyph candidates with support stats.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    in_csv = Path(args.in_csv)
    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    rows = list(csv.DictReader(in_csv.open(encoding="utf-8")))

    # Each RAM file contains two aligned slot streams:
    # - vm_u16_list: token/code in VM context
    # - raw_entry: 4-byte glyph/attr runtime entry
    # Build per-file slot alignment first.
    per_file = defaultdict(lambda: {"vm": {}, "raw": {}})
    for r in rows:
        slot_s = (r.get("slot") or "").strip()
        if not slot_s:
            continue
        try:
            slot = int(slot_s)
        except ValueError:
            continue

        ram_file = r.get("ram_file", "")
        row_type = r.get("row_type", "")
        if row_type == "vm_u16_list":
            code = (r.get("code_u16") or "").strip()
            if code:
                per_file[ram_file]["vm"][slot] = r
        elif row_type == "raw_entry":
            entry_hex = (r.get("entry_hex") or "").strip().upper()
            if entry_hex:
                per_file[ram_file]["raw"][slot] = r

    code_to_entry = defaultdict(Counter)
    code_to_char = defaultdict(Counter)
    for ram_file, data in per_file.items():
        common_slots = set(data["vm"]) & set(data["raw"])
        for slot in common_slots:
            vm = data["vm"][slot]
            raw = data["raw"][slot]
            code = vm["code_u16"].upper()
            entry_hex = raw["entry_hex"].upper()
            code_to_entry[code][entry_hex] += 1
            guess = (vm.get("tbl_guess") or "").strip()
            if guess:
                code_to_char[code][guess] += 1

    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "token_u16",
                "char_guess",
                "best_entry_hex",
                "best_b0",
                "best_b1",
                "best_b2",
                "best_b3",
                "support",
                "variants",
                "all_variants",
            ]
        )
        for code in sorted(code_to_entry.keys(), key=lambda x: int(x, 16)):
            cnt = code_to_entry[code]
            best, support = cnt.most_common(1)[0]
            b0, b1, b2, b3 = best[0:2], best[2:4], best[4:6], best[6:8]
            guess = code_to_char[code].most_common(1)[0][0] if code_to_char[code] else ""
            variants = "|".join(f"{h}:{n}" for h, n in cnt.most_common())
            w.writerow(
                [
                    code,
                    guess,
                    best,
                    b0,
                    b1,
                    b2,
                    b3,
                    support,
                    len(cnt),
                    variants,
                ]
            )

    print(f"wrote {out_csv} (codes={len(code_to_entry)})")


if __name__ == "__main__":
    main()
