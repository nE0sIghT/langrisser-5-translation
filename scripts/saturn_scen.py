#!/usr/bin/env python3
"""Shared read model for the Saturn SCEN.DAT container.

`SCEN.DAT` is a top-level catalog of 131 payload blocks; each block has a fixed
0x30-byte header of section offsets, and its scenario text lives in the
`resource_table.field_3c` local index table. This module holds the parsing that
both `saturn_scen_scan.py` (structural diagnostics) and `saturn_scen_text.py`
(text dump) need, so neither reimplements it. All multi-byte fields use the
Saturn on-disc big-endian order by default. See docs/SATURN_DISC_FORMAT.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from lang5_binfmt import BE, ByteOrder

SECTOR = 0x800
TEXT_TERMINATORS = {0xFFFE, 0xFFFF}


def parse_catalog(data: bytes, order: ByteOrder = BE) -> list[tuple[int, int]]:
    """Return `(start_offset, used_size)` for every payload block.

    The catalog is `u32 count` followed by `count` `(start_sector, used_size)`
    pairs; `start_sector` is in 0x800-byte units relative to the file.
    """
    count = order.u32(data, 0)
    if not (0 < count < 0x10000 and 4 + count * 8 <= len(data)):
        return []
    return [
        (order.u32(data, 4 + i * 8) * SECTOR, order.u32(data, 8 + i * 8))
        for i in range(count)
    ]


@dataclass(frozen=True)
class BlockHeader:
    resource_table_offset: int
    category: int
    sub_id: int
    section0_offset: int
    section1_offset: int
    record_index_offset: int
    resource_map_offset: int
    fields: tuple[int, ...]  # field_18..field_2c


def parse_block_header(data: bytes, start: int, used: int, order: ByteOrder = BE) -> BlockHeader | None:
    """Parse the fixed 0x30-byte block header, or None if it is out of range."""
    if used < 0x30 or start + 0x30 > len(data):
        return None
    return BlockHeader(
        resource_table_offset=order.u32(data, start + 0x00),
        category=order.u16(data, start + 0x04),
        sub_id=order.u16(data, start + 0x06),
        section0_offset=order.u32(data, start + 0x08),
        section1_offset=order.u32(data, start + 0x0C),
        record_index_offset=order.u32(data, start + 0x10),
        resource_map_offset=order.u32(data, start + 0x14),
        fields=tuple(order.u32(data, start + off) for off in range(0x18, 0x30, 4)),
    )


def local_index_layout(data: bytes, start: int, used: int, order: ByteOrder = BE) -> tuple[int, int, list[int]] | None:
    """Return `(base, total_size, offsets)` of the field_3c local index table.

    The table is the scenario text pool: `u32 total_size`, then `u16` entry
    offsets (count derived from the first offset), then the entry payloads.
    Returns None if the structure does not validate.
    """
    if used < 0x44:
        return None
    resource_table_offset = order.u32(data, start)
    if not (0 <= resource_table_offset <= used - 0x44):
        return None
    table_base = start + resource_table_offset
    field_3c = order.u32(data, table_base + 0x3C)
    base = table_base + field_3c
    if base + 6 > len(data):
        return None
    total_size = order.u32(data, base)
    if not (4 <= total_size <= used - resource_table_offset - field_3c):
        return None
    first_offset = order.u16(data, base + 4)
    if first_offset < 6 or (first_offset - 4) % 2:
        return None
    count = (first_offset - 4) // 2
    offsets = [order.u16(data, base + 4 + i * 2) for i in range(count)]
    for i, off in enumerate(offsets):
        next_off = offsets[i + 1] if i + 1 < count else total_size
        if not (first_offset <= off <= next_off <= total_size):
            return None
    return base, total_size, offsets


def local_index_entries(data: bytes, start: int, used: int, order: ByteOrder = BE) -> list[list[int]] | None:
    """Return the token-word entries of a block's field_3c text table, or None."""
    layout = local_index_layout(data, start, used, order)
    if layout is None:
        return None
    base, total_size, offsets = layout
    entries: list[list[int]] = []
    for i, off in enumerate(offsets):
        next_off = offsets[i + 1] if i + 1 < len(offsets) else total_size
        entries.append([order.u16(data, base + off + 2 * j) for j in range((next_off - off) // 2)])
    return entries
