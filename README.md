# Langrisser V PS1 patch workspace

This repository contains reproducible scripts to build a `PPF3` patch for the
`SLPS-01818-9-B` PlayStation image.

Current status:
- `patches/langrisser_v_en.ppf` is generated from the clean image.
- The patch currently replaces the executable title string
  `ラングリッサー５` with `LANGRISSER V`.
- Full story script insertion is not implemented yet because `SCEN.DAT` and
  `SCEN2.DAT` use a custom script/container format that still needs decoding.

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
