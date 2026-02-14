#!/usr/bin/env python3
import argparse
import csv
import struct
from pathlib import Path


BASE = 0x80000000
TABLE_ADDR = 0x8010DB40
ENTRY_SIZE = 0x18


def decode_name(name_bytes: bytes) -> str:
    # 12-byte name is stored as 3 little-endian words in RAM; convert to ASCII.
    # Example dwords: 54535953 422E4D45 313B4E49 -> "SYSTEM.BIN;1"
    out = bytearray()
    for i in range(0, min(len(name_bytes), 12), 4):
        w = struct.unpack_from("<I", name_bytes, i)[0]
        out.extend(w.to_bytes(4, "little"))
    return out.split(b"\x00", 1)[0].decode("ascii", errors="ignore")


def main() -> None:
    ap = argparse.ArgumentParser(description="Dump Langrisser V runtime resource descriptors from RAM.")
    ap.add_argument("--ram", default="work/scen_analysis/SLPS-01819_1_ram.bin")
    ap.add_argument("--out", default="work/scen_analysis/resource_descriptors.csv")
    ap.add_argument("--max-entries", type=int, default=64)
    args = ap.parse_args()

    mem = Path(args.ram).read_bytes()
    off = TABLE_ADDR - BASE

    rows = []
    for i in range(args.max_entries):
        eoff = off + i * ENTRY_SIZE
        e = mem[eoff : eoff + ENTRY_SIZE]
        if len(e) < ENTRY_SIZE:
            break
        v0, v1 = struct.unpack_from("<II", e, 0)
        name = decode_name(e[8:20])
        tail = struct.unpack_from("<I", e, 20)[0]
        rows.append(
            {
                "index": i,
                "offset_2048_hex": f"0x{v0:08X}",
                "size_hex": f"0x{v1:08X}",
                "size_dec": v1,
                "name": name,
                "tail_hex": f"0x{tail:08X}",
                "raw_hex": e.hex().upper(),
            }
        )
        if v0 == 0 and v1 == 0 and not name:
            break

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "index",
                "offset_2048_hex",
                "size_hex",
                "size_dec",
                "name",
                "tail_hex",
                "raw_hex",
            ],
        )
        w.writeheader()
        w.writerows(rows)

    print(f"wrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
