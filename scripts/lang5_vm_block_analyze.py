#!/usr/bin/env python3
import argparse
import csv
import json
import struct
from pathlib import Path
from typing import Dict, List, Set, Tuple


def ru16(b: bytes, off: int) -> int:
    return struct.unpack_from("<H", b, off)[0]


def ru32(b: bytes, off: int) -> int:
    return struct.unpack_from("<I", b, off)[0]


def parse_u16_list(block: bytes, off: int, max_items: int = 2048) -> Tuple[List[int], bool]:
    vals: List[int] = []
    p = off
    for _ in range(max_items):
        if p + 2 > len(block):
            return (vals, False)
        v = ru16(block, p)
        p += 2
        if v == 0xFFFF:
            return (vals, True)
        vals.append(v)
    return (vals, False)


def list_quality(block: bytes, vals: List[int]) -> Tuple[float, float]:
    if not vals:
        return (0.0, 0.0)
    in_range = sum(1 for v in vals if v < len(block))
    even = sum(1 for v in vals if (v & 1) == 0)
    return (in_range / len(vals), even / len(vals))


def entry_words(block: bytes, off: int, max_words: int = 64) -> List[int]:
    out: List[int] = []
    p = off
    while p + 2 <= len(block) and len(out) < max_words:
        w = ru16(block, p)
        out.append(w)
        p += 2
        if w == 0xFFFF:
            break
    return out


def detect_markers(words: List[int]) -> str:
    marks = []
    for m in (0x0122, 0x011E, 0x010C, 0x010B, 0x010D, 0x010F, 0x016A, 0x026A, 0xFF00, 0xFF0B, 0xFFFF):
        if m in words:
            marks.append(f"{m:04X}")
    return " ".join(marks)


def main() -> None:
    ap = argparse.ArgumentParser(description="Analyze one Langrisser V VM block and emit normalized structure tables.")
    ap.add_argument("--bin", default="work/extracted/SCEN.DAT")
    ap.add_argument("--base-off", type=lambda x: int(x, 0), default=0x840)
    ap.add_argument("--block-size", type=lambda x: int(x, 0), default=0x1AB4)
    ap.add_argument("--header-ptrs", type=int, default=16, help="Number of dwords to read at block head as candidate pointers.")
    ap.add_argument("--min-entry-off", type=lambda x: int(x, 0), default=0x40)
    ap.add_argument("--out-dir", default="work/scen_analysis")
    args = ap.parse_args()

    data = Path(args.bin).read_bytes()
    block = data[args.base_off : args.base_off + args.block_size]
    if len(block) < args.block_size:
        raise RuntimeError("block shorter than requested size")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # candidate pointer dwords from block head
    ptr_rows = []
    ptrs: List[int] = []
    for i in range(args.header_ptrs):
        off = i * 4
        v = ru32(block, off)
        ptrs.append(v)
        ptr_rows.append(
            {
                "ptr_index": i,
                "ptr_off": f"0x{off:04X}",
                "ptr_value": f"0x{v:08X}",
                "in_block": int(v < len(block)),
            }
        )

    # parse each in-range pointer as potential u16 list
    list_rows = []
    accepted_ptrs: Set[int] = set()
    entry_offsets: Set[int] = set()
    header_end = args.header_ptrs * 4
    for i, v in enumerate(ptrs):
        if v >= len(block):
            continue
        vals, terminated = parse_u16_list(block, v)
        if not vals:
            list_rows.append(
                {
                    "ptr_index": i,
                    "list_ptr": f"0x{v:04X}",
                    "entry_count": 0,
                    "terminated": int(terminated),
                    "in_range_ratio": "",
                    "even_ratio": "",
                    "accepted": 0,
                    "min_entry": "",
                    "max_entry": "",
                    "first_entries": "",
                }
            )
            continue
        q_in, q_even = list_quality(block, vals)
        min_v = min(vals)
        max_v = max(vals)
        looks_like_entries = min_v >= args.min_entry_off and max_v < len(block)
        if v < header_end and min_v < header_end:
            looks_like_entries = False
        accepted = int(terminated and len(vals) >= 1 and q_in >= 1.0 and q_even >= 1.0 and looks_like_entries)
        if accepted:
            accepted_ptrs.add(i)
            for e in vals:
                if e < len(block):
                    entry_offsets.add(e)
        list_rows.append(
                {
                    "ptr_index": i,
                    "list_ptr": f"0x{v:04X}",
                    "entry_count": len(vals),
                    "terminated": int(terminated),
                    "in_range_ratio": f"{q_in:.3f}",
                    "even_ratio": f"{q_even:.3f}",
                    "accepted": accepted,
                "min_entry": f"0x{min(vals):04X}",
                "max_entry": f"0x{max(vals):04X}",
                "first_entries": " ".join(f"{x:04X}" for x in vals[:16]),
            }
        )

    # entry table
    entry_rows = []
    for eo in sorted(entry_offsets):
        w = entry_words(block, eo, max_words=96)
        if len(w) < 2:
            continue
        w0 = w[0]
        w1 = w[1]
        op = w1 & 0x00FF
        arg8 = (w1 >> 8) & 0xFF
        arg16 = w[2] if len(w) > 2 else 0
        entry_rows.append(
            {
                "entry_off": f"0x{eo:04X}",
                "entry_abs_off": f"0x{args.base_off + eo:06X}",
                "w0": f"{w0:04X}",
                "w1": f"{w1:04X}",
                "op_u8": f"{op:02X}",
                "arg8_u8": f"{arg8:02X}",
                "arg16_u16": f"{arg16:04X}",
                "dispatch_main_0_8": int(op < 9),
                "word_count_scanned": len(w),
                "markers": detect_markers(w),
                "head_words": " ".join(f"{x:04X}" for x in w[:20]),
            }
        )

    # quick histogram for op codes
    hist: Dict[int, int] = {}
    for r in entry_rows:
        op = int(r["op_u8"], 16)
        hist[op] = hist.get(op, 0) + 1

    out_ptrs = out_dir / "vm_block_ptrs.csv"
    out_lists = out_dir / "vm_block_lists.csv"
    out_entries = out_dir / "vm_block_entries.csv"
    out_json = out_dir / "vm_block_summary.json"

    for p, rows, cols in (
        (out_ptrs, ptr_rows, ["ptr_index", "ptr_off", "ptr_value", "in_block"]),
        (
            out_lists,
            list_rows,
            [
                "ptr_index",
                "list_ptr",
                "entry_count",
                "terminated",
                "in_range_ratio",
                "even_ratio",
                "accepted",
                "min_entry",
                "max_entry",
                "first_entries",
            ],
        ),
        (
            out_entries,
            entry_rows,
            [
                "entry_off",
                "entry_abs_off",
                "w0",
                "w1",
                "op_u8",
                "arg8_u8",
                "arg16_u16",
                "dispatch_main_0_8",
                "word_count_scanned",
                "markers",
                "head_words",
            ],
        ),
    ):
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)

    summary = {
        "source_bin": args.bin,
        "base_off_hex": hex(args.base_off),
        "block_size_hex": hex(args.block_size),
        "pointer_count": len(ptr_rows),
        "accepted_pointer_indices": sorted(accepted_ptrs),
        "nonempty_lists": sum(1 for r in list_rows if r["entry_count"]),
        "unique_entries": len(entry_rows),
        "op_histogram": {f"{k:02X}": v for k, v in sorted(hist.items())},
    }
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {out_ptrs}")
    print(f"wrote {out_lists}")
    print(f"wrote {out_entries}")
    print(f"wrote {out_json}")


if __name__ == "__main__":
    main()
