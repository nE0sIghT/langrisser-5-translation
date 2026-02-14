#!/usr/bin/env python3
import argparse
import csv
import struct
from pathlib import Path
from typing import List, Tuple


def ru16(b: bytes, off: int) -> int:
    return struct.unpack_from("<H", b, off)[0]


def ru32(b: bytes, off: int) -> int:
    return struct.unpack_from("<I", b, off)[0]


def parse_u16_list(block: bytes, off: int, max_items: int = 512) -> List[int]:
    out: List[int] = []
    p = off
    for _ in range(max_items):
        if p + 2 > len(block):
            break
        v = ru16(block, p)
        p += 2
        if v == 0xFFFF:
            break
        out.append(v)
    return out


def parse_entry_first(block: bytes, off: int) -> Tuple[int, int, int, int]:
    # Returns (flags_u16, op_u8, arg_u8, arg_u16)
    if off + 6 > len(block):
        return (0, 0xFF, 0, 0)
    flags = ru16(block, off)
    op = block[off + 2]
    arg_u8 = block[off + 3]
    arg_u16 = ru16(block, off + 4)
    return (flags, op, arg_u8, arg_u16)


def words_hex(block: bytes, off: int, count: int = 12) -> str:
    end = min(len(block), off + count * 2)
    ws: List[str] = []
    for p in range(off, end - 1, 2):
        ws.append(f"{ru16(block, p):04X}")
    return " ".join(ws)


def main() -> None:
    ap = argparse.ArgumentParser(description="Dump Langrisser V VM block layout (section pointers + entry lists).")
    ap.add_argument("--bin", default="work/extracted/SCEN.DAT")
    ap.add_argument("--base-off", type=lambda x: int(x, 0), default=0x840)
    ap.add_argument("--block-size", type=lambda x: int(x, 0), default=0x1AB4)
    ap.add_argument("--section-count", type=int, default=11)
    ap.add_argument("--out-csv", default="work/scen_analysis/vm_layout_section_entries.csv")
    ap.add_argument("--out-txt", default="work/scen_analysis/vm_layout_summary.txt")
    args = ap.parse_args()

    src = Path(args.bin).read_bytes()
    block = src[args.base_off : args.base_off + args.block_size]
    if len(block) < args.block_size:
        raise RuntimeError("block shorter than requested size")

    section_ptrs = [ru32(block, i * 4) for i in range(args.section_count)]
    header_tail = [ru32(block, i) for i in (0x2C, 0x30, 0x34, 0x38, 0x3C)]

    rows = []
    lines: List[str] = []
    lines.append(f"source={args.bin}")
    lines.append(f"base_off=0x{args.base_off:X}")
    lines.append(f"block_size=0x{args.block_size:X}")
    lines.append(f"section_count={args.section_count}")
    lines.append("section_ptrs=" + ", ".join(f"{p:08X}" for p in section_ptrs))
    lines.append("header_tail(2C..3C)=" + ", ".join(f"{v:08X}" for v in header_tail))
    lines.append("")

    for si, sp in enumerate(section_ptrs):
        if sp >= len(block):
            lines.append(f"[section {si}] ptr=0x{sp:04X} OUT_OF_RANGE")
            continue
        lst = parse_u16_list(block, sp)
        lines.append(f"[section {si}] ptr=0x{sp:04X} entries={len(lst)}")
        for ei, eo in enumerate(lst):
            if eo >= len(block):
                rows.append(
                    {
                        "section_index": si,
                        "section_ptr": f"0x{sp:04X}",
                        "entry_index": ei,
                        "entry_off": f"0x{eo:04X}",
                        "entry_abs_off": f"0x{args.base_off + eo:06X}",
                        "flags_u16": "",
                        "op_u8": "",
                        "arg_u8": "",
                        "arg_u16": "",
                        "entry_words": "",
                    }
                )
                continue
            flags, op, arg_u8, arg_u16 = parse_entry_first(block, eo)
            eh = words_hex(block, eo, 12)
            rows.append(
                {
                    "section_index": si,
                    "section_ptr": f"0x{sp:04X}",
                    "entry_index": ei,
                    "entry_off": f"0x{eo:04X}",
                    "entry_abs_off": f"0x{args.base_off + eo:06X}",
                    "flags_u16": f"{flags:04X}",
                    "op_u8": f"{op:02X}",
                    "arg_u8": f"{arg_u8:02X}",
                    "arg_u16": f"{arg_u16:04X}",
                    "entry_words": eh,
                }
            )
            if ei < 4:
                lines.append(
                    f"  e{ei:02d} off=0x{eo:04X} flags={flags:04X} op={op:02X} arg8={arg_u8:02X} arg16={arg_u16:04X} words={eh}"
                )
        lines.append("")

    # Probe known extra pointer-list candidates from header tail.
    for label, ptr in (("extra_2C", header_tail[0]), ("extra_30", header_tail[1]), ("extra_34", header_tail[2])):
        if ptr >= len(block):
            continue
        lst = parse_u16_list(block, ptr)
        lines.append(f"[{label}] ptr=0x{ptr:04X} entries={len(lst)}")
        for ei, eo in enumerate(lst[:12]):
            if eo >= len(block):
                continue
            flags, op, arg_u8, arg_u16 = parse_entry_first(block, eo)
            eh = words_hex(block, eo, 12)
            lines.append(
                f"  e{ei:02d} off=0x{eo:04X} flags={flags:04X} op={op:02X} arg8={arg_u8:02X} arg16={arg_u16:04X} words={eh}"
            )
        lines.append("")

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "section_index",
                "section_ptr",
                "entry_index",
                "entry_off",
                "entry_abs_off",
                "flags_u16",
                "op_u8",
                "arg_u8",
                "arg_u16",
                "entry_words",
            ],
        )
        w.writeheader()
        w.writerows(rows)

    out_txt = Path(args.out_txt)
    out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_csv} ({len(rows)} rows)")
    print(f"wrote {out_txt}")


if __name__ == "__main__":
    main()
