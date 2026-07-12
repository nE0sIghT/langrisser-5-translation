#!/usr/bin/env python3
"""Dump Saturn SYSTEM.DAT string groups in read-only mode."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from lang5_system_dump import load_codemap


FFFF = 0xFFFF
SOFT_BREAK = 0xFFFC
MAX_STEP = 0x30
MIN_ENTRIES = 8
MAX_PREAMBLE = 16


def u16(data: bytes, off: int, endian: str) -> int:
    return struct.unpack_from(">H" if endian == "be" else "<H", data, off)[0]


def unpack_words(data: bytes, off: int, count: int, endian: str) -> list[int]:
    fmt = (">" if endian == "be" else "<") + f"{count}H"
    return list(struct.unpack_from(fmt, data, off)) if count else []


def decode_run(words: list[int], codemap: dict[int, str]) -> str:
    out: list[str] = []
    for word in words:
        if word == SOFT_BREAK:
            out.append("\\n")
        elif word >= 0xFB00 or word == 0:
            out.append("" if word == 0 else f"{{{word:04X}}}")
        else:
            out.append(codemap.get(word, f"{{?{word:04X}}}"))
    return "".join(out)


def read_table(data: bytes, pos: int, endian: str) -> list[int] | None:
    if pos + 2 > len(data) or u16(data, pos, endian) != 0:
        return None
    vals = [0]
    prev = 0
    i = pos + 2
    while i + 2 <= len(data):
        value = u16(data, i, endian)
        if prev < value <= prev + MAX_STEP:
            vals.append(value)
            prev = value
            i += 2
        else:
            break
    return vals if len(vals) >= MIN_ENTRIES else None


def run_length(data: bytes, off: int, endian: str) -> int:
    n = 0
    while off + 2 * n + 2 <= len(data) and u16(data, off + 2 * n, endian) != FFFF:
        n += 1
    return n


def base_for(data: bytes, pos: int, table: list[int], endian: str) -> int | None:
    table_end = pos + len(table) * 2
    for preamble_words in range(MAX_PREAMBLE + 1):
        base = table_end + preamble_words * 2
        ok = True
        for k in range(1, len(table)):
            term = base + (table[k] - 1) * 2
            if term + 2 > len(data) or u16(data, term, endian) != FFFF:
                ok = False
                break
        if ok:
            return base
    return None


def group_at(data: bytes, pos: int, endian: str) -> tuple[list[int], int] | None:
    table = read_table(data, pos, endian)
    if table is None:
        return None
    for count in range(len(table), MIN_ENTRIES - 1, -1):
        sub = table[:count]
        base = base_for(data, pos, sub, endian)
        if base is not None:
            return sub, base
    return None


def find_groups(data: bytes, scan_start: int, endian: str) -> list[tuple[int, list[int], int]]:
    groups: list[tuple[int, list[int], int]] = []
    pos = scan_start
    while pos + 2 <= len(data):
        found = group_at(data, pos, endian)
        if found is None:
            pos += 2
            continue
        table, base = found
        last_off = base + table[-1] * 2
        end = last_off + (run_length(data, last_off, endian) + 1) * 2
        groups.append((pos, table, base))
        pos = end
    return groups


def dump_system(data: bytes, codemap: dict[int, str], scan_start: int, endian: str) -> dict:
    groups = find_groups(data, scan_start, endian)
    entries = []
    for group_index, (table_off, table, base) in enumerate(groups):
        for index in range(len(table)):
            off = base + table[index] * 2
            if index + 1 < len(table):
                word_count = table[index + 1] - table[index] - 1
            else:
                word_count = run_length(data, off, endian)
            words = unpack_words(data, off, word_count, endian)
            entries.append({
                "id": f"table:{table_off:05X}:{index}",
                "group": group_index,
                "table": f"0x{table_off:05X}",
                "index": index,
                "offset": f"0x{off:05X}",
                "words": word_count,
                "leading_cells": next((i for i, word in enumerate(words) if word != 0), len(words)),
                "jp": decode_run(words, codemap),
            })
    return {
        "endian": endian,
        "scan_start": f"0x{scan_start:05X}",
        "group_count": len(groups),
        "string_count": len(entries),
        "groups": [
            {
                "group": i,
                "table": f"0x{table_off:05X}",
                "entries": len(table),
                "base": f"0x{base:05X}",
                "end": f"0x{base + table[-1] * 2 + (run_length(data, base + table[-1] * 2, endian) + 1) * 2:05X}",
            }
            for i, (table_off, table, base) in enumerate(groups)
        ],
        "entries": entries,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--system", default="work/build/saturn/SYSTEM.DAT")
    ap.add_argument("--tbl", default="data/common/tables/lang5_jp.tbl")
    ap.add_argument("--out", default="work/build/saturn/system_strings.json")
    ap.add_argument("--scan-start", type=lambda value: int(value, 0), default=0x7000)
    ap.add_argument("--endian", choices=("be", "le"), default="be")
    args = ap.parse_args()

    data = Path(args.system).read_bytes()
    codemap = load_codemap(args.tbl)
    dumped = dump_system(data, codemap, args.scan_start, args.endian)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dumped, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"dumped {dumped['string_count']} strings from {dumped['group_count']} "
        f"groups -> {out}"
    )


if __name__ == "__main__":
    main()
