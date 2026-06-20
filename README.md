# Langrisser V (PS1) Translation Toolkit

Toolkit for translating Langrisser V (PS1, SLPS-01818). The active target is
English; other target languages can reuse the same extraction, validation and
repacking flow with different glyph assignments and translation data.

## Applying the patch

Provide your own original Langrisser V disc image (see *Original Image
Verification* below for the exact `.bin`). The patch only modifies the `.bin`;
your `.cue` is unchanged.

- **DuckStation:** drop the `.ppf` next to your `.bin` with the same base name
  (`yourgame.bin` + `yourgame.ppf`) and run the game as usual — DuckStation
  applies the patch on the fly and never touches your image.
- **Permanent patch / other emulators:** apply the `.ppf` to the `.bin` with any
  PPF3.0 tool — [ROMPatcher.js](https://www.marcrobledo.com/RomPatcher.js/)
  (browser), `ApplyPPF3`, or PPF-O-Matic 3; keep the `.cue` as-is (PPF only
  modifies the `.bin`). The patch embeds the PPF3.0 image-validation block, so
  these tools confirm you are patching the exact original image.

Then verify your result against the release `SHA256SUMS`.

## Donations

If you want to support the work or say thanks, donations are welcome:

- EVM (Ethereum, Polygon, BSC, Arbitrum, ...): `0x6b513f6853003726502ec258351fcf6b82336d49`
- Boosty: https://boosty.to/ne0sight/donate

## License

This toolkit is licensed under the GNU GPL version 3 or later. See `LICENSE`.
Game assets are not included in this repository.

Bundled third-party fonts:

- `data/fonts/spleen-6x12.bdf` — Spleen 6x12, BSD 2-Clause; see
  `data/fonts/Spleen-LICENSE`.
- `data/fonts/PixelMplus*.ttf` — PixelMplus / M+ Fonts, M+ Font License; see
  `data/fonts/PixelMplus-README.txt`.
- `data/fonts/LiberationSansNarrow-Bold.ttf` — Liberation Sans Narrow,
  GPL-2 with font exception; see
  `data/fonts/LiberationSansNarrow-COPYRIGHT.txt`.

## Requirements

- Python 3.10+
- Pillow (`pip install pillow`)
- Original BIN/CUE image in `iso/`

## Original Image Verification

The build scripts expect the original Langrisser V PS1 image in `iso/`.
The current verified local image is:

- `iso/SLPS-01818-9-B.bin`
  - Size: `696248448` bytes
  - CRC32: `5d13a8df`
  - MD5: `7a9e431453fde9301188841f215bff98`
  - SHA-1: `e096604f2d4d69b48eb3c1b20ca5ea26e1ea8766`
  - SHA-256: `af3f5e1d6912f31f712d43cf71d954481fa9814021e62b41fdd8fce0c9429247`
- `iso/SLPS-01818-9-B.cue`
  - Size: `224` bytes
  - CRC32: `2683304f`
  - MD5: `455eca5422d06973bb32f7fed4ce2416`
  - SHA-1: `f2f2f1abf836e26acfd37030d7d9a378cca2a0de`
  - SHA-256: `754cfdc98d0aa354dd1d8cd0c5e4d377883a2acccf9636fd5e9826f1b1e52a66`

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
| `data/fonts/` | fonts used by the build: Spleen/PixelMplus for game glyphs, Liberation Sans Narrow Bold for title credits |
| `data/translation/en/SCEN/chunk_NNN.txt` | translated chunks (the build input) |
| `data/translation/names_base.csv` | item/class/spell/NPC name glossary (jp,en,alt) |
| `data/translation/system_strings.json` | all SYSTEM.BIN UI text (names, descriptions, command help, save messages) — one offset-keyed file, see *Translating SYSTEM.BIN text* below |
| `work/scriptdump/` | the original JP dump (regenerable) |
| `work/wip_en/` | staging area for chunks being translated |
| `docs/PLAN.md` | format notes and the project plan |

## Translation Flow

The workflow starts from a clean original image, extracts the game files into
`work/`, dumps the Japanese script for reference, edits English chunk files
under `data/translation/en/SCEN/`, validates the fixed-size repack budget, and
finally writes a PPF3 patch plus a ready-to-test BIN/CUE copy.

### 1. Extract Game Files

```bash
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /L5/SCEN.DAT  work/extracted/SCEN.DAT
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /L5/SCEN2.DAT work/extracted/SCEN2.DAT
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /L5/SYSTEM.BIN work/extracted/SYSTEM.BIN
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /L5/IMG.DAT    work/extracted/IMG.DAT
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /SLPS_018.19 work/extracted/SLPS_018.19
```

### 2. Dump The Original Script

```bash
python3 scripts/lang5_scendump.py          # -> work/scriptdump/SCEN*/chunk_NNN.txt
python3 scripts/lang5_verify_roundtrip.py  # must print OK: dump->insert is byte-identical
```

Chunk file format: one scene per file, `record_index<TAB>text`, control
words as `<$XXXX>` tags. Record order in a story chunk: speaker name plates
(`...<$FFFF>`), win/loss objectives (`・...`), location plate, dialogue.

Each spoken record is preceded by a `# spk: <name>` comment naming the
speaker (`(crowd)` for runtime-remapped off-screen lines), and
`work/scriptdump/all_records.csv` has a matching `speaker` column. The
speaker is read straight from the record's display command, not a VM walk
(see *docs/SPEAKER_NAME_EXTRACTION.md*); the same data drives the per-record
plate reserve in `lang5_rewrap.py`. The `# spk:` lines are comments, so the
dump→translate→insert round-trip ignores them.

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

### 3. Prepare English Glyphs

The JP font has no lowercase Latin. New glyphs are written into slots of
rarely-used kanji:

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

### 4. Translate A Scenario

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

For SYSTEM.BIN UI text instead of script text (names, menu labels,
descriptions, command help, save messages): edit
`data/translation/system_strings.json` — see *Translating SYSTEM.BIN text*
below.

For VM/script diagnostics, `scripts/lang5_vm_dialog_refs.py` extracts
chunk-local name pools and static VM command sites that reference `FB00`
dialogue IDs. Its output is evidence for reverse-engineering speaker binding;
speaker plates are not maintained as hand-written data.

### 5. Rebuild The Patch

```bash
python3 scripts/lang5_build_ppf.py
```

This renders the font, patches `SLPS_018.19` and the SYSTEM.BIN name-entry
grid, packs all SYSTEM.BIN UI text (names, descriptions, command help, save
messages — see *Translating SYSTEM.BIN text* below), patches `IMG.DAT`
title-screen credits and
the project QR code, redraws the prologue poem graphic (see *Translating
graphics* below), syncs `SCEN -> SCEN2`, re-inserts all translated chunks
with fixed-size container repacking, injects everything into a copy of the
BIN (sizes unchanged — never use `--allow-grow`: the free space overlaps the
CD audio tracks) and writes
`patches/langrisser_v_en.ppf` (PPF3, apply to the original BIN). A
ready-to-boot image is left in `work/build/langrisser_v_en.bin` for emulator
testing.

The title-screen credit line is generated from `--patch-version` and the
current git commit (`git rev-parse --short=8 HEAD`), for example:

```bash
python3 scripts/lang5_build_ppf.py --patch-version 1
```

The build also writes title previews to `work/build/title_credits_*.png`.

## Translating SYSTEM.BIN text

All of SYSTEM.BIN's UI text — unit/class/item/weapon/spell and character names,
their triangle-button descriptions, the menu command help, and the save /
memory-card messages — is stored as groups of `[offset table][strings]`, not as
a flat run of lines. One flow dumps, translates and packs all of it; the format
is documented in `docs/SYSTEM_BIN_FORMAT.md`.

1. **Dump** every string (offset-table aware, so glued first lines and short
   tails are captured exactly) to one offset-keyed JSON:

   ```bash
   python3 scripts/lang5_system_dump.py --out data/translation/system_strings.json
   ```

2. **Translate** by filling each entry's `en`. Leave `en` empty to keep the
   original Japanese; use `"{BLANK}"` to clear a leftover line. Missing
   punctuation can be added to the font via
   `data/font_mapping/en_slot_assignments.csv` (assign it an unused kana slot).
   Each string is one on-screen line, so keep it within the original line's
   width.

3. **Pack / check.** `lang5_build_ppf.py` runs this automatically, or run it
   directly; `--strict` fails on any over-budget or unencodable line:

   ```bash
   python3 scripts/lang5_system_pack.py \
       --system-in work/build/SYSTEM.BIN.ne --system-out work/build/SYSTEM.BIN.en \
       --strings data/translation/system_strings.json --strict
   ```

   The default in-place mode keeps each string's slot and the offset table
   (byte-compatible). `--repack` regenerates the table so a line may change
   length (bounded by the group total); since it moves later strings, verify in
   an emulator before relying on it.

Knowing semantic compressions made to fit the budgets are tracked in
`docs/COMPRESSION_DEBT.md`.

## Translating graphics (the prologue poem)

The opening poem on the title attract loop is a picture, not script text: it
lives in `IMG.DAT` as asset 12, image 0 (a 768x252 8bpp indexed bitmap). It is
translated by redrawing the bitmap from a plain text file, so no image editor is
needed - you only type the English.

1. **Write the text.** Edit `data/translation/poem_prologue.txt`:

   - Lines starting with `#` are comments.
   - **Blank lines** split the poem into **four blocks**, matching the original.
     In game the poem is **one continuous vertical scroll** (the three stored
     768px columns are stacked top-to-bottom into one tall strip), so the blocks
     are not separate screens - a blank line just adds a one-line gap between
     stanzas. Keep four blocks.
   - Every line is centred automatically and sits on a single **uniform line
     pitch** - there is no per-block stretching, and lines may straddle a column
     boundary and rejoin seamlessly. The pitch is the original 20px unless the
     English runs longer, in which case it is compressed just enough to leave a
     readable blank tail at the bottom of the last screen (so the reader has time
     to finish before it scrolls off).

2. **Build the graphic.** Either run the step on its own:

   ```bash
   python3 scripts/lang5_poem_translate.py
   ```

   or just run the full patch build (`lang5_build_ppf.py` runs it automatically,
   on top of the title-screen edit). It decodes the indexed bitmap, redraws the
   English with the bundled `data/fonts/DejaVuSerif-Bold.ttf` (black outline plus
   the poem palette's red shades), re-encodes the picture into its `IMG.DAT`
   scanline packets - both the main image **and** the small `type=2` remainder
   block that holds each column's bottom rows - **without changing the asset
   size**, and writes the patched `work/build/IMG.DAT.poem` plus a preview
   `work/build/poem_en_preview.png`.

To retarget the font, colours or layout, change the constants at the top of
`scripts/lang5_poem_translate.py`. The container/packet format the writer uses
is documented in `docs/IMG_DAT_FORMAT.md`.

## Another language

The pipeline is not tied to English:

1. Create `data/translation/<lang>/SCEN/` and pass it via `--en-dump`
   (`lang5_tm_prefill.py`, `lang5_validate_en.py`, `lang5_rewrap.py`,
   `lang5_build_ppf.py` all accept it).
2. Make your own slot-assignments CSV for the target alphabet and frequent
   pairs, plus a bitmap font that has those glyphs; pass both to
   `lang5_build_en_font.py`.
3. Translate `names_base.csv` and the `en` fields in
   `data/translation/system_strings.json` into your language; the fit checks
   are language-agnostic (they count cells).

## Reference

- Borgor's GameFAQs scene-by-scene EN script:
  https://gamefaqs.gamespot.com/saturn/562834-langrisser-v-the-end-of-legend/faqs/41339.
  Its wording may be reused where it fits the JP line and the byte budget.
- `docs/PLAN.md` — verified container format, root-cause notes, roadmap.
- `docs/BATTLE_SUFFIX_FORMAT.md` — current notes on the battle chunk payload
  after the text block.
- `docs/IMG_DAT_FORMAT.md` — current notes and tooling for the `IMG.DAT`
  image container and the verified title-screen bitmap layout.
