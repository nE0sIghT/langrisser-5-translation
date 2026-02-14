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


def read_chunk_pointers(data: bytes) -> List[int]:
    pts: List[int] = []
    for off in range(0, 0x800, 4):
        if off + 4 > len(data):
            break
        v = ru32(data, off)
        if v == 0:
            break
        pts.append(v)
        if len(pts) > 1 and v <= pts[-2]:
            break
        if v == len(data):
            break
    return pts


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


def entry_head_words(block: bytes, off: int, count: int = 12) -> str:
    out: List[str] = []
    end = min(len(block), off + count * 2)
    for p in range(off, end - 1, 2):
        out.append(f"{ru16(block, p):04X}")
    return " ".join(out)


def read_entry_words_until_end(block: bytes, off: int, max_words: int = 256) -> List[int]:
    out: List[int] = []
    p = off
    for _ in range(max_words):
        if p + 2 > len(block):
            break
        w = ru16(block, p)
        out.append(w)
        p += 2
        if w == 0xFFFF:
            break
    return out


def extract_ff00_ids(words: List[int]) -> List[int]:
    ids: List[int] = []
    for i in range(len(words) - 1):
        if words[i] == 0xFF00:
            ids.append(words[i + 1])
    return ids


def scan_one(src: Path, out_dir: Path) -> None:
    data = src.read_bytes()
    pts = read_chunk_pointers(data)
    if len(pts) < 2:
        raise RuntimeError(f"no chunk pointers in {src}")

    rows_blocks = []
    rows_entries = []

    for cidx in range(len(pts) - 1):
        c_start = pts[cidx]
        c_end = pts[cidx + 1]
        chunk = data[c_start:c_end]
        clen = len(chunk)
        if clen < 0x40:
            continue

        d0 = ru32(chunk, 0)
        is_vm = False
        vm_off = d0
        vm_size = 0
        ptr_2c = 0
        ptr_30 = 0
        ptr_34 = 0
        v14 = 0
        main_count = 0
        terminated = 0

        if 0 <= vm_off <= clen - 0x40:
            vm_size = ru32(chunk, vm_off + 0x3C)
            ptr_2c = ru32(chunk, vm_off + 0x2C)
            ptr_30 = ru32(chunk, vm_off + 0x30)
            ptr_34 = ru32(chunk, vm_off + 0x34)
            v14 = ru32(chunk, vm_off + 0x38)
            p0 = ru32(chunk, vm_off + 0x00)
            # Stable VM header signature observed in multiple chunks.
            if p0 == 0x44 and 0x40 <= vm_size <= (clen - vm_off):
                is_vm = True

        if is_vm and ptr_2c < vm_size:
            block = chunk[vm_off:vm_off + vm_size]
            entries, ok = parse_u16_list(block, ptr_2c)
            if ok and entries:
                # filter obvious junk offsets
                entries = [e for e in entries if (e & 1) == 0 and 0x40 <= e < vm_size]
            main_count = len(entries)
            terminated = int(ok)
            for eidx, eoff in enumerate(entries):
                if eoff + 6 > len(block):
                    continue
                flags = ru16(block, eoff)
                op = block[eoff + 2]
                arg8 = block[eoff + 3]
                arg16 = ru16(block, eoff + 4)
                entry_words = read_entry_words_until_end(block, eoff, 256)
                ff00_ids = extract_ff00_ids(entry_words)
                rows_entries.append(
                    {
                        "source_file": src.name,
                        "chunk_index": cidx,
                        "chunk_start": f"0x{c_start:06X}",
                        "vm_off": f"0x{vm_off:04X}",
                        "vm_size": f"0x{vm_size:04X}",
                        "entry_index": eidx,
                        "entry_off": f"0x{eoff:04X}",
                        "entry_abs_off": f"0x{c_start + vm_off + eoff:06X}",
                        "flags_u16": f"{flags:04X}",
                        "op_u8": f"{op:02X}",
                        "arg8_u8": f"{arg8:02X}",
                        "arg16_u16": f"{arg16:04X}",
                        "ff00_count": len(ff00_ids),
                        "ff00_ids": " ".join(f"{x:04X}" for x in ff00_ids[:16]),
                        "head_words": entry_head_words(block, eoff, 12),
                    }
                )

        rows_blocks.append(
            {
                "source_file": src.name,
                "chunk_index": cidx,
                "chunk_start": f"0x{c_start:06X}",
                "chunk_size": f"0x{clen:X}",
                "d0_vm_off": f"0x{d0:08X}",
                "is_vm_header": int(is_vm),
                "vm_size": f"0x{vm_size:X}" if vm_size else "",
                "header_2c": f"0x{ptr_2c:08X}" if is_vm else "",
                "header_30": f"0x{ptr_30:08X}" if is_vm else "",
                "header_34": f"0x{ptr_34:08X}" if is_vm else "",
                "header_38": f"0x{v14:08X}" if is_vm else "",
                "main_list_terminated": terminated if is_vm else "",
                "main_entry_count": main_count if is_vm else "",
            }
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    out_blocks = out_dir / f"{src.stem.lower()}_vm_chunks.csv"
    out_entries = out_dir / f"{src.stem.lower()}_vm_entries.csv"

    with out_blocks.open("w", newline="", encoding="utf-8") as fh:
        cols = list(rows_blocks[0].keys()) if rows_blocks else []
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows_blocks)

    with out_entries.open("w", newline="", encoding="utf-8") as fh:
        cols = list(rows_entries[0].keys()) if rows_entries else [
            "source_file",
            "chunk_index",
            "chunk_start",
            "vm_off",
            "vm_size",
            "entry_index",
            "entry_off",
            "entry_abs_off",
            "flags_u16",
            "op_u8",
            "arg8_u8",
            "arg16_u16",
            "ff00_count",
            "ff00_ids",
            "head_words",
        ]
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows_entries)

    print(f"wrote {out_blocks}")
    print(f"wrote {out_entries}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Scan SCEN container chunks for VM blocks and main entry lists.")
    ap.add_argument("--scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--scen2", default="work/extracted/SCEN2.DAT")
    ap.add_argument("--out-dir", default="work/scen_analysis")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    scan_one(Path(args.scen), out_dir)
    scan_one(Path(args.scen2), out_dir)


if __name__ == "__main__":
    main()
