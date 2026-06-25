# Langrisser V (PS1) Translation Toolkit

Toolkit for translating Langrisser V (PS1, SLPS-01818). English is the shipped
v2 target. Other targets, including Russian, are language packs under
`data/lang/<lang>/` and use the same extraction, validation, font and packaging
flow.

Game assets, extracted files and generated dumps are not tracked. Durable
translation data is tracked under `data/`; generated data stays under `work/`.

## Patch Use

Provide your own original Langrisser V disc image. The patch modifies only the
`.bin`; the `.cue` is unchanged.

- DuckStation: put `yourgame.ppf` next to `yourgame.bin` and run the game.
- Other emulators: apply the PPF3 patch to the `.bin` with a PPF tool, then keep
  the original `.cue`.

Verify the result against release `SHA256SUMS`.

## Donations

If you want to support the work or say thanks:

- EVM: `0x6b513f6853003726502ec258351fcf6b82336d49`
- Boosty: https://boosty.to/ne0sight/donate

## License

This toolkit is GPL-3.0-or-later. See `LICENSE`. Game assets are not included.

Bundled third-party fonts:

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
| `data/common/` | shared maps, original font map and JP table |
| `data/lang/en/` | English language pack |
| `data/lang/ru/` | Russian language scaffold |
| `data/lang/<lang>/manifest.json` | language settings used by tools |
| `data/lang/<lang>/SCEN/` | translated script chunks for that language |
| `data/lang/<lang>/system_strings.json` | SYSTEM.BIN UI text |
| `data/lang/<lang>/names.csv` | item, class, spell and NPC names |
| `data/lang/<lang>/font_slot_assignments.csv` | target glyph assignments |
| `work/extracted/` | extracted game files, generated |
| `work/scriptdump/` | generated JP script dump, not tracked |
| `work/wip_<lang>/` | partial translation staging area |
| `work/build/` | generated build files and previews |
| `patches/langrisser_v_<lang>.ppf` | generated PPF output |

Do not commit generated JP script dumps or partial translated chunks.

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
python3 scripts/lang5_verify_roundtrip.py
```

The generated JP source for translation is `work/scriptdump/`.

## Flow 2: Prepare A Language Pack

Create a new language scaffold:

```bash
python3 scripts/lang5_init_lang.py ru --label Russian
```

By default this copies durable editorial files but not script chunks. Use
`--copy-script` only for explicit experiments.

Review or edit these files for the target language:

- `data/lang/<lang>/manifest.json`
- `data/lang/<lang>/font_slot_assignments.csv`
- `data/lang/<lang>/system_strings.json`
- `data/lang/<lang>/names.csv`
- `data/lang/<lang>/glossary.csv`
- `data/lang/<lang>/name_entry_grid.json`
- `data/lang/<lang>/poem_prologue.txt`
- `data/lang/<lang>/virash_monologue.json`

Regenerate font data when the alphabet changes:

```bash
python3 scripts/lang5_assign_font_slots.py --lang ru
python3 scripts/lang5_build_font.py --lang ru
python3 scripts/lang5_font_review.py
```

## Flow 3: Translate

Work scenario by scenario:

```bash
python3 scripts/lang5_scenario.py --lang ru list
python3 scripts/lang5_scenario.py --lang ru dump 1
python3 scripts/lang5_scenario.py --lang ru prefill 1
```

`prefill` writes partial chunks to `work/wip_ru/SCEN/`. Move a chunk to
`data/lang/ru/SCEN/` only after it is fully translated and validates.

Per translation pass:

```bash
python3 scripts/lang5_rewrap.py --lang ru
python3 scripts/lang5_check_speakers.py --lang ru
python3 scripts/lang5_validate_translation.py --lang ru
python3 scripts/lang5_review_html.py --lang ru
```

Editing rules:

- Preserve control tags and control arguments.
- Move only safe line/page breaks: `<$FFFC>` and `<$FFFD>`.
- Keep choice records single-line.
- Use ordinary spaces and punctuation; the encoder selects compact glyph pairs.
- Record meaning loss caused by byte budgets in `docs/COMPRESSION_DEBT.md`.

English reference guide:
https://gamefaqs.gamespot.com/saturn/562834-langrisser-v-the-end-of-legend/faqs/41339

## Flow 4: Build Patch

Mandatory checks and build:

```bash
python3 scripts/lang5_verify_roundtrip.py
python3 scripts/lang5_rewrap.py --lang ru
python3 scripts/lang5_check_speakers.py --lang ru
python3 scripts/lang5_validate_translation.py --lang ru
python3 scripts/lang5_build_ppf.py --lang ru --patch-version dev
```

Generated outputs:

- `work/build/langrisser_v_ru.bin`
- `patches/langrisser_v_ru.ppf`
- preview images under `work/build/`

Build English v2:

```bash
python3 scripts/lang5_build_ppf.py --lang en --patch-version 2
```

## Documentation

- `docs/PLAN.md`: verified format notes and project plan.
- `docs/LANGUAGE_PACK_FORMAT.md`: language-pack structure.
- `docs/SYSTEM_BIN_FORMAT.md`: SYSTEM.BIN string groups.
- `docs/IMG_DAT_FORMAT.md`: IMG.DAT image container.
- `docs/BATTLE_SUFFIX_FORMAT.md`: battle chunk suffix payloads.
- `docs/SPEAKER_NAME_EXTRACTION.md`: speaker plate extraction and wrapping.
