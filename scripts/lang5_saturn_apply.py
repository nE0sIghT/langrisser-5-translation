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
from lang5_scen import Codec, find_text_block, load_charmap_tbl, read_chunk_spans, words_from_bytes
from lang5_sceninsert import parse_dump_file
from saturn_scen import local_index_entries, parse_catalog, repack_scen


def _speaker(tokens: list[int]) -> int | None:
    """First `FB00` speaker argument in a token stream, or None."""
    for i, token in enumerate(tokens):
        if token == 0xFB00 and i + 1 < len(tokens):
            return tokens[i + 1]
    return None


def align_prefix(entries: list[list[int]], records: dict[int, str],
                 codec: Codec) -> list[list[int]] | None:
    """Map Saturn entry `e` to PS1 record `e+1`, verified by speaker tokens.

    Returns the encoded entry list if every Saturn entry lines up with a record
    carrying the same `FB00` speaker (so exact-count and trailing-extra-record
    blocks map safely), or None if the sequences diverge (interspersed
    insertions/merges that need real alignment).
    """
    if len(records) < len(entries):
        return None
    encoded: list[list[int]] = []
    for e, entry in enumerate(entries):
        text = records.get(e + 1)
        if text is None:
            return None
        tokens = codec.encode(text)
        if _speaker(entry) != _speaker(tokens):
            return None
        encoded.append(tokens)
    return encoded


def stable_signature(tokens: list[int]) -> tuple[int, ...]:
    """Return the PS1/Saturn-stable part of a JP token stream.

    Kana, ASCII/punctuation and control words are shared between platforms.
    The high kanji bank is reordered on Saturn, so it must not participate in
    automated alignment. Control arguments are kept because speaker ids and
    name macros are alignment-critical.
    """
    out: list[int] = []
    prev: int | None = None
    for token in tokens:
        keep = token < 0x0185 or token >= 0xE000
        if prev == 0xF600 or (prev is not None and 0xFB00 <= prev <= 0xFBFF):
            keep = True
        if keep:
            out.append(token)
        prev = token
    return tuple(out)


def ps1_chunk_records(ps1_scen: bytes, chunk_index: int) -> list[list[int]]:
    start, end = read_chunk_spans(ps1_scen)[chunk_index]
    block = find_text_block(ps1_scen[start:end])
    out: list[list[int]] = []
    for idx in range(1, block.record_count + 1):
        a, b = block.record_span(idx)
        out.append(words_from_bytes(ps1_scen[start + a:start + b]))
    return out


def count_exact_alignments(sat_sigs: list[tuple[int, ...]],
                           ps_sigs: list[tuple[int, ...]]) -> int:
    """Count exact subsequence alignments, capped at 2."""
    from functools import lru_cache

    @lru_cache(None)
    def walk(i: int, j: int) -> int:
        if i == len(sat_sigs):
            return 1
        total = 0
        for k in range(j, len(ps_sigs)):
            if ps_sigs[k] == sat_sigs[i]:
                total += walk(i + 1, k + 1)
                if total >= 2:
                    return total
        return total

    return walk(0, 0)


def exact_signature_map(entries: list[list[int]], ps1_tokens: list[list[int]]) -> list[int] | None:
    sat_sigs = [stable_signature(entry) for entry in entries]
    ps_sigs = [stable_signature(entry) for entry in ps1_tokens]
    if count_exact_alignments(sat_sigs, ps_sigs) != 1:
        return None
    mapping: list[int] = []
    j = 0
    for sig in sat_sigs:
        while j < len(ps_sigs) and ps_sigs[j] != sig:
            j += 1
        if j >= len(ps_sigs):
            return None
        mapping.append(j + 1)  # PS1 SCEN records are 1-based in dump files.
        j += 1
    return mapping


def align_by_signature(entries: list[list[int]], records: dict[int, str],
                       codec: Codec, ps1_tokens: list[list[int]]) -> list[list[int]] | None:
    mapping = exact_signature_map(entries, ps1_tokens)
    if mapping is None:
        return None
    encoded: list[list[int]] = []
    for record_index in mapping:
        text = records.get(record_index)
        if text is None:
            return None
        encoded.append(codec.encode(text))
    return encoded


def apply_scen(data: bytes, lang_scen_dir: Path, codec: Codec,
               ps1_scen: bytes | None = None) -> tuple[bytes, dict]:
    blocks = parse_catalog(data)
    stats = {"blocks": len(blocks), "applied": 0, "skipped_misaligned": 0,
             "entries_written": 0, "missing_dump": 0, "signature_aligned": 0}
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
        new_entries = align_prefix(entries, records, codec)
        if new_entries is None:
            if ps1_scen is not None:
                new_entries = align_by_signature(
                    entries, records, codec, ps1_chunk_records(ps1_scen, chunk_index)
                )
                if new_entries is not None:
                    stats["signature_aligned"] += 1
            if new_entries is None:
                stats["skipped_misaligned"] += 1
                continue
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
    ap.add_argument("--ps1-scen", default="work/extracted/SCEN.DAT",
                    help="PS1 SCEN.DAT used only for exact stable-token alignment")
    args = ap.parse_args()

    lang = language_from_args(args)
    tbl = Path(args.tbl) if args.tbl else lang.tbl
    codec = Codec(load_charmap_tbl(tbl))
    data = Path(args.scen).read_bytes()
    ps1_scen = Path(args.ps1_scen).read_bytes() if args.ps1_scen else None
    out, stats = apply_scen(data, lang.script_dir, codec, ps1_scen)

    out_path = Path(args.out_scen)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(out)
    print(
        f"applied {stats['applied']}/{stats['blocks']} blocks, "
        f"{stats['entries_written']} entries; "
        f"signature-aligned={stats['signature_aligned']} "
        f"skipped(misaligned)={stats['skipped_misaligned']} "
        f"missing-dump={stats['missing_dump']}; "
        f"file grew {stats['grown_bytes']} bytes -> {out_path}"
    )


if __name__ == "__main__":
    main()
