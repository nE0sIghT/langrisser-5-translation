# Langrisser V PS1 patch workspace

This repository contains reproducible scripts to build a `PPF3` patch for the
`SLPS-01818-9-B` PlayStation image.

Canonical documentation:
- `STATUS.md`: current project status and next steps.
- `docs/LANGRISSER_V_DATA_FORMAT.md`: confirmed format findings and RE notes.
- `docs/ENVIRONMENT_BOOTSTRAP.md`: tool bootstrap for environment resets.

Current patch status:
- `patches/langrisser_v_en.ppf` is generated from the clean image.
- Current demo patch replaces executable title string `ラングリッサー５`
  with `LANGRISSER V`.

## Build

```bash
python3 scripts/make_langrisser_v_ppf.py
```

Inputs:
- `iso/SLPS-01818-9-B.bin`

Outputs:
- `work/build/SLPS-01818-9-B.en.bin`
- `patches/langrisser_v_en.ppf`

## Environment bootstrap (after reset)

```bash
./scripts/bootstrap_env.sh
```

## Utility scripts

- `scripts/iso_mode2.py`: list/extract/inject files inside PS1 `MODE2/2352` BIN.
- `scripts/ppf3.py`: generate a `PPF3` patch from original and modified BIN.
- `scripts/make_langrisser_v_ppf.py`: end-to-end patch builder for this project.
- `scripts/lang5_scen_extract.py`: reverse/analyze `SCEN*.DAT` and export
  chunk/record/token data for script work.
- `scripts/lang5_story_extract.py`: export scenario-ordered tokenized dialogue
  and rough JP↔EN sequential alignment.
- `scripts/lang5_infer_lexicon.py`: infer speaker-token prefixes and generate
  partially labeled JP token stream with seed-based token substitutions.
- `scripts/lang5_make_source_dump.py`: build canonical scenario-ordered source
  dump (tokenized JP + aligned EN).
- `scripts/lang5_chunk_probe.py`: inspect records near a chunk-relative offset
  with current token map decoding.
- `scripts/lang5_anchor_report.py`: generate focused report for records with
  anchor names (`ギザロフ`, `ランフォード`) to drive token-map expansion.
- `scripts/lang5_ingame_ocr.py`: OCR helper for `work/ingame` screenshots to
  create reproducible JP anchor text (`work/scen_analysis/ingame_ocr.csv`).
- `scripts/bootstrap_env.sh`: one-shot environment recovery after resets.

## Extract script structure and storyline mapping

```bash
python3 scripts/lang5_scen_extract.py
python3 scripts/lang5_story_extract.py
python3 scripts/lang5_infer_lexicon.py
python3 scripts/lang5_make_source_dump.py
```

Outputs in `work/scen_analysis`:

- `summary.json`: high-level findings (diff chunks, magic presence, hints).
- `chunks.csv`: one line per chunk with offsets, table location, FB counts.
- `records.csv`: record-level word streams (hex words) for scripting research.
- `dialogue_candidates.csv`: record subset with strong text-token characteristics.
- `story_map.csv`: practical linkage `Scenario N` -> chunk index.
- `story_ordered.json`: scenario-ordered tokenized JP stream
  (`[XXXX]` tokens + control markers).
- `story_alignment_preview.csv`: sequence-level alignment between
  `story_ordered` records and `translation.txt` lines.
- `speaker_lexicon.json`: inferred speaker-name token prefixes from aligned rows.
- `story_alignment_partial_decode.csv`: same alignment with partial speaker
  labeling plus confirmed JP token substitutions
  (currently seeded from `ランフォード元帥`).
- `source_script_tokenized.txt` and `source_script_tokenized.csv`:
  canonical source dump in scenario order.
