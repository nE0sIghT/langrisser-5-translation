#!/usr/bin/env python3
"""Dump every translatable SYSTEM.BIN string from its offset-table groups.

SYSTEM.BIN stores its UI text (unit/class/item/weapon/spell names, their
triangle-button descriptions, and the menu command help) as a sequence of
*groups*. Each group is::

    [ u16 offset table : N entries ][ N glyph-code strings ]

The offset table starts with `0x0000` and holds strictly increasing 16-bit
*word* offsets; entry `k` is the start of string `k` measured in 16-bit words
from the string base (`base = table_start + N*2`). String `k` therefore lives at
`base + offset[k]*2` and is terminated by `0xFFFF`; its length is
`offset[k+1] - offset[k] - 1` words for `k < N-1`, and the final string runs to
its own `0xFFFF`. Glyph codes index the SYSTEM font (`<0x0720`); `0xFFFC` is a
soft line break; `0xFFFF` terminates.

This is the single source of truth for what text the game shows: there is no
heuristic FFFF scan and no minimum-length filter, so short tails and the first
string of a group (which an FFFF scan would glue onto the table) are captured
exactly. See docs/SYSTEM_BIN_FORMAT.md.
"""
import argparse
import json
import struct
from pathlib import Path

from lang5_patch_name_entry import grid_span as name_entry_grid_span

FFFF = 0xFFFF
SOFT_BREAK = 0xFFFC
SCAN_START = 0x8052      # first verified text group table
MAX_STEP = 0x30          # max plausible string length (+terminator) in words
MIN_ENTRIES = 8          # a real group has at least this many strings

# The katakana name-entry grid lives inside group 0 but is owned by
# lang5_patch_name_entry.py, which rewrites it as fixed 5-single-glyph runs.
# The unified text flow must NOT capture it: re-encoding those runs as ordinary
# text picks readability pair-glyphs (e.g. "ab" in one cell), which collapses
# the 5-column grid and corrupts the rename screen. Its span comes from the
# patcher (the single source of the grid location); see name_entry_grid_span.


def load_codemap(tbl_path: str) -> dict[int, str]:
    codemap: dict[int, str] = {}
    for line in Path(tbl_path).read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if len(key) == 4:
            try:
                codemap[int(key, 16)] = value
            except ValueError:
                pass
    return codemap


def decode_run(words: list[int], codemap: dict[int, str]) -> str:
    out: list[str] = []
    for w in words:
        if w == SOFT_BREAK:
            out.append("\\n")
        elif w >= 0xFB00 or w == 0:
            out.append("" if w == 0 else f"{{{w:04X}}}")
        else:
            out.append(codemap.get(w, f"{{?{w:04X}}}"))
    return "".join(out)


def read_table(data: bytes, pos: int) -> list[int] | None:
    """Parse a group offset table at `pos`, or None if there isn't one."""
    if pos + 2 > len(data) or struct.unpack_from("<H", data, pos)[0] != 0:
        return None
    vals = [0]
    prev = 0
    i = pos + 2
    while i + 2 <= len(data):
        v = struct.unpack_from("<H", data, i)[0]
        if prev < v <= prev + MAX_STEP:
            vals.append(v)
            prev = v
            i += 2
        else:
            break
    return vals if len(vals) >= MIN_ENTRIES else None


def run_length(data: bytes, off: int) -> int:
    n = 0
    while off + 2 * n + 2 <= len(data) and struct.unpack_from("<H", data, off + 2 * n)[0] != FFFF:
        n += 1
    return n


MAX_PREAMBLE = 16  # words between a group's table and its string base


def base_for(data: bytes, pos: int, table: list[int]) -> int | None:
    """Return the string base for a group, or None if the table is not a group.

    A real text group has a 0xFFFF terminator just before every string start.
    The base is normally `table_end`, but a few groups (e.g. the memory-card
    messages) keep a small preamble between the table and the strings, so try a
    short range of bases and accept the first where every terminator checks out.
    This rejects look-alike ascending sequences (nested sub-tables) outright.
    """
    table_end = pos + len(table) * 2
    for pre in range(MAX_PREAMBLE + 1):
        base = table_end + pre * 2
        ok = True
        for k in range(1, len(table)):
            term = base + (table[k] - 1) * 2
            if term + 2 > len(data) or struct.unpack_from("<H", data, term)[0] != FFFF:
                ok = False
                break
        if ok:
            return base
    return None


def group_at(data: bytes, pos: int) -> tuple[list[int], int] | None:
    """Return (table, base) for the group at `pos`, trimming any over-read.

    `read_table` greedily extends the ascending run, which can swallow the first
    string's leading codes when they happen to keep ascending. Accept the longest
    table prefix whose every entry points at a FFFF-terminated string.
    """
    table = read_table(data, pos)
    if table is None:
        return None
    for n in range(len(table), MIN_ENTRIES - 1, -1):
        sub = table[:n]
        base = base_for(data, pos, sub)
        if base is not None:
            return sub, base
    return None


def find_groups(data: bytes) -> list[tuple[int, list[int], int]]:
    groups: list[tuple[int, list[int], int]] = []
    pos = SCAN_START
    while pos + 2 <= len(data):
        found = group_at(data, pos)
        if found is not None:
            table, base = found
            last_off = base + table[-1] * 2
            end = last_off + (run_length(data, last_off) + 1) * 2
            groups.append((pos, table, base))
            pos = end
        else:
            pos += 2
    return groups


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--system-bin", default="work/extracted/SYSTEM.BIN")
    ap.add_argument("--tbl", default="data/common/tables/lang5_jp.tbl")
    ap.add_argument("--out", default="work/systemdump/system_strings.json")
    args = ap.parse_args()

    data = Path(args.system_bin).read_bytes()
    codemap = load_codemap(args.tbl)
    groups = find_groups(data)
    grid_span = name_entry_grid_span(data, codemap)

    entries = []
    covered = bytearray(len(data))  # mark bytes that belong to a group
    for gi, (table_off, table, base) in enumerate(groups):
        n = len(table)
        last_off = base + table[-1] * 2
        end = last_off + (run_length(data, last_off) + 1) * 2
        for b in range(table_off, end):
            covered[b] = 1
        for k in range(n):
            off = base + table[k] * 2
            if k + 1 < n:
                words = table[k + 1] - table[k] - 1
            else:
                words = run_length(data, off)
            if grid_span and grid_span[0] <= off < grid_span[1]:
                continue  # name-entry grid run: owned by lang5_patch_name_entry
            run = list(struct.unpack_from("<%dH" % words, data, off)) if words else []
            entries.append({
                "id": f"table:{table_off:05X}:{k}",
                "group": gi,
                "table": f"0x{table_off:05X}",
                "index": k,
                "offset": f"0x{off:05X}",
                "words": words,
                "jp": decode_run(run, codemap),
            })

    # Loose strings: FFFF-terminated runs in the text region that are not part of
    # any offset-table group (e.g. the memory-card error messages). They have no
    # table to regenerate, so the packer keeps them at their fixed offset.
    region_end = max((int(e["offset"], 16) + e["words"] * 2 for e in entries), default=SCAN_START)
    pos = SCAN_START
    while pos < region_end:
        if covered[pos]:
            pos += 2
            continue
        words = run_length(data, pos)
        if words >= 1 and not covered[pos]:
            run = list(struct.unpack_from("<%dH" % words, data, pos))
            text = decode_run(run, codemap)
            if any("぀" <= ch <= "ヿ" or "一" <= ch <= "鿿" for ch in text):
                entries.append({
                    "id": f"offset:{pos:05X}",
                    "group": -1, "table": None, "index": None,
                    "offset": f"0x{pos:05X}", "words": words,
                    "jp": text,
                })
        pos += (words + 1) * 2

    entries.sort(key=lambda e: int(e["offset"], 16))

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"dumped {len(entries)} strings from {len(groups)} groups -> {args.out}")


if __name__ == "__main__":
    main()
