# Langrisser V control tokens (disasm-backed)

Sources:
- `work/scen_analysis/ghidra_vm_text_decode_dump.txt`
- `work/scen_analysis/slps_text.objdump.txt`
- EXE: `work/extracted/SLPS_018.19`

## Core parser path

- `FUN_800a36b4` (`0x800A36B4`) is the central `u16` stream dispatcher.
- It treats:
  - `< 0xE000` as direct printable token path.
  - `0xFFF3..0xFFFF` via jump table at `0x80015BAC`.
  - `0xF6xx..0xFExx` via jump table at `0x80015BE4`.

## Confirmed control semantics

- `F600`:
  - handled in `FUN_800a87e0` (`0x800A87E0`, branch at `0x800A884C`).
  - consumes next word as argument (`param_1[1]`), resolves macro text through
    `func_0x800ada2c`, then emits expanded glyph sequence via `func_0x8008eedc`.

- `FFFC`:
  - explicit branch in `FUN_800a87e0` (`0x800A8854`, `0x800A891C`): writes
    `0xFFFF` line separator to output buffer.
  - special state-branch in `FUN_800b2638` (`0x800B264C`): token `-4` drives UI
    flow/paging return codes (`1/3/4` states).

- `FFFD`:
  - appears as explicit control seed (`li 0xFFFD`) in `FUN_800a3e24`
    (`0x800A3E38`), pushed into local control buffer.
  - in `FUN_800a36b4` dispatch table, `0xFFFD -> 0x800A37F4` state transition
    path (non-printing control branch).

- `FFFE`:
  - termination sentinel in `FUN_800a87e0`: loop stop condition is
    `(word + 2) < 2`, i.e. `0xFFFE` or `0xFFFF`.
  - in `FUN_800a36b4` dispatch table, `0xFFFE -> 0x800A377C`
    (state/control transition, non-printing).

- `FFFF`:
  - terminator/return-control branch in `FUN_800a36b4` table:
    `0xFFFF -> 0x800A3730`.
  - also used as hard separator in many intermediate output buffers.

- `FB00`:
  - `0xFBxx` family is dispatched by `FUN_800a36b4` via `0x80015BE4`
    (`index = high_byte - 0xF6`).
  - for `0xFBxx` (`index 5`) branch target is `0x800A39A4`.
  - this path is non-printing control flow (advances script pointer; optional
    side-call), not direct glyph emission.

## Jump-table maps

`0x80015BAC` (`0xFFF3..0xFFFF`):
- `FFF3 -> 0x800A3944`
- `FFF4 -> 0x800A3920`
- `FFF5 -> 0x800A38F0`
- `FFF6 -> 0x800A38C0`
- `FFF7 -> 0x800A389C`
- `FFF8 -> 0x800A3874`
- `FFF9 -> 0x800A3848`
- `FFFA -> 0x800A381C`
- `FFFB -> 0x800A37BC`
- `FFFC -> 0x800A379C`
- `FFFD -> 0x800A37F4`
- `FFFE -> 0x800A377C`
- `FFFF -> 0x800A3730`

`0x80015BE4` (`0xF6xx..0xFExx`):
- `F6xx -> 0x800A3A90`
- `F7xx -> 0x800A3B00`
- `F8xx -> 0x800A3B00`
- `F9xx -> 0x800A3B00`
- `FAxx -> 0x800A3BFC`
- `FBxx -> 0x800A39A4`
- `FCxx -> 0x800A3B00`
- `FDxx -> 0x800A3A34`
- `FExx -> 0x800A39F8`

