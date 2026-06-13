#!/usr/bin/env python3
"""Inspect the non-text payload after Langrisser V battle text blocks.

The script is diagnostic only. It parses the text block, derives the suffix
start, then checks whether the suffix begins with the archive-like table seen
in battle chunks. It also reports narrow structural references that look like
chunk-local pointers into the suffix.
"""
from __future__ import annotations

import argparse
import csv
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

from lang5_scen import find_text_block, read_chunk_spans


def u32(blob: bytes, off: int) -> int:
    return struct.unpack_from("<I", blob, off)[0]


def parse_chunk_list(text: str) -> list[int]:
    out: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return sorted(set(out))


@dataclass
class VmInfo:
    offset: int
    size: int


@dataclass
class SuffixInfo:
    base: int
    suffix_len: int
    payload_size: int
    table_bytes: int
    offsets: list[int]
    unique_offsets: list[int]

    @property
    def used_len(self) -> int:
        # The leading u32 is a size word. Offsets are relative to base+4.
        return 4 + self.payload_size

    @property
    def trailing_len(self) -> int:
        return self.suffix_len - self.used_len


def parse_vm(chunk: bytes, text_base: int) -> VmInfo | None:
    if len(chunk) < 4:
        return None
    off = u32(chunk, 0)
    if not (0 <= off + 0x40 <= len(chunk) and off < text_base):
        return None
    if u32(chunk, off) != 0x44:
        return None
    size = u32(chunk, off + 0x3C)
    if not (0x40 <= size <= len(chunk) - off and off + size <= text_base):
        return None
    return VmInfo(off, size)


def parse_suffix(chunk: bytes, base: int) -> SuffixInfo | None:
    suffix_len = len(chunk) - base
    if suffix_len < 8:
        return None

    payload_size = u32(chunk, base)
    table_bytes = u32(chunk, base + 4)
    if table_bytes < 4 or table_bytes % 4:
        return None
    if 4 + payload_size > suffix_len:
        return None
    if table_bytes > payload_size:
        return None

    table_abs = base + 4
    count = table_bytes // 4
    if table_abs + count * 4 > len(chunk):
        return None
    offsets = [u32(chunk, table_abs + i * 4) for i in range(count)]
    if not offsets or offsets[0] != table_bytes:
        return None
    if any(off < table_bytes or off >= payload_size for off in offsets):
        return None

    unique_offsets = sorted(set(offsets))
    return SuffixInfo(
        base=base,
        suffix_len=suffix_len,
        payload_size=payload_size,
        table_bytes=table_bytes,
        offsets=offsets,
        unique_offsets=unique_offsets,
    )


def structural_regions(chunk: bytes, vm: VmInfo | None, full: bool) -> list[tuple[str, int, int]]:
    if full:
        return [("pre_suffix", 0, len(chunk))]

    regions: list[tuple[str, int, int]] = [("chunk_header", 0, min(0x40, len(chunk)))]
    if vm:
        regions.append(("pre_vm", 0, vm.offset))
        regions.append(("vm_header", vm.offset, min(vm.offset + 0x44, vm.offset + vm.size)))
    return regions


def find_u32_refs(
    chunk: bytes,
    regions: list[tuple[str, int, int]],
    targets: set[int],
) -> list[tuple[str, int, int]]:
    refs: list[tuple[str, int, int]] = []
    for name, start, end in regions:
        start = max(0, start)
        end = min(len(chunk), end)
        for off in range(start, max(start, end - 3), 4):
            val = u32(chunk, off)
            if val in targets:
                refs.append((name, off, val))
    return refs


def row_for_chunk(chunk_idx: int, chunk: bytes, scan_full: bool) -> dict[str, str]:
    block = find_text_block(chunk)
    vm = parse_vm(chunk, block.base)
    suffix_base = block.base + block.size
    suffix = parse_suffix(chunk, suffix_base)

    row: dict[str, str] = {
        "chunk": f"{chunk_idx:03d}",
        "chunk_len": f"0x{len(chunk):X}",
        "text_base": f"0x{block.base:X}",
        "text_size": f"0x{block.size:X}",
        "text_end": f"0x{suffix_base:X}",
        "vm_off": f"0x{vm.offset:X}" if vm else "",
        "vm_size": f"0x{vm.size:X}" if vm else "",
        "suffix_len": f"0x{len(chunk) - suffix_base:X}",
        "archive_payload_size": "",
        "archive_table_bytes": "",
        "archive_entries": "",
        "archive_unique_offsets": "",
        "archive_trailing": "",
        "structural_refs": "",
    }

    if not suffix:
        return row

    target_values = {suffix.base, suffix.base + suffix.used_len}
    # Offsets in the suffix table are relative to suffix_base + 4.
    target_values.update(suffix.base + 4 + off for off in suffix.offsets)
    target_values.update(suffix.offsets)

    refs = find_u32_refs(
        chunk,
        structural_regions(chunk[:suffix_base], vm, scan_full),
        target_values,
    )

    row.update(
        {
            "archive_payload_size": f"0x{suffix.payload_size:X}",
            "archive_table_bytes": f"0x{suffix.table_bytes:X}",
            "archive_entries": str(len(suffix.offsets)),
            "archive_unique_offsets": ",".join(f"0x{o:X}" for o in suffix.unique_offsets),
            "archive_trailing": f"0x{suffix.trailing_len:X}",
            "structural_refs": ";".join(
                f"{name}+0x{off:X}=0x{val:X}" for name, off, val in refs
            ),
        }
    )
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--chunks", default="1-42",
                    help="Chunk list/ranges, e.g. 1-42 or 2,37,42.")
    ap.add_argument("--csv", action="store_true", help="Write CSV instead of a readable table.")
    ap.add_argument("--scan-full", action="store_true",
                    help="Scan the whole pre-suffix area for u32 references. This is noisy.")
    args = ap.parse_args()

    data = Path(args.scen).read_bytes()
    spans = read_chunk_spans(data)
    chunks = parse_chunk_list(args.chunks)

    rows: list[dict[str, str]] = []
    for idx in chunks:
        if idx < 0 or idx >= len(spans):
            print(f"chunk {idx}: outside file span table", file=sys.stderr)
            continue
        start, end = spans[idx]
        try:
            rows.append(row_for_chunk(idx, data[start:end], args.scan_full))
        except Exception as exc:  # keep diagnostics usable across non-battle chunks
            rows.append({"chunk": f"{idx:03d}", "error": str(exc)})

    if args.csv:
        fieldnames = [
            "chunk", "chunk_len", "text_base", "text_size", "text_end",
            "vm_off", "vm_size", "suffix_len", "archive_payload_size",
            "archive_table_bytes", "archive_entries", "archive_unique_offsets",
            "archive_trailing", "structural_refs", "error",
        ]
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        return 0

    for row in rows:
        if "error" in row:
            print(f"{row['chunk']}: ERROR {row['error']}")
            continue
        print(
            f"{row['chunk']}: text_end={row['text_end']} suffix={row['suffix_len']} "
            f"archive={row['archive_payload_size']} table={row['archive_table_bytes']} "
            f"entries={row['archive_entries']} trailing={row['archive_trailing']}"
        )
        if row.get("structural_refs"):
            print(f"  refs: {row['structural_refs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
