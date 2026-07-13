#!/usr/bin/env python3
"""Pack the universal SYSTEM translation into the Saturn SYSTEM.DAT groups.

Saturn `SYSTEM.DAT` uses the same offset-table group model as PS1, and its 16
groups correspond 1:1 to the PS1 `SYSTEM.BIN` groups in order. This reuses the
shared `lang5_offsetgroups` model with the Saturn BE config and the PS1 codec to
rebuild each group's `[u16 offset table][strings]` in place with the translated
text, mapping Saturn group `g` index `i` to the PS1 group `g` index `i` where
that mapping is structurally proven.

Fixed-size per group: the group stays at its base and within its original byte
budget, so nothing that points at it moves. A group whose rebuild would exceed
the budget is left untranslated (reported), never truncated. Identical strings
share one blob slot, matching the PS1 `--repack` behavior.
See docs/SATURN_DISC_FORMAT.md.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from lang5_binfmt import BE
from lang5_offsetgroups import PS1, SATURN, find_groups, run_length
from lang5_scen import Codec, load_charmap_tbl

FFFF = 0xFFFF
NAME_GRID_FIRST = 213
NAME_GRID_COUNT = 19
NAME_GRID_RUN_WORDS = 6  # five glyphs plus the FFFF separator
VOICE_ACTOR_FIRST = 257
VOICE_ACTOR_LAST = 289


def group_end_offset(data: bytes, table: list[int], base: int, cfg) -> int:
    last_off = base + table[-1] * 2
    return last_off + (run_length(data, last_off, cfg) + 1) * 2


def dedup_blob(seqs: list[list[int]]) -> tuple[list[int], list[int]]:
    """Return (offsets, blob) with identical strings sharing one blob slot."""
    offsets: list[int] = []
    blob: list[int] = []
    slot_by_seq: dict[tuple[int, ...], int] = {}
    for seq in seqs:
        key = tuple(seq)
        slot = slot_by_seq.get(key)
        if slot is None:
            slot = len(blob)
            slot_by_seq[key] = slot
            blob.extend(seq)
            blob.append(FFFF)
        offsets.append(slot)
    return offsets, blob


def build_group_blob(seqs: list[list[int]]) -> list[int]:
    """Rebuild [u16 offset table][FFFF-terminated strings] as a word list.

    `offset[k]` is the word offset of string `k` from the string base (which is
    `n` words after the table start); string `k` is its words plus an `FFFF`.
    """
    offsets, blob = dedup_blob(seqs)
    return offsets + blob


def build_group0_blob(data: bytes, table: list[int], base: int, group_end: int,
                      seqs: list[list[int]]) -> list[int] | None:
    """Rebuild Saturn group 0 while preserving the name-entry grid address.

    Saturn group 0 includes the 19 visible name-entry alphabet rows. Static
    tracing has not proven whether the screen reads those rows only through the
    offset table or also by their loaded address, so keep the original row bytes
    at the original physical offset and pack translated strings on both sides.
    `saturn_name_entry.py` rewrites those fixed rows after this pack step.
    """
    after_grid = NAME_GRID_FIRST + NAME_GRID_COUNT
    if len(table) <= after_grid:
        return None
    grid_start = base + table[NAME_GRID_FIRST] * 2
    grid_end = base + table[after_grid] * 2
    if grid_end - grid_start != NAME_GRID_COUNT * NAME_GRID_RUN_WORDS * 2:
        return None
    for i in range(NAME_GRID_COUNT):
        k = NAME_GRID_FIRST + i
        if table[k] != table[NAME_GRID_FIRST] + i * NAME_GRID_RUN_WORDS:
            return None
        off = base + table[k] * 2
        if run_length(data, off, SATURN) != NAME_GRID_RUN_WORDS - 1:
            return None

    prefix_offsets, prefix_blob = dedup_blob(seqs[:NAME_GRID_FIRST])
    prefix_capacity = (grid_start - base) // 2
    if len(prefix_blob) > prefix_capacity:
        return None

    suffix_offsets, suffix_blob = dedup_blob(seqs[after_grid:])
    suffix_start = (grid_end - base) // 2
    suffix_capacity = (group_end - grid_end) // 2
    if len(suffix_blob) > suffix_capacity:
        return None

    string_area_words = (group_end - base) // 2
    string_area = [FFFF] * string_area_words
    string_area[:len(prefix_blob)] = prefix_blob
    grid_words = BE.words(data, grid_start, (grid_end - grid_start) // 2)
    grid_offset = table[NAME_GRID_FIRST]
    string_area[grid_offset:grid_offset + len(grid_words)] = grid_words
    string_area[suffix_start:suffix_start + len(suffix_blob)] = suffix_blob

    return (
        prefix_offsets
        + table[NAME_GRID_FIRST:after_grid]
        + [suffix_start + offset for offset in suffix_offsets]
        + string_area
    )


def can_map_group(gi: int, sat_count: int, ps1_count: int) -> bool:
    """Return whether Saturn group entries can use PS1 translations by index.

    Most groups are safe only with identical counts. Group 0 is a verified
    exception: Saturn keeps the 19-row name-entry grid inside the group, while
    the PS1 SYSTEM dump deliberately excludes that grid. The surrounding entries
    keep their physical indices, and `saturn_name_entry.py` rewrites the grid
    afterwards from `name_entry_grid.json`.
    """
    return sat_count == ps1_count or gi == 0


def compact_voice_actor_initial(text: str) -> str:
    """Save one cell in Saturn's fixed group-0 tail without changing meaning."""
    return re.sub(r"^([^\W\d_])\. +", r"\1.", text, count=1, flags=re.UNICODE)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--system-in", default="work/build/saturn/SYSTEM.DAT.ru.font")
    ap.add_argument("--system-out", default="work/build/saturn/SYSTEM.ru.DAT")
    ap.add_argument("--ps1-system", default="work/extracted/SYSTEM.BIN")
    ap.add_argument("--strings", default="work/build/system_strings.ru.json")
    ap.add_argument("--tbl", default="work/build/saturn/lang5_ru.saturn.tbl")
    args = ap.parse_args()

    codec = Codec(load_charmap_tbl(Path(args.tbl)))
    data = bytearray(Path(args.system_in).read_bytes())
    ps1_data = Path(args.ps1_system).read_bytes()
    sat_groups = find_groups(data, SATURN)
    ps1_groups = find_groups(ps1_data, PS1)
    translations = json.loads(Path(args.strings).read_text(encoding="utf-8"))

    changed = 0
    skipped_groups = 0
    mapped_groups = 0
    compacted_actor_names = 0
    preserved_actor_names = 0
    for gi, (table_off, table, base) in enumerate(sat_groups):
        n = len(table)
        if base != table_off + n * 2:
            continue  # group keeps a preamble between table and strings: skip
        group_end = group_end_offset(data, table, base, SATURN)
        budget = (group_end - table_off) // 2   # offset table + strings, in words
        if gi >= len(ps1_groups) or not can_map_group(gi, n, len(ps1_groups[gi][1])):
            continue  # unaligned group: leave untranslated
        mapped_groups += 1
        ps1_table_off = ps1_groups[gi][0]
        seqs: list[list[int]] = []
        origs: list[list[int]] = []
        texts: dict[int, str] = {}
        for k in range(n):
            off = base + table[k] * 2
            orig_len = table[k + 1] - table[k] - 1 if k + 1 < n else run_length(data, off, SATURN)
            orig = SATURN.order.words(data, off, orig_len)
            origs.append(orig)
            text = translations.get(f"table:{ps1_table_off:05X}:{k}")
            if not text or text == "{BLANK}":
                seqs.append([] if text == "{BLANK}" else orig)
                continue
            try:
                clean = text.rstrip()
                texts[k] = clean
                seqs.append(codec.encode(clean))
            except Exception:
                seqs.append(orig)
        if gi == 0 and n != len(ps1_groups[gi][1]):
            blob = build_group0_blob(data, table, base, group_end, seqs)
            if blob is None:
                compacted = list(seqs)
                local_compacted = 0
                for k in range(VOICE_ACTOR_FIRST, min(VOICE_ACTOR_LAST + 1, n)):
                    text = texts.get(k)
                    if not text:
                        continue
                    shorter = compact_voice_actor_initial(text)
                    if shorter == text:
                        continue
                    try:
                        compacted[k] = codec.encode(shorter)
                    except Exception:
                        continue
                    local_compacted += 1
                blob = build_group0_blob(data, table, base, group_end, compacted)
                if blob is not None:
                    compacted_actor_names += local_compacted
                    seqs = compacted
            if blob is None:
                preserved = list(seqs)
                local_preserved = 0
                for k in range(VOICE_ACTOR_FIRST, min(VOICE_ACTOR_LAST + 1, n)):
                    if texts.get(k) is None:
                        continue
                    preserved[k] = origs[k]
                    local_preserved += 1
                blob = build_group0_blob(data, table, base, group_end, preserved)
                if blob is not None:
                    preserved_actor_names += local_preserved
                    seqs = preserved
            if blob is None:
                continue
        else:
            blob = build_group_blob(seqs)
        if len(blob) > budget:
            skipped_groups += 1
            continue
        blob += [FFFF] * (budget - len(blob))  # pad the fixed group span
        for i, word in enumerate(blob):
            data[table_off + i * 2:table_off + i * 2 + 2] = BE.pack_u16(word)
        changed += 1

    out = Path(args.system_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(bytes(data))
    print(f"packed {changed}/{len(sat_groups)} SYSTEM groups "
          f"(mapped={mapped_groups} skipped-over-budget={skipped_groups} "
          f"compacted-actor-names={compacted_actor_names} "
          f"preserved-actor-names={preserved_actor_names}) -> {out}")


if __name__ == "__main__":
    main()
