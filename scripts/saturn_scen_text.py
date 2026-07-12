#!/usr/bin/env python3
"""Dump the full Saturn SCEN.DAT scenario text pool in read-only mode.

The scenario text lives in each payload block's ``resource_table.field_3c``
local index table (see docs/SATURN_DISC_FORMAT.md). This tool walks all 131
payload blocks, reads every indexed text entry and emits a stable
``(chunk_index, entry_index)`` record set, mirroring the PS1
``work/scriptdump/all_records.csv`` shape so the two platforms can be aligned.

Decoding uses the PS1 Japanese token table. Kana and control words match the
Saturn stream exactly; a subset of kanji decodes incorrectly because the Saturn
kanji banks are reordered relative to PS1. The raw token ids are always emitted
so downstream alignment does not depend on kanji parity.
"""

from __future__ import annotations

import argparse
import csv
import json
import struct
from pathlib import Path

from lang5_system_dump import load_codemap

TEXT_TERMINATORS = {0xFFFE, 0xFFFF}
SOFT_BREAK = 0xFFFC


def u32be(data: bytes, off: int) -> int:
    return struct.unpack_from(">I", data, off)[0]


def u16be(data: bytes, off: int) -> int:
    return struct.unpack_from(">H", data, off)[0]


def decode_tokens(words: list[int], codemap: dict[int, str]) -> str:
    out: list[str] = []
    for word in words:
        if word in TEXT_TERMINATORS:
            out.append("<$%04X>" % word)
        elif word == SOFT_BREAK:
            out.append("<$FFFC>")
        elif word >= 0xFB00:
            out.append("<$%04X>" % word)
        elif word == 0:
            out.append("")
        else:
            out.append(codemap.get(word, "{?%04X}" % word))
    return "".join(out)


def parse_catalog(data: bytes) -> list[tuple[int, int]]:
    count = u32be(data, 0)
    return [
        (u32be(data, 4 + i * 8) * 0x800, u32be(data, 8 + i * 8))
        for i in range(count)
    ]


def local_index_entries(data: bytes, start: int, used: int) -> list[list[int]] | None:
    """Return the token-word entries of a block's field_3c text table."""
    if used < 0x44:
        return None
    resource_table_offset = u32be(data, start)
    if not (0 <= resource_table_offset <= used - 0x44):
        return None
    table_base = start + resource_table_offset
    field_3c = u32be(data, table_base + 0x3C)
    base = table_base + field_3c
    if base + 6 > len(data):
        return None
    total_size = u32be(data, base)
    if not (4 <= total_size <= used - resource_table_offset - field_3c):
        return None
    first_offset = u16be(data, base + 4)
    if first_offset < 6 or (first_offset - 4) % 2:
        return None
    count = (first_offset - 4) // 2
    offsets = [u16be(data, base + 4 + i * 2) for i in range(count)]
    entries: list[list[int]] = []
    for i, off in enumerate(offsets):
        next_off = offsets[i + 1] if i + 1 < count else total_size
        if not (first_offset <= off <= next_off <= total_size):
            return None
        entries.append([u16be(data, base + off + 2 * j) for j in range((next_off - off) // 2)])
    return entries


def dump(data: bytes, codemap: dict[int, str]) -> dict:
    catalog = parse_catalog(data)
    chunks = []
    records = []
    bad = []
    for chunk_index, (start, used) in enumerate(catalog):
        entries = local_index_entries(data, start, used)
        if entries is None:
            bad.append(chunk_index)
            continue
        text_entries = 0
        for entry_index, words in enumerate(entries):
            is_text = any(word in TEXT_TERMINATORS for word in words)
            if is_text:
                text_entries += 1
            records.append({
                "chunk_index": chunk_index,
                "entry_index": entry_index,
                "word_count": len(words),
                "is_text": is_text,
                "tokens": " ".join("%04X" % word for word in words),
                "jp": decode_tokens(words, codemap),
            })
        chunks.append({"chunk_index": chunk_index, "entry_count": len(entries),
                       "text_entries": text_entries})
    return {
        "file_size": len(data),
        "chunk_count": len(catalog),
        "parsed_chunks": len(chunks),
        "bad_chunks": bad,
        "entry_count": len(records),
        "text_entry_count": sum(1 for r in records if r["is_text"]),
        "chunks": chunks,
        "records": records,
    }


def write_csv(result: dict, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["chunk_index", "entry_index", "word_count", "is_text", "jp"])
        for rec in result["records"]:
            writer.writerow([rec["chunk_index"], rec["entry_index"],
                             rec["word_count"], int(rec["is_text"]), rec["jp"]])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scen", default="work/build/saturn/SCEN.DAT")
    ap.add_argument("--tbl", default="data/common/tables/lang5_jp.tbl")
    ap.add_argument("--out", default="work/build/saturn/scen_text.json")
    ap.add_argument("--out-csv", default="work/build/saturn/scen_text.csv")
    args = ap.parse_args()

    data = Path(args.scen).read_bytes()
    codemap = load_codemap(args.tbl)
    result = dump(data, codemap)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.out_csv:
        write_csv(result, Path(args.out_csv))
    print(
        f"parsed {result['parsed_chunks']}/{result['chunk_count']} chunks, "
        f"{result['entry_count']} entries "
        f"({result['text_entry_count']} text) -> {out}"
    )
    if result["bad_chunks"]:
        print(f"unparsed chunks: {result['bad_chunks']}")


if __name__ == "__main__":
    main()
