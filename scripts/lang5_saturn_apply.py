#!/usr/bin/env python3
"""Apply a target-language translation onto the Saturn SCEN.DAT text pool.

This reuses the PS1 translation content and codec unchanged: because the target
alphabet occupies the same font slots on both consoles, a record's encoded token
stream is identical; only the byte order (Saturn on-disc big-endian) and the
container (the field_3c local index table) differ. Each Saturn text entry is
rebuilt in place at fixed size via `saturn_scen.splice_local_index_table`.

Saturn block `c`'s entry `e` corresponds to PS1 chunk `c` record `e+1`. Where a
block's Saturn entry count matches the PS1 record count exactly, the whole block
is applied; blocks with a count delta are left untouched pending mapping
reconciliation (see docs/SATURN_DISC_FORMAT.md). Read-only against the disc: it
reads an extracted SCEN.DAT and writes a new one.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lang5_project import add_language_args, language_from_args
from lang5_scen import Codec, load_charmap_tbl
from lang5_sceninsert import parse_dump_file
from saturn_scen import local_index_entries, parse_catalog, repack_scen


def apply_scen(data: bytes, lang_scen_dir: Path, codec: Codec) -> tuple[bytes, dict]:
    blocks = parse_catalog(data)
    stats = {"blocks": len(blocks), "applied": 0, "skipped_count": 0,
             "entries_written": 0, "missing_dump": 0, "grown_blocks": 0}
    block_entries: dict[int, list[list[int]]] = {}
    for chunk_index, (start, used) in enumerate(blocks):
        entries = local_index_entries(data, start, used)
        if entries is None:
            continue
        dump_path = lang_scen_dir / f"chunk_{chunk_index:03d}.txt"
        if not dump_path.exists():
            stats["missing_dump"] += 1
            continue
        records = parse_dump_file(dump_path)  # {1-based idx: text}
        # Exact 1:1 mapping only: Saturn entry e <-> record e+1.
        if not records or max(records) != len(entries) or len(records) != len(entries):
            stats["skipped_count"] += 1
            continue
        new_entries = [codec.encode(records[e + 1]) for e in range(len(entries))]
        block_entries[chunk_index] = new_entries
        stats["applied"] += 1
        stats["entries_written"] += len(new_entries)

    out = repack_scen(data, block_entries)
    stats["grown_bytes"] = len(out) - len(data)
    return out, stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_language_args(ap)
    ap.add_argument("--scen", default="work/build/saturn/SCEN.DAT")
    ap.add_argument("--out-scen", default="work/build/saturn/SCEN.applied.DAT")
    ap.add_argument("--tbl", default=None, help="charmap .tbl (default: the language's built tbl)")
    args = ap.parse_args()

    lang = language_from_args(args)
    tbl = Path(args.tbl) if args.tbl else lang.tbl
    codec = Codec(load_charmap_tbl(tbl))
    data = Path(args.scen).read_bytes()
    out, stats = apply_scen(data, lang.script_dir, codec)

    out_path = Path(args.out_scen)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(out)
    print(
        f"applied {stats['applied']}/{stats['blocks']} blocks, "
        f"{stats['entries_written']} entries; "
        f"skipped(count-mismatch)={stats['skipped_count']} "
        f"missing-dump={stats['missing_dump']}; "
        f"file grew {stats['grown_bytes']} bytes -> {out_path}"
    )


if __name__ == "__main__":
    main()
