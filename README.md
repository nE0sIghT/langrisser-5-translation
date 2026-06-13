# Langrisser V (PS1) Translation Toolkit

Toolkit for translating Langrisser V (PS1, SLPS-01818). Target language is
arbitrary (current work: English; Russian etc. is possible) — only the glyph
set and per-language data files differ, see "Another language" below.

Requirements: Python 3.10+, Pillow (`pip install pillow`), original BIN/CUE
image in `iso/` (not in git).

## How the game stores text

- Text is encoded as 16-bit tokens. A token below `0xE000` is an index into
  the 12x12 1bpp font atlas at the start of `SYSTEM.BIN` (glyphs 0–1820;
  tiles 1821+ are menu data — never glyphs). Tokens `0xF600`/`0xFB00–0xFBFF`
  take one argument word (speaker/portrait IDs, the player-name macro
  `<$F600><$0000>`). `0xFFFC` is a line break, `0xFFFD` a page break,
  `0xFFF4`/`0xFFF3` highlight on/off, `0xFFFE`/`0xFFFF` terminators. Other
  `0xFFxx`/`0xFExx` words are effect/pause controls — keep them.
- Story text lives in `SCEN.DAT`/`SCEN2.DAT` (131 chunks each; the text
  blocks of both files are byte-identical, so you translate `SCEN` only and
  the build step copies it to `SCEN2`). Chunks 1–42 are roughly the
  scenarios in order (chunk 0 is the intro quiz); later chunks hold clear
  scenes, save-point scenes and small events.
- Menu labels, item/class/spell names and their descriptions are
  fixed-position runs inside `SYSTEM.BIN`.
- The disc has CD audio after the data track: file sizes must never change.
  Text growth is absorbed by rebuilding the internal SCEN/SCEN2 chunk layout
  at 0x800 alignment and rewriting the chunk pointer table. The validator
  checks that the fixed-size repack still fits inside the original files.

## Where things are

| Path | What it is |
| --- | --- |
| `data/font_mapping/groups_report.csv` | the font table: glyph index → character (JP original) |
| `data/font_mapping/en_slot_assignments.csv` | which rare-kanji slots were given to new glyphs (letters, letter pairs, spacing pairs) |
| `data/fonts/` | bitmap fonts used to render new glyphs (Spleen 6x12 BDF, PixelMplus TTF) |
| `data/translation/en/SCEN/chunk_NNN.txt` | translated chunks (the build input) |
| `data/translation/names_base.csv` | item/class/spell/NPC name glossary (jp,en,alt) |
| `data/translation/system_menu_map.json` | menu/UI label replacements |
| `work/scriptdump/` | the original JP dump (regenerable) |
| `work/wip_en/` | staging area for chunks being translated |
| `docs/PLAN.md` | format notes and the project plan |

## Step 0 — extract game files (once)

```bash
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /L5/SCEN.DAT  work/extracted/SCEN.DAT
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /L5/SCEN2.DAT work/extracted/SCEN2.DAT
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /L5/SYSTEM.BIN work/extracted/SYSTEM.BIN
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /SLPS_018.19 work/extracted/SLPS_018.19
```

## Step 1 — dump the original script

```bash
python3 scripts/lang5_scendump.py          # -> work/scriptdump/SCEN*/chunk_NNN.txt
python3 scripts/lang5_verify_roundtrip.py  # must print OK: dump->insert is byte-identical
```

Chunk file format: one scene per file, `record_index<TAB>text`, control
words as `<$XXXX>` tags. Record order in a story chunk: speaker name plates
(`...<$FFFF>`), win/loss objectives (`・...`), location plate, dialogue.

Chunks map to game scenarios (`data/scenario_map.json`): scenario K is
played as scene chunk `44+K` -> battle chunk `K` (which also contains the
post-battle dialogue) -> scene chunk `86+K`. Chunk 0 is the intro quiz,
37 the tutorial battle, 38-42 optional maps (intros 82-86), 129/130 the
in-game recap screens. Work with scenarios instead of raw chunk numbers:

```bash
python3 scripts/lang5_scenario.py list      # all scenarios, chunks, progress
python3 scripts/lang5_scenario.py dump 11   # -> work/scenario_text/scenario_11.txt
python3 scripts/lang5_scenario.py prefill 11  # stage all chunks of scenario 11
python3 scripts/lang5_review_html.py        # JP/EN review pages -> work/review/
```

## Step 2 — glyphs for your language

The JP font has no lowercase Latin and no Cyrillic. New glyphs are written
into slots of rarely-used kanji:

1. `data/font_mapping/en_slot_assignments.csv` maps
   `glyph index → new character → sacrificed kanji`. For another language,
   make the same kind of file for its alphabet: single letters and/or
   two-letter pairs (a pair packs two 6px letters into one 12x12 cell and
   halves the byte cost of text), narrow `space+letter` / `letter+space` pairs,
   `punctuation+space` pairs, and punctuation pairs such as `h:`.
   `scripts/lang5_assign_en_slots.py` picks sacrificial slots automatically
   from kanji that the translated text no longer needs.
2. `scripts/lang5_build_en_font.py` renders the assignments into the font
   atlas with a bitmap font and writes the insert table (`.tbl`) the encoder
   uses. To use a different font, pass `--font path/to/font.bdf` (or `.ttf`)
   and `--font-size`; the font must contain your alphabet's glyphs and fit a
   12px grid with the baseline on row 10 (the native glyph baseline).
   The EN build also redraws the native digits, question, exclamation and
   colon glyphs to match the bitmap Latin font, and lowers the ellipsis to
   the text baseline. Verify the result visually with
   `scripts/lang5_font_review.py`.

Caveat: until the whole script is translated, a sacrificed kanji shows up
as the new glyph in untranslated lines.

## Step 3 — translate a scenario

```bash
python3 scripts/lang5_scenario.py prefill 6   # stages chunks 50, 6, 92
python3 scripts/lang5_tm_prefill.py 6         # or stage a single chunk
```

The prefill fills records that already have known translations (repeated
lines, name plates from the glossary) and prints the indices left to do.
Edit the staging file, translating record by record:

- keep every `<$XXXX>` control tag and its position relative to the text;
  only `<$FFFC>`/`<$FFFD>` line/page breaks may be moved, added or removed;
- the text window is 21 cells wide (a lowercase pair is one cell, a narrow
  `space+letter`, `letter+space`, `punctuation+space`, or `letter+punctuation`
  pair is one cell when assigned, the player-name macro counts as 8) and a page
  holds up to 4 lines; write normal spaces and punctuation in the text files —
  the encoder picks the compact glyphs automatically. Don't worry about exact
  line breaks: the re-wrapper handles them, reserving speaker-plate width on
  the first line of a plated spoken record. Continuation pages after `<$FFFD>`
  do not redraw the plate and wrap at full width. The wrapper may compact
  plain-text continuation pages in non-battle scene chunks, but battle chunks
  keep `<$FFFD>` hard because battle scripts can tie paging to portrait/event
  state. When decoded VM display rows identify a record's plate slot, the
  wrapper uses that exact width; otherwise it falls back to the chunk's widest
  speaker plate (keep plate names at 5 cells or less);
- choice records (starting with `・`) must stay single-line;
- the font has no `; — – !? /` — use `,` and full-width `！？`.

When the chunk is fully translated, move it into the build input and run the
re-wrapper and validator:

```bash
mv work/wip_en/SCEN/chunk_006.txt data/translation/en/SCEN/
python3 scripts/lang5_rewrap.py            # wraps lines to the window width
python3 scripts/lang5_validate_en.py       # tags, encodability, byte budget
```

`lang5_validate_en.py` compares every record's control-tag signature with
the JP original, checks that everything encodes with the current font table
and that the translated SCEN/SCEN2 files still fit the fixed-size repack
budget ("OVER BUDGET" means the text must be shortened). Don't move partially
translated chunks into
`data/translation/en` — untranslated kanji whose glyph slots were sacrificed
will fail the encode check.

For battle chunks with portrait/asset regressions, also run
`python3 scripts/lang5_validate_en.py N --budget-mode block`: this stricter
mode requires the translation to fit inside the original text block so the
following chunk data stays at byte-identical offsets.
The normal inserter keeps grown text blocks 4-byte aligned, matching the
original battle suffix alignment. Aligned growth has been verified in-game on
chunk 002; block mode is now a diagnostic fallback only if a future battle
asset regression appears. `scripts/lang5_battle_suffix.py` reports the battle
suffix asset-slot table behind this rule.

For names/menus instead of script text: edit `names_base.csv` /
`system_menu_map.json`; `scripts/lang5_build_names_map.py` expands the
glossary against the actual `SYSTEM.BIN` runs and reports labels that don't
fit their slots.

For VM/script diagnostics, `scripts/lang5_vm_dialog_refs.py` extracts
chunk-local name pools and static VM command sites that reference `FB00`
dialogue IDs. Its output is evidence for reverse-engineering speaker binding;
speaker plates are not maintained as hand-written data.

## Step 4 — rebuild the patch

```bash
python3 scripts/lang5_build_ppf.py
```

This renders the font, patches `SYSTEM.BIN` (menus + names), patches
`SLPS_018.19` (name-entry grid), syncs `SCEN -> SCEN2`, re-inserts all
translated chunks with fixed-size container repacking, injects everything
into a copy of the BIN (sizes unchanged — never use `--allow-grow`: the
free space overlaps the CD audio tracks) and writes
`patches/langrisser_v_en.ppf` (PPF3, apply to the original BIN). A
ready-to-boot image is left in `work/build/langrisser_v_en.bin` for emulator
testing.

## Another language

The pipeline is not tied to English:

1. Create `data/translation/<lang>/SCEN/` and pass it via `--en-dump`
   (`lang5_tm_prefill.py`, `lang5_validate_en.py`, `lang5_rewrap.py`,
   `lang5_build_ppf.py` all accept it).
2. Make your own slot-assignments CSV (e.g. Cyrillic letters and frequent
   pairs) and a bitmap font that has those glyphs; pass both to
   `lang5_build_en_font.py`.
3. Translate `names_base.csv` / `system_menu_map.json` values into your
   language; the fit checks are language-agnostic (they count cells).

## Reference

- `translation.txt` — borgor's GameFAQs scene-by-scene EN script; its
  wording may be reused where it fits the JP line and the byte budget.
- `docs/PLAN.md` — verified container format, root-cause notes, roadmap.
- `docs/BATTLE_SUFFIX_FORMAT.md` — current notes on the battle chunk payload
  after the text block.
- `external/lang3` — the Langrisser 3 toolkit this one is modeled on.
