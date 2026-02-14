#!/usr/bin/env python3
import argparse
import csv
import json
import struct
from pathlib import Path


BASE = 0x80000000


def u32(mem: bytes, addr: int) -> int:
    return struct.unpack_from("<I", mem, addr - BASE)[0]


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Dump Langrisser V runtime token/glyph cache tables from RAM dump."
    )
    ap.add_argument("--ram", default="work/scen_analysis/SLPS-01819_6_ram.bin")
    ap.add_argument("--out-prefix", default="work/scen_analysis/runtime_token_table")
    args = ap.parse_args()

    mem = Path(args.ram).read_bytes()
    out_prefix = Path(args.out_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    # Observed runtime globals and table addresses from reverse work.
    ptr_script_base = u32(mem, 0x800DB90C)
    ptr_script_cur = u32(mem, 0x800DBA1C)
    ptr_tbl_b34c = u32(mem, 0x800DB34C)  # often 0x80108910
    ptr_tbl_b3f8 = u32(mem, 0x800DB3F8)
    ptr_tbl_b6c0 = u32(mem, 0x800DB6C0)
    tbl_active = 0x80108C68  # gp+0xE38 init in SLPS startup

    summary = {
        "ram": str(Path(args.ram)),
        "script_base": f"0x{ptr_script_base:08X}",
        "script_cur": f"0x{ptr_script_cur:08X}",
        "tbl_b34c_ptr": f"0x{ptr_tbl_b34c:08X}",
        "tbl_b3f8_ptr": f"0x{ptr_tbl_b3f8:08X}",
        "tbl_b6c0_ptr": f"0x{ptr_tbl_b6c0:08X}",
        "active_token_table": f"0x{tbl_active:08X}",
    }

    # Dump active 4-byte entries (0x800 bytes -> 512 entries).
    active_csv = out_prefix.with_name(out_prefix.name + "_active_80108C68.csv")
    with active_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["slot", "glyph_u16", "attr_b2", "attr_b3", "raw_hex"])
        off = tbl_active - BASE
        block = mem[off : off + 0x800]
        for i in range(0x800 // 4):
            e = block[i * 4 : i * 4 + 4]
            glyph = struct.unpack_from("<H", e, 0)[0]
            w.writerow([i, f"{glyph:04X}", e[2], e[3], e.hex().upper()])
        summary["active_nz_bytes"] = sum(1 for b in block if b)

    # Dump neighbor raw blocks for deeper RE correlation.
    neighbors = [
        ("tbl_80108910_raw.bin", 0x80108910, 0x600),
        ("tbl_80108B02_raw.bin", 0x80108B02, 0x600),
        ("tbl_80108C68_raw.bin", 0x80108C68, 0x800),
    ]
    for name, addr, size in neighbors:
        chunk = mem[addr - BASE : addr - BASE + size]
        p = out_prefix.with_name(name)
        p.write_bytes(chunk)
        summary[f"{name}_nz_bytes"] = sum(1 for b in chunk if b)

    summary_json = out_prefix.with_suffix(".json")
    summary_json.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {active_csv}")
    print(f"wrote {summary_json}")


if __name__ == "__main__":
    main()
