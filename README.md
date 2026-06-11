# Langrisser V (PS1) Translation Toolkit

A toolkit for translating Langrisser V (PS1, SLPS-01818) into any language.
The current target is English, but every step below works the same way for
another language (e.g. Russian) — only the glyph set and the per-language
data files change.

Requirements: Python 3.10+, Pillow (`pip install pillow`), the original
BIN/CUE image in `iso/` (not in git).

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
  Text growth is absorbed into each chunk's trailing zero padding, which the
  validator checks as the per-chunk byte budget.

## Where things are

| Path | What it is |
| --- | --- |
| `data/font_mapping/groups_report.csv` | the font table: glyph index → character (JP original) |
| `data/font_mapping/en_slot_assignments.csv` | which rare-kanji slots were given to new glyphs (letters and letter pairs) |
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
```

## Step 1 — dump the original script

```bash
python3 scripts/lang5_scendump.py          # -> work/scriptdump/SCEN*/chunk_NNN.txt
python3 scripts/lang5_verify_roundtrip.py  # must print OK: dump->insert is byte-identical
```

Each chunk file is one scene: `record_index<TAB>text`, control words as
`<$XXXX>` tags. The first records of a story chunk are speaker name plates
(`...<$FFFF>`), then the win/loss objectives (`・...`), the location plate,
then dialogue. To see which chunk is which scenario, look at the name
plates/objectives, or generate the side-by-side review pages:

```bash
python3 scripts/lang5_review_html.py       # -> work/review/index.html
```

## Step 2 — glyphs for your language

The JP font has no lowercase Latin (and no Cyrillic). New glyphs are
rendered into slots of rarely-used kanji:

1. `data/font_mapping/en_slot_assignments.csv` maps
   `glyph index → new character → sacrificed kanji`. For another language,
   maintain the same kind of file with your alphabet (single letters and/or
   two-letter pairs; pairs put two 6px letters into one 12x12 cell — this is
   what makes EN text fit the JP byte budget).
   `scripts/lang5_assign_en_slots.py` picks sacrificial slots automatically
   from kanji that the translated text no longer needs.
2. `scripts/lang5_build_en_font.py` renders the assignments into the font
   atlas with a bitmap font and writes the insert table (`.tbl`) the encoder
   uses. To use a different font, pass `--font path/to/font.bdf` (or `.ttf`)
   and `--font-size`; the font must contain your alphabet's glyphs and fit a
   12px grid with the baseline on row 10 (the native glyph baseline).
   Verify the result visually with `scripts/lang5_font_review.py`.

Caveat: while parts of the script remain untranslated, any kanji whose slot
was sacrificed will display as the new glyph in those untranslated lines.

## Step 3 — translate a chunk

```bash
python3 scripts/lang5_tm_prefill.py 6      # -> work/wip_en/SCEN/chunk_006.txt
```

The prefill fills records that already have known translations (repeated
lines, name plates from the glossary) and prints the indices left to do.
Edit the staging file, translating record by record:

- keep every `<$XXXX>` control tag and its position relative to the text;
  only `<$FFFC>`/`<$FFFD>` line/page breaks may be moved, added or removed;
- the dialogue window is ~20 cells wide and 3 lines tall (a lowercase pair
  is one cell, a space or capital is one cell); don't worry about exact line
  breaks — the re-wrapper handles them;
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
and that the chunk fits its byte budget ("OVER BUDGET" means the text must
be shortened). Don't move partially translated chunks into
`data/translation/en` — untranslated kanji whose glyph slots were sacrificed
will fail the encode check.

For names/menus instead of script text: edit `names_base.csv` /
`system_menu_map.json`; `scripts/lang5_build_names_map.py` expands the
glossary against the actual `SYSTEM.BIN` runs and reports labels that don't
fit their slots.

## Step 4 — rebuild the patch

```bash
python3 scripts/lang5_build_ppf.py
```

This renders the font, patches `SYSTEM.BIN` (menus + names), syncs
`SCEN -> SCEN2`, re-inserts all translated chunks, injects everything into a
copy of the BIN (sizes unchanged — never use `--allow-grow`: the free space
overlaps the CD audio tracks) and writes `patches/langrisser_v_en.ppf`
(PPF3, apply to the original BIN). A ready-to-boot image is left in
`work/build/langrisser_v_en.bin` for emulator testing.

## Translating to another language

Nothing in the pipeline is English-specific:

1. Create `data/translation/<lang>/SCEN/` and pass it via `--en-dump`
   (`lang5_tm_prefill.py`, `lang5_validate_en.py`, `lang5_rewrap.py`,
   `lang5_build_ppf.py` all accept it).
2. Make your own slot-assignments CSV (e.g. Cyrillic letters and frequent
   pairs) and a bitmap font that has those glyphs; pass both to
   `lang5_build_en_font.py`.
3. Translate `names_base.csv` / `system_menu_map.json` values into your
   language; the fit checks are language-agnostic (they count cells).

## Reference

- `translation.txt` — borgor's GameFAQs scene-by-scene EN script, used as a
  meaning reference (do not copy wording verbatim).
- `docs/PLAN.md` — verified container format, root-cause notes, roadmap.
- `external/lang3` — the Langrisser 3 toolkit this one is modeled on.
