# Tutorial Screen Anchors (Ingame Capture)

Last updated: 2026-02-14

This document tracks screenshot-confirmed Japanese tutorial lines and their
current mapping status to `SCEN.DAT` records.

## Confirmed on-screen lines

Verified directly from screenshots in `work/ingame2`:

- `では、もう一度最初から設定を行います。`
- `まず最終成長形態の設定を行います。`
- `４つの金属の中から、３つを培養液に混ぜ合わせます。`
  `不要な物を選んで下さい。`

## Reproducible OCR extraction

- Command:
  - `python3 scripts/lang5_ingame_ocr.py --input-dir work/ingame2 --out-csv work/scen_analysis/ingame2_ocr.csv --out-txt work/scen_analysis/ingame2_timeline.txt`
- Outputs:
  - `work/scen_analysis/ingame2_ocr.csv`
  - `work/scen_analysis/ingame2_timeline.txt`

## SCEN anchor window (current best match)

Strong candidate window in `SCEN.DAT`:

- chunk `56`, records `22..26` (`0x547E..0x54FC`)

Key evidence:

- `rec 22` includes `ギザロフ[02B0]。`
- `rec 25` has exactly two sentence terminators (`0006`) and one explicit line
  break control (`FFFC`), matching the two-line/two-sentence metal-selection
  prompt structure.

Record summary:

- `rec 22`: `0216 0225 0054 0046 0003 008B 0093 00CA 00B2 02B0 0006 ...`
- `rec 23`: `0057 007D 004D 0003 053C 0365 0044 0031 0004 ...`
- `rec 24`: `F600 0000 0039 0003 026B 0042 0079 006B 0044 004C 0006 ...`
- `rec 25`: `0351 004D 0050 0053 0006 FFFC 002F 0031 0051 0039 ... 0006 ...`
- `rec 26`: `0056 0033 0031 0033 0040 0055 004D 0003 0186 ...`

## Confidence

- Tutorial sequence locality in chunk 56: high confidence.
- Exact 1:1 mapping for each sentence to each record: medium confidence.
  (Parser still treats this as short control/text records; grammar is not fully
  finalized.)
