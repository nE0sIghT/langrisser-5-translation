#!/usr/bin/env python3
import argparse
import csv
import struct
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description="Dump Langrisser V VM dispatch tables from PS1 RAM dump.")
    ap.add_argument("--ram", default="work/ram.bin")
    ap.add_argument("--base-main", type=lambda x: int(x, 0), default=0x00010200)
    ap.add_argument("--count-main", type=int, default=16)
    ap.add_argument("--base-secondary", type=lambda x: int(x, 0), default=0x00010250)
    ap.add_argument("--count-secondary", type=int, default=24)
    ap.add_argument("--out-csv", default="work/scen_analysis/vm_dispatch_tables.csv")
    args = ap.parse_args()

    ram = Path(args.ram).read_bytes()
    rows = []
    for kind, base, count in (
        ("main", args.base_main, args.count_main),
        ("secondary", args.base_secondary, args.count_secondary),
    ):
        for i in range(count):
            off = base + i * 4
            if off + 4 > len(ram):
                break
            v = struct.unpack_from("<I", ram, off)[0]
            rows.append(
                {
                    "table": kind,
                    "index": i,
                    "ram_off": f"0x{off:06X}",
                    "target": f"0x{v:08X}",
                }
            )

    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["table", "index", "ram_off", "target"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
