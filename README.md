# Langrisser V (PS1) Translation Toolkit

Toolkit and language-pack repository for translating **Langrisser V** (PS1,
SLPS-01818). The project currently ships English and Russian patches, and the
same tooling can be used to prepare additional target-language packs under
`data/lang/<lang>/`.

The repository contains only durable translation data and tooling. Original game
assets, extracted files, generated Japanese dumps, build products and local
patch outputs are not tracked.

## Patch Use

Provide your own original Langrisser V disc image. The patch modifies only the
`.bin`; the `.cue` is unchanged.

- DuckStation: put the language PPF next to your `.bin` and run the game.
- Other emulators: apply the PPF3 patch to the `.bin` with a PPF tool, then keep
  the original `.cue`.

Generated patch names:

- `patches/langrisser_v_en.ppf` - English patch.
- `patches/langrisser_v_ru.ppf` - Russian patch.

Verify release downloads against release `SHA256SUMS`.

## Donations

If you want to support the work or say thanks:

- EVM: `0x6b513f6853003726502ec258351fcf6b82336d49`
- Boosty: https://boosty.to/ne0sight/donate

## License

This toolkit is GPL-3.0-or-later. See `LICENSE`. Game assets are not included.

Bundled third-party fonts:

- `data/fonts/terminus-normal.otb` and `data/fonts/ter-u14n.bdf`: Terminus
  Font, SIL Open Font License 1.1. See `data/fonts/Terminus-OFL.txt`.
- `data/fonts/spleen-6x12.bdf`: Spleen 6x12, BSD 2-Clause. See
  `data/fonts/Spleen-LICENSE`.
- `data/fonts/PixelMplus*.ttf`: PixelMplus / M+ Fonts, M+ Font License. See
  `data/fonts/PixelMplus-README.txt`.
- `data/fonts/LiberationSansNarrow-Bold.ttf`: Liberation Sans Narrow, GPL-2
  with font exception. See `data/fonts/LiberationSansNarrow-COPYRIGHT.txt`.
- `data/fonts/DejaVuSerif-Bold.ttf`: DejaVu Fonts, Bitstream Vera / public
  domain derivative notices. See `data/fonts/DejaVu-LICENSE.txt`.

## Requirements

- Python 3.10+
- Pillow: `python3 -m pip install --user pillow`
- Original BIN/CUE image in `iso/`

## Original Image

The build scripts expect this verified local image:

| File | Size | CRC32 | MD5 | SHA-1 | SHA-256 |
| --- | ---: | --- | --- | --- | --- |
| `iso/SLPS-01818-9-B.bin` | `696248448` | `5d13a8df` | `7a9e431453fde9301188841f215bff98` | `e096604f2d4d69b48eb3c1b20ca5ea26e1ea8766` | `af3f5e1d6912f31f712d43cf71d954481fa9814021e62b41fdd8fce0c9429247` |
| `iso/SLPS-01818-9-B.cue` | `224` | `2683304f` | `455eca5422d06973bb32f7fed4ce2416` | `f2f2f1abf836e26acfd37030d7d9a378cca2a0de` | `754cfdc98d0aa354dd1d8cd0c5e4d377883a2acccf9636fd5e9826f1b1e52a66` |

## Repository Layout

| Path | Purpose |
| --- | --- |
| `data/common/` | shared maps, scenario map, UI constraints and JP table |
| `data/lang/en/` | English language pack |
| `data/lang/ru/` | Russian language pack |
| `data/lang/<lang>/manifest.json` | language settings used by tools |
| `data/lang/<lang>/SCEN/` | completed translated script chunks for that language |
| `data/lang/<lang>/system_strings.json` | target SYSTEM.BIN UI text overlay |
| `data/lang/<lang>/system_layout.json` | SYSTEM.BIN line-growth constraints |
| `data/lang/<lang>/title_credits.json` | language-specific title credits |
| `data/lang/<lang>/names.csv` | item, class, spell, unit and NPC names |
| `data/lang/<lang>/glossary.csv` | canonical glossary and recurring terms |
| `data/lang/<lang>/font_slot_assignments.csv` | target glyph assignments |
| `data/lang/<lang>/name_entry_grid.json` | target name-entry alphabet layout |
| `data/lang/<lang>/review_status.csv` | per-record translation and JP cross-check status |
| `work/extracted/` | extracted game files, generated |
| `work/scriptdump/` | generated JP script dump, not tracked |
| `work/systemdump/` | generated SYSTEM.BIN string dump, not tracked |
| `work/wip_<lang>/` | partial translation staging area |
| `work/build/` | generated build files and previews |
| `patches/langrisser_v_<lang>.ppf` | generated PPF output |

Do not commit generated JP script dumps, extracted game files, build outputs or
partial translated chunks.

## Translation Model

Every target language is a language pack under `data/lang/<lang>/`. A pack
contains durable translation/editorial data only:

- completed SCEN chunks;
- target SYSTEM strings;
- names, glossary and review status;
- font assignments and name-entry layout;
- target title credits and non-reproducible graphic/cutscene transcript text.

Generated Japanese source data stays under `work/` and is reproducible from the
user's own disc image. This avoids committing game text that can be extracted by
scripts.

English (`en`) and Russian (`ru`) are complete language packs. Additional
languages should start from `scripts/lang5_init_lang.py` and follow the same
extraction, review, validation and build flow.

## Flow 1: Extract Source Data

Extract original game files:

```bash
mkdir -p work/extracted
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /L5/SCEN.DAT  work/extracted/SCEN.DAT
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /L5/SCEN2.DAT work/extracted/SCEN2.DAT
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /L5/SYSTEM.BIN work/extracted/SYSTEM.BIN
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /L5/IMG.DAT    work/extracted/IMG.DAT
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /SLPS_018.19  work/extracted/SLPS_018.19
```

Dump source text and verify the no-edit round trip:

```bash
python3 scripts/lang5_scendump.py
python3 scripts/lang5_system_dump.py
python3 scripts/lang5_verify_roundtrip.py
```

Generated JP source stays under `work/scriptdump/` and `work/systemdump/`.
These dumps are required for translation and building but are not committed.

## Flow 2: Prepare A Language Pack

Create a new language scaffold:

```bash
python3 scripts/lang5_init_lang.py <lang> --label "Language Name"
```

By default this copies source structure while clearing target-language fields
and does not copy script chunks. Use `--copy-script` only for explicit
experiments.

Review or edit these files for the target language:

- `data/lang/<lang>/manifest.json`
- `data/lang/<lang>/font_slot_assignments.csv`
- `data/lang/<lang>/system_strings.json`
- `data/lang/<lang>/system_layout.json`
- `data/lang/<lang>/title_credits.json`
- `data/lang/<lang>/names.csv`
- `data/lang/<lang>/glossary.csv`
- `data/lang/<lang>/name_entry_grid.json`
- `data/lang/<lang>/manual_record_overrides.json`
- `data/lang/<lang>/poem_prologue.txt`
- `data/lang/<lang>/virash_monologue.json`

`system_strings.json` is a target-only `stable id -> translated text` overlay.
Offsets, budgets and Japanese source come from the generated
`work/systemdump/system_strings.json`. Exact JP strings already present in the
language pack's `names.csv` or `glossary.csv` are inherited automatically during
the build; do not duplicate those canonical translations in the SYSTEM overlay.
Set `system_complete` in the language manifest only after the strict resolver
passes; later builds then reject any unresolved Japanese SYSTEM entry.

`system_layout.json` keeps conservative per-line growth limits and stable-id
exceptions required by longer target-language strings. Add exceptions only after
confirming that the affected UI field can display them.

The full patch build derives any missing target-language pairs into
`work/build/font_slot_assignments.<lang>.csv`, rebuilds the font, rewraps a copy
under `work/build/translation.<lang>/` with that exact table and validates it
before insertion. It never rewrites tracked translation sources. To persist a
new assignment baseline for review, run:

```bash
python3 scripts/lang5_assign_font_slots.py --lang <lang>
python3 scripts/lang5_build_font.py --lang <lang>
python3 scripts/lang5_font_review.py
```

## Flow 3: Translate And Review

Work scenario by scenario:

```bash
python3 scripts/lang5_scenario.py --lang <lang> list
python3 scripts/lang5_scenario.py --lang <lang> dump 1
python3 scripts/lang5_scenario.py --lang <lang> prefill 1
```

`prefill` writes partial chunks to `work/wip_<lang>/SCEN/`. Move a chunk to
`data/lang/<lang>/SCEN/` only after it is fully translated and validates.

Source priority for translation and review:

1. Generated Japanese dump under `work/` is authoritative.
2. Existing English text is a cross-check, not a replacement for the Japanese.
3. The GameFAQs guide and fan terminology are secondary references.
4. If English conflicts with Japanese, Japanese wins and English should be
   corrected.

Per translation/review pass:

```bash
python3 scripts/lang5_rewrap.py --lang <lang>
python3 scripts/lang5_validate_terms.py --lang <lang> --require-complete
python3 scripts/lang5_validate_translation.py --lang <lang>
python3 scripts/lang5_review_html.py --lang <lang> --scenario 1
```

For English, verify the speaker extractor against the in-game test set:

```bash
python3 scripts/lang5_check_speakers.py --lang en
```

For Russian, enforce speaker coverage and conservative plate width:

```bash
python3 scripts/lang5_validate_terms.py --lang ru --require-complete --require-speakers --max-plate-chars 10
```

The review generator writes `work/review/<lang>/index.html` and one page per
selected chunk. It shows JP, reference EN and target text together with speaker
plates, controls and page boundaries. Use `--scenario quiz`, `--scenario 1`, or
`--scenario opt:<name>` to follow play order; omit `--scenario` for the complete
non-empty script.

Review decisions are durable language-pack data in
`data/lang/<lang>/review_status.csv`. Set `target_done=1` only after the target
record is complete and `reference_checked=1` only after checking the reference
English record against JP. Generated review pages separately flag missing
records, control mismatches and residual Japanese.

Editing rules:

- Preserve control tags and control arguments.
- Move only safe line/page breaks: `<$FFFC>` and `<$FFFD>`.
- Keep choice records single-line.
- Use ordinary spaces and punctuation; the encoder selects compact glyph pairs.
- Keep normal hyphenated spelling; the allocator creates boundary pairs that
  prevent narrow hyphens from producing false visual spaces.
- Record meaning loss caused by byte budgets in `docs/COMPRESSION_DEBT.md`.

English reference guide:
https://gamefaqs.gamespot.com/saturn/562834-langrisser-v-the-end-of-legend/faqs/41339

## Flow 4: Build Patch

Mandatory shared checks:

```bash
python3 scripts/lang5_verify_roundtrip.py
python3 scripts/lang5_rewrap.py --lang <lang>
python3 scripts/lang5_validate_terms.py --lang <lang> --require-complete
python3 scripts/lang5_validate_translation.py --lang <lang>
python3 scripts/lang5_build_ppf.py --lang <lang> --patch-version dev
```

Run `python3 scripts/lang5_check_speakers.py --lang en` before English release
builds; Russian speaker coverage is enforced by
`lang5_validate_terms.py --lang ru --require-complete --require-speakers --max-plate-chars 10`.

The PPF build automatically validates engine-specific SYSTEM UI constraints,
including startup-menu VRAM-atlas rows and other tight fixed-width fields.

Generated outputs for language suffix `<s>`:

- `work/build/langrisser_v_<s>.bin`
- `patches/langrisser_v_<s>.ppf`
- generated DAT/SYSTEM/EXE intermediates under `work/build/`
- preview images under `work/build/`

Release build:

```bash
scripts/release.sh --release
```

The release script builds the complete English and Russian artifact set by
default, writes it to `dist/vX/`, and records PPF plus patched-image hashes in
`SHA256SUMS` and `MANIFEST.txt`. Use `--lang <lang>` to build a single language
or `--version <label>` for a non-tagged development release.

## Important Constraints

- Disc files must not grow. SCEN/SCEN2 chunk relocation is allowed only inside
  the original fixed file sizes.
- `SCEN` is the canonical script source. `SCEN2` text is byte-identical and is
  rebuilt from the same language-pack chunks.
- The font atlas ends at glyph 1820; later SYSTEM.BIN words are menu data.
- Control words and argument words must survive translation in order.
- Target punctuation must exist in the native map or be allocated by the
  language pack.

## Documentation

- `AGENTS.md`: non-negotiable project rules for coding agents.
- `docs/PLAN.md`: active Russian editorial and EN cross-check plan.
- `docs/IMPLEMENTED.md`: completed toolkit, English and multilingual milestones.
- `docs/INTERNAL_DATA_FORMATS.md`: format index and verified binary notes.
- `docs/LANGUAGE_PACK_FORMAT.md`: language-pack structure.
- `docs/RU_TERMINOLOGY.md`: canonical Russian names and terminology policy.
- `docs/SYSTEM_BIN_FORMAT.md`: SYSTEM.BIN string groups.
- `docs/IMG_DAT_FORMAT.md`: IMG.DAT image container.
- `docs/BATTLE_SUFFIX_FORMAT.md`: battle chunk suffix payloads.
- `docs/SPEAKER_NAME_EXTRACTION.md`: speaker plate extraction and wrapping.
