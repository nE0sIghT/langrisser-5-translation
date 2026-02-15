#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path


RAM_BASE = 0x80000000
RAM_STAGE_BYTE_ADDR = 0x800DB931
TABLE_ADDR = 0x80108C68
TABLE_SIZE = 0x800
ENTRY_SIZE = 4


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Extract Langrisser V token->glyph table from ADPCM.DAT using loader algorithm."
    )
    p.add_argument("--adpcm", default="work/extracted/ADPCM.DAT")
    p.add_argument(
        "--stage",
        type=int,
        default=None,
        help="Value used by loader (db931). If omitted and --ram is set, taken from RAM.",
    )
    p.add_argument(
        "--ram",
        default=None,
        help="Optional RAM dump to auto-read db931 and/or verify loaded table at 0x80108C68.",
    )
    p.add_argument("--out-csv", default="work/scen_analysis/token_glyph_table_from_adpcm.csv")
    p.add_argument("--verify", action="store_true", help="If --ram is given, verify bytes vs RAM table.")
    return p.parse_args()


def read_stage_from_ram(ram: bytes) -> int:
    return ram[RAM_STAGE_BYTE_ADDR - RAM_BASE]


def extract_block(adpcm: bytes, stage: int) -> bytes:
    # Loader path:
    #   FUN_80019430 -> FUN_8001A8E0(id=0x0B, ..., param3=db931+1, size=0x800)
    #   source_lba = descriptor_lba + param3, and 1 sector == 0x800 bytes.
    # For ADPCM.DAT payload this is equivalent to:
    #   byte_offset = (stage + 1) * 0x800
    off = (stage + 1) * 0x800
    end = off + TABLE_SIZE
    if off < 0 or end > len(adpcm):
        raise ValueError(f"ADPCM offset out of range: stage={stage}, off=0x{off:X}, size=0x{len(adpcm):X}")
    return adpcm[off:end]


def main() -> None:
    args = parse_args()
    adpcm = Path(args.adpcm).read_bytes()
    ram = Path(args.ram).read_bytes() if args.ram else None

    stage = args.stage
    if stage is None:
        if ram is None:
            raise SystemExit("Need either --stage or --ram.")
        stage = read_stage_from_ram(ram)

    block = extract_block(adpcm, stage)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["token_u16", "glyph_u16", "attr_b2", "attr_b3", "entry_hex"])
        for token in range(TABLE_SIZE // ENTRY_SIZE):
            off = token * ENTRY_SIZE
            e = block[off : off + 4]
            glyph = int.from_bytes(e[0:2], "little")
            w.writerow([f"{token:04X}", f"{glyph:04X}", e[2], e[3], e.hex().upper()])

    print(f"stage={stage} block_offset=0x{(stage + 1) * 0x800:X}")
    print(f"wrote {out_csv}")

    if args.verify:
        if ram is None:
            raise SystemExit("--verify requires --ram.")
        ram_block = ram[TABLE_ADDR - RAM_BASE : TABLE_ADDR - RAM_BASE + TABLE_SIZE]
        same = ram_block == block
        print(f"verify_ram_table={same}")


if __name__ == "__main__":
    main()
