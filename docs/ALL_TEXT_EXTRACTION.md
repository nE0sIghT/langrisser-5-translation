# Langrisser V: Offline All-Text Extraction

This document defines the canonical **data-only** extraction workflow for
Langrisser V text-bearing content.  
No emulator state/savestate is required.

## Goal

Build a single corpus of text-bearing token streams from game files:

- `SCEN.DAT`
- `SCEN2.DAT`
- `SYSTEM.BIN`
- `SLPS_018.19`

Output:

- `work/scen_analysis/all_texts.csv`

Each row contains:

- source file
- section/anchor (chunk+record or global run id)
- extraction kind
- token stream (`words_hex`)
- deterministic partial decode (`decoded_partial`) using current token map.

## Script

- `scripts/lang5_extract_all_texts.py`

Run:

```bash
python3 scripts/lang5_extract_all_texts.py \
  --scen work/extracted/SCEN.DAT \
  --scen2 work/extracted/SCEN2.DAT \
  --system work/extracted/SYSTEM.BIN \
  --slps work/extracted/SLPS_018.19 \
  --out-csv work/scen_analysis/all_texts.csv
```

## Algorithm

1. Load manual token map (`scripts/lang5_token_map_manual.json`).

2. For `SCEN.DAT` and `SCEN2.DAT`:
   - split into chunks by LE32 pointer table at file start.
   - detect per-chunk local `u16` increasing offset table.
   - split chunk into records using adjacent offsets.
   - extract text windows in each record via VM text markers:
     - start at `0003`
     - stop at one of `0004 / FFFC / FFFD / FFFE / FB00`
   - include short `...FFFF` terminal records as label/name candidates.

3. For `SYSTEM.BIN` and `SLPS_018.19`:
   - parse as LE16 stream.
   - split by `FFFF` into short runs.
   - keep runs passing minimum ratio threshold.

4. For each candidate:
   - keep full token stream (`words_hex`)
   - emit deterministic partial decode:
     - known token map chars as chars
     - controls `FFxx` as `{FFxx}`
     - unknowns as `[XXXX]`

5. Sort rows deterministically by source/section/anchor/kind/tokens.

## Notes

- This algorithm extracts **all text-bearing token streams** reproducibly from
  static data files.
- Full natural-language readability still depends on expanding the remaining
  unknown token map / macro-layer tokens.
- The extraction itself is now fully offline and reproducible.
