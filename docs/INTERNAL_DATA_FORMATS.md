# Internal Data Formats (Confirmed)

## ISO layout (relevant files)

- `/L5/SCEN.DAT`
- `/L5/SCEN2.DAT`
- `/L5/SYSTEM.BIN`
- `/SLPS_018.19`

## SCEN.DAT / SCEN2.DAT

Container layout:
1. Global chunk pointer table (`u32`, little-endian)
2. Chunk payloads

Each chunk:
1. Local record offset table (`u16` ascending offsets)
2. Record byte streams (word-oriented script data)

Record word format:
- `u16` tokens
- printable tokens are generally `< 0xE000`
- control tokens are mostly high ranges (`0xFxxx`, `0xFFxx`)

## Text stream model

- Script records are token streams, not raw Shift-JIS strings.
- Rendering/logic uses control opcodes and printable token IDs.
- Practical editable representation in tooling:
  - known glyph tokens as chars
  - unknown/control as tags: `<$HHHH>`

## SYSTEM.BIN

Contains:
- 12x12 font plane data (token/glyph usage)
- many short `{FFFF}`-terminated UI/menu strings
- class/skill/item/system labels and message fragments

Menu patching strategy:
- split into short `FFFF`-terminated runs
- decode with canonical token map
- replace mapped runs via fixed dictionary
- preserve run length and control words

## Control token groups (high-level)

- `F600` — macro family with argument word
- `FB00`/`FBxx` — dialog/control commands with argument semantics in flow
- `FFFC` — line/page separator semantics in text path
- `FFFD`, `FFFE`, `FFFF` — control/termination states in stream handling

Detailed dispatch-level evidence is in:
- `docs/DISASM_SUMMARY.md`
