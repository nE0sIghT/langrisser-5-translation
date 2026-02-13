# Langrisser V PS1 patch workspace

This repository contains reproducible scripts to build a `PPF3` patch for the
`SLPS-01818-9-B` PlayStation image.

Current status:
- `patches/langrisser_v_en.ppf` is generated from the clean image.
- The patch currently replaces the executable title string
  `ラングリッサー５` with `LANGRISSER V`.
- `SCEN.DAT` and `SCEN2.DAT` format is partially reversed and extractor tooling
  is available.

## Build

```bash
python3 scripts/make_langrisser_v_ppf.py
```

Inputs:
- `iso/SLPS-01818-9-B.bin`

Outputs:
- `work/build/SLPS-01818-9-B.en.bin`
- `patches/langrisser_v_en.ppf`

## Utility scripts

- `scripts/iso_mode2.py`: list/extract/inject files inside PS1 `MODE2/2352` BIN.
- `scripts/ppf3.py`: generate a `PPF3` patch from original and modified BIN.
- `scripts/make_langrisser_v_ppf.py`: end-to-end patch builder for this project.
- `scripts/lang5_scen_extract.py`: reverse/analyze `SCEN*.DAT` and export
  chunk/record/token data for script work.

## SCEN format findings

Based on direct binary analysis and archived forum notes:

- `SCEN.DAT`/`SCEN2.DAT` are composed of sector-aligned chunks.
- File header (`0x800` sector) is a table of little-endian chunk pointers.
- Each chunk contains:
  - script/event bytecode,
  - a local 16-bit increasing offset table (record index),
  - many records with mixed control words and text tokens.
- Token stream uses 16-bit words with bank suffixes:
  - character banks are observed under high bytes `00`, `01`, `02`,
  - `FFFF` is used as end marker in short text records,
  - `FB00` appears frequently in event/dialog orchestration records.
- Magic separator sequence
  `01 00 00 01 80 00 00 00 78 80 70 80 30 30 01 02 78 78 00 13 28 13 38 38 02 00 A0 A0 00 10 18 10`
  is present in 116 / 131 chunks (same pattern in both files).
- `SCEN` vs `SCEN2` differ only in chunks:
  `1..36` and `40..42` (likely route/ending variants).

## Extract script structure and storyline mapping

```bash
python3 scripts/lang5_scen_extract.py
```

Outputs in `work/scen_analysis`:

- `summary.json`: high-level findings (diff chunks, magic presence, hints).
- `chunks.csv`: one line per chunk with offsets, table location, FB counts.
- `records.csv`: record-level word streams (hex words) for scripting research.
- `dialogue_candidates.csv`: record subset with strong text-token characteristics.
- `story_map.csv`: practical linkage `Scenario N` -> chunk index.

## External reference artifacts

- `external/l5scen.py` and `external/l5scen.py.zip`:
  recovered from archived `zophar.net` thread attachment
  (`l5scen.py.zip`) for historical reference.
