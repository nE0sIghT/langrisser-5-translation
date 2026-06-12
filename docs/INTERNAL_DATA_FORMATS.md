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

## Speaker plate reserves

The first `FFFF`-terminated records in story chunks form a local name-plate
pool. Dialogue records do not point to that pool directly: `FB00 <id>` is a
dialogue/event ID, not a name-record index. Example from chunk 45: record 10
uses `FB00 0003`, while its visible speaker is the local machine-voice plate
(name record 7 in that chunk).

The reference layer is in the chunk VM bytecode before the text block.
`scripts/lang5_vm_dialog_refs.py` extracts command sites that reference the
same `FB00` IDs, with currently confirmed shapes:

```text
<state> <fb_id> FF0B <flags> FFFF FFFF
FF00 <fb_id> ... FF0B <flags> FFFF FFFF
```

The `state` word and optional words before `FF0B` are actor/pose/window state
and still require dispatch-level interpretation before they can be converted
to exact speaker plate widths. No hand-written speaker map is canonical.

Detailed dispatch-level evidence is in:
- `docs/DISASM_SUMMARY.md`
