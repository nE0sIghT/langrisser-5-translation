#!/usr/bin/env python3
"""Pack the universal SYSTEM translation into the Saturn SYSTEM.DAT groups.

Saturn `SYSTEM.DAT` uses the same offset-table group model as PS1, and its 16
groups correspond 1:1 to the PS1 `SYSTEM.BIN` groups in order (14/16 with
identical entry counts). This reuses the shared `lang5_offsetgroups` model with
the Saturn BE config and the PS1 codec to rebuild each group's
`[u16 offset table][strings]` in place with the translated text, mapping Saturn
group `g` index `i` to the PS1 group `g` index `i`.

Fixed-size per group: the group stays at its base and within its original byte
budget, so nothing that points at it moves. A group whose rebuild would exceed
the budget is left untranslated (reported), never truncated.
See docs/SATURN_DISC_FORMAT.md.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lang5_binfmt import BE
from lang5_offsetgroups import PS1, SATURN, find_groups, run_length
from lang5_scen import Codec, load_charmap_tbl

FFFF = 0xFFFF


def group_end_offset(data: bytes, table: list[int], base: int, cfg) -> int:
    last_off = base + table[-1] * 2
    return last_off + (run_length(data, last_off, cfg) + 1) * 2


def build_group_blob(seqs: list[list[int]]) -> list[int]:
    """Rebuild [u16 offset table][FFFF-terminated strings] as a word list.

    `offset[k]` is the word offset of string `k` from the string base (which is
    `n` words after the table start); string `k` is its words plus an `FFFF`.
    """
    offsets: list[int] = []
    strings: list[int] = []
    pos = 0
    for seq in seqs:
        offsets.append(pos)
        strings.extend(seq)
        strings.append(FFFF)
        pos += len(seq) + 1
    return offsets + strings


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
    for gi, (table_off, table, base) in enumerate(sat_groups):
        n = len(table)
        if base != table_off + n * 2:
            continue  # group keeps a preamble between table and strings: skip
        group_end = group_end_offset(data, table, base, SATURN)
        budget = (group_end - table_off) // 2   # offset table + strings, in words
        if gi >= len(ps1_groups) or len(ps1_groups[gi][1]) != n:
            continue  # unaligned group: leave untranslated
        ps1_table_off = ps1_groups[gi][0]
        seqs: list[list[int]] = []
        for k in range(n):
            off = base + table[k] * 2
            orig_len = table[k + 1] - table[k] - 1 if k + 1 < n else run_length(data, off, SATURN)
            orig = SATURN.order.words(data, off, orig_len)
            text = translations.get(f"table:{ps1_table_off:05X}:{k}")
            if not text or text == "{BLANK}":
                seqs.append([] if text == "{BLANK}" else orig)
                continue
            try:
                seqs.append(codec.encode(text.rstrip()))
            except Exception:
                seqs.append(orig)
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
          f"(skipped-over-budget={skipped_groups}) -> {out}")


if __name__ == "__main__":
    main()
