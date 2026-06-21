# SYSTEM.BIN text format

`SYSTEM.BIN` holds the game's UI font and all of its menu/UI text: unit, class,
item, weapon, spell and character names; their triangle-button descriptions; the
menu command help; and the save / memory-card messages. This document describes
how that text is stored, so it can be dumped, translated and packed back with a
single flow (`lang5_system_dump.py` + `lang5_system_pack.py`) instead of
content-matched global replaces.

## Layout overview

```
0x00000 .. 0x0800A   font/menu-adjacent glyph data through glyph slot 1820
0x0800A .. 0x08052   non-text data before the first string group
0x08052 .. ~0x179B0  text region: a sequence of string groups (+ a few loose runs)
```

Glyph codes are 16-bit little-endian indices into the font plane (`code * 18`
points at the glyph). Special codes:

| code | meaning |
| --- | --- |
| `0x0000` | space |
| `0xFFFC` | soft line break inside a run |
| `0xFFFF` | end of string (run terminator) |
| `>= 0xFB00` | reserved / control (not a glyph) |

Glyph 1820 starts at `0x7FF8` and occupies bytes through `0x8009`. The bytes
from `0x800A` through `0x8051` are non-text prelude data, so
`lang5_system_dump.py` starts at the first verified string-group table,
`0x8052`; that group's first string base is `0x8298`. `lang5_build_en_font.py`
rewrites glyphs only up to slot 1820 to draw the English alphabet (see also
`IMG_DAT_FORMAT.md` for the unrelated picture assets).

## String groups

Almost all text lives in **groups**. A group is:

```
[ u16 offset table : N entries ][ optional preamble ][ N glyph strings ]
```

- **Offset table** — starts with `0x0000` and holds strictly increasing 16-bit
  *word* offsets. Entry `k` is the start of string `k`, measured in 16-bit words
  from the string base. Successive entries differ by `len(string_k) + 1` (the
  `+1` is the string's `0xFFFF` terminator), so steps are small (a line is at
  most ~0x20 words). The table ends where the values stop ascending.
- **Preamble** — most groups have none (`base = table_end`), but a few (e.g. the
  memory-card group) keep a small fixed block of words between the table and the
  first string. The real base is the one where a `0xFFFF` terminator sits just
  before every string start; the dumper searches `0..16` preamble words for it.
- **Strings** — string `k` is at `base + offset[k]*2` and runs to its `0xFFFF`.
  Length is `offset[k+1] - offset[k] - 1` words for `k < N-1`; the last string
  runs to its own terminator.

A candidate ascending run is only a real group if **every** table entry points at
a `0xFFFF`-terminated run (validated terminator before each string start). This
rejects look-alike ascending data (nested sub-tables, stat arrays). The greedy
ascending read can also overshoot into the first string; the dumper trims the
table to the longest prefix that still validates.

The original (Japanese) build has 16 groups holding 2639 strings, plus a small
run of ~10 **loose** strings (the memory-card / "do not power off" messages) that
have no offset table and are addressed directly. The dumper emits those with
`group = -1`.

### Why the first line of a description used to look "glued"

A naive `0xFFFF` scan starts each run after the previous terminator, so it glues
a group's offset table onto string 0 (the table has no `0xFFFF` inside it) and
reports one oversized run of garbage + text. Parsing the table instead yields
string 0 cleanly. This is why the old help dump missed several first lines and
short tail lines.

## Editing flow

```bash
# 1. dump every string (offset table aware) to one JSON
python3 scripts/lang5_system_dump.py --out data/translation/system_strings.json

# 2. translate: fill "en" per entry. "{BLANK}" clears a leftover line.

# 3. pack back into SYSTEM.BIN
python3 scripts/lang5_system_pack.py \
    --system-in work/build/SYSTEM.BIN.font \
    --system-out work/build/SYSTEM.BIN.en \
    --strings data/translation/system_strings.json --strict
```

`lang5_system_pack.py` has two modes:

- **in-place (default)** — each translated string is written into its original
  slot, padded with `0xFFFF`; the offset table is untouched. This is
  byte-compatible with the original layout, so every string keeps its exact
  position. A translation may not be longer than the original line.
- **`--repack`** — the offset table is regenerated from the actual string
  lengths, so a string may be longer or shorter (bounded by the group's total
  size). Because this moves later strings within the group, it is only safe if
  the game locates strings by table index (not by absolute offset); verify in an
  emulator before relying on it. `--max-grow N` then caps how many words wider
  than the original each line may get.

### Display limits

A string is one on-screen line. Even though `--repack` frees the data from the
original byte length, the **display** does not grow: each line is bounded by the
text box width (about 21 full-width cells; half-width English packs ~2 glyphs per
cell), and a help topic has a fixed number of lines (one run per line, and `N` is
fixed per group). Growing a line past the box width clips it. So `--repack` only
usefully reclaims room on lines that were under-full or via re-flowing a topic
across its existing lines — it does not allow unbounded expansion.

## Round-trip guarantee

Dumping with the JP table and packing with all `en` empty reproduces SYSTEM.BIN
byte-for-byte (`lang5_system_pack.py --system-in SYSTEM.BIN --tbl
data/tables/lang5_jp.tbl`), which is the correctness check for the group parser.
