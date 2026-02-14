# DuckStation Runtime Plan (Deterministic Text Decode)

Last updated: 2026-02-14

Goal: replace OCR-assisted inference with runtime-confirmed decoding behavior.

## Current static anchors (from `SLPS_018.19`)

Reproducible via:

- `python3 scripts/slps_runtime_probe.py`
- Output: `work/scen_analysis/slps_runtime_probe.txt`

Confirmed addresses:

- `0x8001CFA0`: reads script word (`lhu`) and checks `0xFFFF` terminator.
- `0x8001D174`: loop-end check against `0xFFFF`.
- `0x8001D500`: loop condition branch on `current_word != 0xFFFF`.

Likely RAM state variables (derived from `lui 0x800e` + offsets):

- `0x800DBA1C`: current script pointer (`script_ptr_current`).
- `0x800DB90C`: script base table pointer (`script_base_table`).
- `0x800DB8D4`: interpreter flag.
- `0x800DB5BA`: mode state.

## DuckStation debugger procedure

1. Boot game and open debugger/disassembly window.
2. Set execution breakpoints:
   - `0x8001CFA0`
   - `0x8001D354`
   - `0x8001D500`
3. Set memory watchpoint (read/write):
   - `0x800DBA1C` (current script pointer)
4. Run until first tutorial dialogue is active.
5. At each hit, log:
   - `PC`
   - `0x800DBA1C` value
   - word at `*(u16*)0x800DBA1C`
   - nearby words (`+0x00..+0x20`)
6. Correlate these runtime words with `SCEN` chunk/record offsets to finalize:
   - control-code semantics
   - exact line boundaries
   - reliable source-text extraction.

## Why this is useful

This path gives hard evidence of how the game consumes the script stream at
runtime and removes ambiguity caused by mixed control/data records.
