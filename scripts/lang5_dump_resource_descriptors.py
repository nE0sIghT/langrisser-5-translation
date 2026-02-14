#!/usr/bin/env python3
import argparse
import csv
import re
import struct
import subprocess
from pathlib import Path


BASE = 0x80000000
TABLE_ADDR = 0x8010DB40
ENTRY_SIZE = 0x18
SECTOR_USER = 2048
SECTOR_RAW = 2352
LEADIN_LBA = 150


def decode_name(name_bytes: bytes) -> str:
    # 12-byte name is stored as 3 little-endian words in RAM; convert to ASCII.
    # Example dwords: 54535953 422E4D45 313B4E49 -> "SYSTEM.BIN;1"
    out = bytearray()
    for i in range(0, min(len(name_bytes), 12), 4):
        w = struct.unpack_from("<I", name_bytes, i)[0]
        out.extend(w.to_bytes(4, "little"))
    return out.split(b"\x00", 1)[0].decode("ascii", errors="ignore")


def bcd_to_int(v: int) -> int:
    return ((v >> 4) * 10) + (v & 0x0F)


def decode_cdl_loc_le_u32(v: int):
    b0 = v & 0xFF
    b1 = (v >> 8) & 0xFF
    b2 = (v >> 16) & 0xFF
    b3 = (v >> 24) & 0xFF
    mm = bcd_to_int(b0)
    ss = bcd_to_int(b1)
    ff = bcd_to_int(b2)
    mode = b3
    lba = ((mm * 60 + ss) * 75 + ff) - LEADIN_LBA
    return {
        "mm_bcd": b0,
        "ss_bcd": b1,
        "ff_bcd": b2,
        "mode_raw": mode,
        "mm": mm,
        "ss": ss,
        "ff": ff,
        "lba": lba,
    }


def list_iso_lbas(bin_path: str):
    cmd = ["python3", "scripts/iso_mode2.py", bin_path, "list"]
    try:
        cp = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except Exception:
        return {}
    out = {}
    for ln in cp.stdout.splitlines():
        m = re.match(r"^f\s+(\d+)\s+(\d+)\s+(.+)$", ln.strip())
        if not m:
            continue
        lba = int(m.group(1))
        size = int(m.group(2))
        name = m.group(3).split("/")[-1].split(";")[0].upper()
        out[name] = (lba, size)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Dump Langrisser V runtime resource descriptors from RAM.")
    ap.add_argument("--ram", default="work/scen_analysis/SLPS-01819_1_ram.bin")
    ap.add_argument("--bin", default="iso/SLPS-01818-9-B.bin", help="MODE2/2352 BIN for optional LBA/size verification.")
    ap.add_argument("--out", default="work/scen_analysis/resource_descriptors.csv")
    ap.add_argument("--max-entries", type=int, default=64)
    args = ap.parse_args()

    mem = Path(args.ram).read_bytes()
    off = TABLE_ADDR - BASE
    iso_lbas = list_iso_lbas(args.bin) if Path(args.bin).exists() else {}

    rows = []
    for i in range(args.max_entries):
        eoff = off + i * ENTRY_SIZE
        e = mem[eoff : eoff + ENTRY_SIZE]
        if len(e) < ENTRY_SIZE:
            break
        v0, v1 = struct.unpack_from("<II", e, 0)
        name = decode_name(e[8:20])
        tail = struct.unpack_from("<I", e, 20)[0]
        loc = decode_cdl_loc_le_u32(v0)
        base = name.split(";")[0].upper() if name else ""
        iso = iso_lbas.get(base)
        iso_lba = iso[0] if iso else ""
        iso_size = iso[1] if iso else ""
        lba_ok = (loc["lba"] == iso_lba) if iso else ""
        size_ok = (v1 == iso_size) if iso else ""
        rows.append(
            {
                "index": i,
                "cdloc_hex": f"0x{v0:08X}",
                "mmssff_bcd": f"{loc['mm_bcd']:02X}:{loc['ss_bcd']:02X}:{loc['ff_bcd']:02X}",
                "mmssff_dec": f"{loc['mm']:02d}:{loc['ss']:02d}:{loc['ff']:02d}",
                "lba_dec": loc["lba"],
                "user_offset_2048_hex": f"0x{(loc['lba'] * SECTOR_USER):X}",
                "raw_offset_2352_hex": f"0x{(loc['lba'] * SECTOR_RAW):X}",
                "size_hex": f"0x{v1:08X}",
                "size_dec": v1,
                "name": name,
                "iso_lba_dec": iso_lba,
                "iso_size_dec": iso_size,
                "iso_lba_match": lba_ok,
                "iso_size_match": size_ok,
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
                "cdloc_hex",
                "mmssff_bcd",
                "mmssff_dec",
                "lba_dec",
                "user_offset_2048_hex",
                "raw_offset_2352_hex",
                "size_hex",
                "size_dec",
                "name",
                "iso_lba_dec",
                "iso_size_dec",
                "iso_lba_match",
                "iso_size_match",
                "tail_hex",
                "raw_hex",
            ],
        )
        w.writeheader()
        w.writerows(rows)

    print(f"wrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
