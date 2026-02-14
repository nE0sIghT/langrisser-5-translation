# Langrisser V PS1 Data Format Notes

Last updated: 2026-02-14 (savestate+RAM extraction update)

This file is the canonical technical reference for discovered data formats in
this repository. Update this file when new reverse-engineering facts are
confirmed.

## Scope

- Disc image: `SLPS-01818-9-B` (PS1, MODE2/2352 BIN).
- Main data files under active RE:
  - `SCEN.DAT`
  - `SCEN2.DAT`
  - `SYSTEM.BIN`

## Container and chunking

### `SCEN.DAT` / `SCEN2.DAT`

- Container consists of 131 chunks.
- File header sector (`0x800` bytes) stores LE32 chunk pointers.
- Pointers are chunk starts; end is determined by next pointer.
- Chunks are sector-aligned (`0x800`) and padded on rebuild.
- Historical tool behavior (`l5scen.py`) matches this layout.

Practical extraction path:
- `scripts/lang5_scen_extract.py`
- `scripts/lang5_story_extract.py`

### Chunk internals (current confidence: medium/high)

- Each chunk contains mixed event/script data, not pure text.
- Inside chunks there is a local 16-bit increasing offset table used for
  record boundaries.
- Records contain mixed control words and text-like token words.
- Frequent control words/markers seen in record streams:
  - `FFFF` (end marker in many short text records)
  - `FFFC`, `FFFD`, `FFFE`
  - `FB00` (dialog/event orchestration contexts)

Confirmed practical text-window pattern:
- Visible dialogue text is commonly inside `0003 ... 0004`.
- Segments often terminate early on `FFFC/FFFD/FFFE/FB00`.
- `FB00` is commonly followed by a script label/id token.
- This provides a stable extraction layer even before full command grammar.
- Extractor:
  - `scripts/lang5_extract_text_segments.py`
  - outputs: `work/scen_analysis/text_segments.{csv,txt}`

New confirmed runtime linkage:
- Savestate runtime windows extracted at interpreter hit (`0x8001D198`) can be
  matched back to static SCEN records by token-overlap.
- Example confirmed window:
  - `00C6 00CD 00B2 0086 00D1 00A6 020E 020F FFFF`
  - decoded: `ランフォード元帥{FFFF}`
  - matched records: `chunk 125/129/130`, `record 5`
- Matching tool:
  - `scripts/lang5_match_runtime_to_records.py`

Observed recurring sequence (likely script/data boundary marker):

`01 00 00 01 80 00 00 00 78 80 70 80 30 30 01 02 78 78 00 13 28 13 38 38 02 00 A0 A0 00 10 18 10`

## Text token encoding model

Current confirmed model:

- Text stream is 16-bit little-endian words.
- Logical token id is word value `0xHHLL` (hex), where high byte acts as bank.
- In old notes this is described as "bank suffix", i.e. bank follows base char
  in serialized bytes.

Confirmed community example, validated in data:

- `ランフォード元帥{end}`
- words: `00C6 00CD 00B2 0086 00D1 00A6 020E 020F FFFF`
- bytes in file (LE words):
  `C6 00 CD 00 B2 00 86 00 D1 00 A6 00 0E 02 0F 02 FF FF`

## Known character mapping

Canonical manual map:

- `scripts/lang5_token_map_manual.json`

Current map confidence:

- High for katakana/punctuation block recovered from `SYSTEM.BIN`.
- Includes deterministic map for:
  - Katakana rows (`ア..ワ/ン`)
  - Dakuten/handakuten rows
  - small kana (`ァィゥェォャュョッ`)
  - punctuation (`、。・ー`)
  - confirmed kanji tokens: `元`, `帥`
  - confirmed honorific/name-suffix token: `02B0 -> 様`

Cross-game seed table result (`lang3.tbl` -> `lang5`):
- `external/lang3/scripts/jp/lang3.tbl` parsed as CP932 provides 1693 token
  entries.
- Coverage against current `SCEN` record token universe is high:
  - `1597 / 1752` unique tokens hit.
- But semantic drift exists:
  - Even after forcing 7 known corrections (`、。・ー元帥様`), many lines still
    decode into plausible but wrong kanji/words.
  - Conclusion: token ids are close between L3/L5 but not globally identical in
    glyph assignment; direct reuse is useful as a bootstrap only.
- Merge builder:
  - `scripts/lang5_build_merged_tbl.py`
  - output example: `work/tables/lang5_merged.tbl`

## `SYSTEM.BIN` findings

- FEIDIAN dump command used successfully:
  - `php -d short_open_tag=1 feidian.php -r 12,12,32,57,0x0 /workspace/work/extracted/SYSTEM.BIN /workspace/work/font_probe/l512x12qg8`
- A deterministic character table block exists in `SYSTEM.BIN` around
  token-run offset `0x008C02` (in decoded run output), used to derive much of
  the manual katakana map.
- `SYSTEM.BIN` also stores large name/class/menu-like text blocks and token
  runs (not only graphics/resources).
- Additional table candidate at `SYSTEM.BIN` offset `0x178B0`:
  - 4-byte entries (`u16 + byte + byte`), 256 entries.
  - `u16` values intersect strongly with known script token ids.
  - Current interpretation: likely script/UI helper lookup table, not proven as
    the global `token -> glyph` table yet.
  - Probe script: `scripts/lang5_system_table_probe.py`
  - Output: `work/scen_analysis/system_table_probe.txt`

Utility:
- `scripts/lang5_system_extract.py`

## RAM dump findings (`work/ram.bin`)

Direct RAM-token extraction (no OCR) confirms that active runtime memory holds
large readable JP token runs with current mapping, including class/menu names.

Examples confirmed from `work/scen_analysis/ram_token_runs.csv`:
- `ダークファイター`
- `ストーンゴーレム`
- `グラディエーター`
- `ブロンズゴーレム`
- `メモリーカード`

Extractor:
- `scripts/lang5_ram_extract.py`

Confirmed runtime token-table blocks (from extracted `*_ram.bin`):
- `0x80108910` (`0x600` bytes)
- `0x80108B02` (`0x600` bytes)
- `0x80108C68` (`0x800` bytes, active table pointer from `gp+0xE38`)

Observed active-entry layout at `0x80108C68`:
- 512 entries of 4 bytes each
- entry bytes: `[u16 glyph_id][u8 attr_b2][u8 attr_b3]`
- state behavior:
  - menu state (`SLPS-01819_5_ram.bin`): table is zeroed
  - dialogue/quiz states (`SLPS-01819_{1,6}_ram.bin`): table is populated

Deterministic dumper:
- `scripts/lang5_dump_runtime_token_table.py`
- outputs:
  - `runtime_token_table_*_active_80108C68.csv`
  - `runtime_token_table_*.json`
  - raw bins for `0x80108910/0x80108B02/0x80108C68`

Confirmed runtime resource descriptor table:
- address: `0x8010DB40`
- entry size: `0x18` bytes
- entry layout:
  - `u32 cdloc` (`MM:SS:FF` in BCD + mode byte, packed little-endian)
  - `u32 size_bytes`
  - `char name[12]` (ISO9660-style, e.g. `SYSTEM.BIN;1`)
  - `u32 tail` (currently always `0` in observed rows)
- confirmed names include:
  - `SYSTEM.BIN;1`
  - `BTLDAT.BIN;1`
  - `MRCUSW.BIN;1`
  - `SCEN.DAT;1`
  - `ALLUSW.BIN;1`
  - `ALLUSB.BIN;1`
  - `SCEN2.DAT;1`
- for these rows, `size_bytes` matches extracted files exactly.
- executable conversion is confirmed:
  - `FUN_800B91F0`: `CDLOC(Bcd) -> LBA`
    - `LBA = ((MM*60 + SS)*75 + FF) - 150`
  - `FUN_800B90EC`: inverse conversion `LBA -> CDLOC(Bcd)`
  - loader callsite:
    - `FUN_80019FB4` computes descriptor pointer (`index*0x18 + 0x8010DB40`)
      and calls `FUN_800B91F0`.
    - `FUN_8001A9B8` runs async read state machine and uses `FUN_800B90EC`
      before issuing CD commands.
- external verification:
  - decoded LBA and `size_bytes` match ISO9660 entries from
    `scripts/iso_mode2.py list` for all 15 named descriptor rows.
- dumper:
  - `scripts/lang5_dump_resource_descriptors.py`
  - output example: `work/scen_analysis/resource_descriptors_state1.csv`

## `SCEN` vs `SCEN2`

- Chunk-level diff shows divergence in chunks:
  - `1..36`, `40..42`
- This matches likely route/late-game variation, while other chunks are shared.

## Confirmed dialogue anchor (screenshots)

- A strong candidate for early in-game tutorial dialogue is in:
  - `SCEN.DAT` chunk `56`, around chunk-relative offset `0x5488`
- In this area, records include:
  - `ギザロフ[02B0]。`
- This supports treating `02B0` as a high-confidence name-suffix token in many
  dialogue contexts (likely honorific usage) and ties observed dialogue style
  to SCEN record streams rather than names-only tables.

OCR-backed screenshot anchors (from `work/ingame`, timestamp order):
- `ギザロフ様。`
- `まず最終成長形態の設定を行います。`
- `４つの金属の中から、３つを培養液に混ぜ合わせます。不要な物を選んで下さい。`

Reproducible extraction:
- `scripts/lang5_ingame_ocr.py`
- output: `work/scen_analysis/ingame_ocr.csv`

Current mapping assessment:
- Chunk-window locality and progression (`rec 22..26`, `0x547E..0x54FC`) is
  high confidence.
- Exact 1:1 "line -> record" mapping in this window is still medium confidence
  until chunk grammar around command/control words is finalized.

## What is still unresolved

- Exact runtime source and load path for the full `token -> glyph` table used
  during dialogue rendering.
- Full expansion model for high-value narrative tokens (many non-katakana
  tokens appear to represent compact dictionary/text units, not only
  single-glyph characters).
- Full hiragana mapping.
- Broad kanji coverage for narrative lines.
- Exact delimiter/structure for "pure dialogue block start/end" inside each
  chunk (currently parse is record-based and robust enough for extraction, but
  not yet complete formal grammar).
- 100% validated mapping of early tutorial lines from screenshots to exact
  token runs and offsets.

## Script/output map

- Structural extraction:
  - `scripts/lang5_scen_extract.py`
  - outputs in `work/scen_analysis/{chunks.csv,records.csv,dialogue_candidates.csv,summary.json}`
- Story ordering and alignment:
  - `scripts/lang5_story_extract.py`
  - `scripts/lang5_infer_lexicon.py`
  - `scripts/lang5_make_source_dump.py`
- Font-map application:
  - `scripts/lang5_apply_font_ocr_map.py`
- Ingame OCR helper:
  - `scripts/lang5_ingame_ocr.py`
- SYSTEM token run extraction:
  - `scripts/lang5_system_extract.py`
- SYSTEM table probe:
  - `scripts/lang5_system_table_probe.py`
- RAM token-run extraction:
  - `scripts/lang5_ram_extract.py`
- Runtime-window -> record matching:
  - `scripts/lang5_match_runtime_to_records.py`
- Runtime resource-descriptor dump:
  - `scripts/lang5_dump_resource_descriptors.py`
- Unified offline all-text extraction:
  - `scripts/lang5_extract_all_texts.py`
  - output: `work/scen_analysis/all_texts.csv`
  - source files: `SCEN.DAT`, `SCEN2.DAT`, `SYSTEM.BIN`, `SLPS_018.19`

## Runtime RE anchors (SLPS)

- Confirmed interpreter loop and end marker behavior:
  - `0x8001CFA0`, `0x8001D174`, `0x8001D500` (`0xFFFF` checks)
- Confirmed runtime state variables in `0x800E....` small-data area:
  - `script_ptr_current @ 0x800DBA1C`
  - `script_base_table @ 0x800DB90C`
  - `interpreter_flag @ 0x800DB8D4`
  - `mode_state @ 0x800DB5BA`
- Confirmed in-module table pointer init:
  - `0x80018448: sw v0, 0xE38($gp)` with `v0 = 0x80108C68`
- In current SLPS image, writes to `0x800DB780` (font bitmap base pointer) are
  not present; only reads are observed in the main module, implying external
  runtime initialization path (other module/loader stage).

### Interpreter shape around `0x8001D354` (new, medium/high confidence)

Inside the `0x8001D198` flow, core loop `0x8001D354..0x8001D5A8` shows a
two-level script VM shape:

1. `a1 = script_ptr_current (0x800DBA1C)` points to a stream of `u16` items.
2. For each item:
   - read `rel = *(u16*)a1`
   - compute `entry = script_base (0x800DB90C) + rel`
   - store parser cursor `gp+0x30C = entry+2`
3. `*(u16*)entry` is used as a "visited/guard" id:
   - checked/updated through bitset table at `0x8011A920`.
4. `*(u8*)(entry+2)` is an opcode (`0..8`) dispatched via jump table at
   `0x80010228`:
   - handlers include calls to `0x80022C04/0x80022E2C/0x80023340/0x80023938/...`
5. One handler (`0x8001D3F0`) parses extra args (`u8`,`u16`) and validates via:
   - bit table `0x8011AA41`
   - limit table `0x8011AA28`
6. If event flag `0x800DB8D4` is raised, VM transitions to a bytecode pass
   (`0x8001D698...`) with byte dispatch table at `0x80010250`.

Implication:
- Many record units are command/event entries, not direct plain text runs.
- This supports the observed macro/dictionary-like compact token behavior in
  narrative lines.

### Savestate RAM structure dump (new)

- Added offline analyzer for already-extracted RAM dumps (no live emulator
  attach needed):
  - `scripts/lang5_state_struct_dump.py`
- It dumps:
  - key global pointers (`0x800DB90C/0x800DBA1C/0x800DB34C/0x800DB508/0x800DB4EC/0x800DB538/0x800DB380`)
  - current VM rel-list around `script_cur`
  - resolved entry records (`head/op/arg/words`)
  - nonzero statistics and byte snapshots for `0x80108910/0x80108B02/0x80108B2E/0x80108BC8`.
- Current observation from `SLPS-01819_{1,6}_ram.bin`:
  - `script_cur` starts with `FFFF` padding then valid rel offsets.
  - First active rels decode to VM entries including `FF00` dispatch ids and
    opcode records.
  - `0x80108B02/0x80108B2E/0x80108BC8` are runtime scratch/candidate buffers,
    not yet proven as immutable global font tables.

### Runtime VM block mapped back to `SCEN.DAT` (new, high confidence)

From savestate `SLPS-01819_6.sav`:
- `script_base @ 0x800DB90C = 0x80169040`
- `script_cur  @ 0x800DBA1C = 0x80169086`

RAM dump at `0x80169040` (`0x20000` bytes sampled) matches file bytes exactly
at:
- `SCEN.DAT` offset `0x840` (decimal `2112`)
- also identical in `SCEN2.DAT` for this block

This places the active VM block in chunk `0`:
- chunk `0` range: `0x800..0xB000`
- local offset in chunk `0`: `0x40`

Mapped block header (`SCEN.DAT@0x840`) begins with:
- section pointers (`u32`) at `+0x00`:
  `0x44,0x48,0x4A,0x4C,0x4E,0x50,0x52,0x54,0x56,0x58,0x5A`
- additional pointers/params at `+0x2C..+0x3C`:
  `0x5C,0xA8,0xA8,0x00000007,0x00001AB4`

Observed list encoding:
- pointer targets contain `u16` entry offsets terminated by `0xFFFF`.
- example at `+0x44`: `[0x00A8, 0xFFFF]`.
- richer list at `+0x5C`: 37 entry offsets terminated by `0xFFFF`.

Entry head shape (consistent with `0x8001D7B4` loop):
- `u16 flags_or_guard_id` at `entry+0`
- `u8 opcode` at `entry+2`
- opcode-specific payload from `entry+3` onward.

Tooling:
- `scripts/lang5_vm_layout_dump.py` dumps this structure into:
  - `work/scen_analysis/vm_layout_summary.txt`
  - `work/scen_analysis/vm_layout_section_entries.csv`

### Runtime-populated dispatch tables (new, high confidence)

In `SLPS_018.19` file image, dispatch slots around `0x80010200` are zeroed, but
in RAM they are populated at runtime.

From `work/ram.bin`:
- main table @ `0x00010200`:
  - `0 -> 0x8001D040`
  - `1 -> 0x8001D05C`
  - `2 -> 0x8001D0DC`
  - `3 -> 0x8001D0EC`
  - `4 -> 0x8001D0FC`
  - `5 -> 0x8001D10C`
  - `6 -> 0x8001D12C`
  - `7 -> 0x8001D13C`
  - `8 -> 0x8001D14C`
  - `10 -> 0x8001D3D4`
  - `11 -> 0x8001D3F0`
  - `12 -> 0x8001D478`
  - `13 -> 0x8001D488`
  - `14 -> 0x8001D498`
  - `15 -> 0x8001D4A8`
- secondary table @ `0x00010250`:
  - starts with `0x8001D738, 0x8001D764, 0x8001D7D0, ...`
  - includes branch handlers at
    `0x8001D89C`, `0x8001D8CC`, `0x8001D960`,
    `0x8001D9A8`, `0x8001DA4C`, `0x8001DA9C`, `0x8001DADC`.

Tool:
- `scripts/lang5_vm_dispatch_dump.py`
- output: `work/scen_analysis/vm_dispatch_tables.csv`

### Static VM-to-text section mapping (new, high confidence)

Confirmed on `SCEN.DAT` and `SCEN2.DAT` for all 131 chunks:

1. Chunk-local VM block:
   - `vm_off = u32(chunk+0x00)`
   - VM header signature at `chunk+vm_off` starts with `0x00000044`.
   - `vm_size = u32(chunk+vm_off+0x3C)`.

2. Text section placement:
   - `text_sec_off = vm_off + vm_size`.
   - `text_sec_size = u32(chunk+text_sec_off)`.
   - section fits inside chunk (`text_sec_off + text_sec_size <= chunk_size`).

3. Text section internal layout (current best model):
   - monotonic `u16` offset table starts at `text_sec_off + 2`
     (first entry is commonly `0x0000`).
   - text payload base:
     - `text_data_base = text_sec_off + 2 + 2 * offset_count`.
   - text record `id` bytes:
     - start `text_data_base + offsets[id]`
     - end   `text_data_base + offsets[id+1]`.

4. VM entry linkage:
   - many VM entries contain `FF00 <id>` markers.
   - these `<id>` values resolve directly to records in the text section above.

Concrete chunk-0 example (`SCEN.DAT`):
- `vm_off=0x40`
- `vm_size=0x1AB4`
- `text_sec_off=0x1AF4`
- `text_sec_size=0x1FC0`
- offset count observed: `205`
- resolved `FF00` ids include `0001`, `0005`, `000B`, `0037`, `00C2`.

Tooling:
- VM scan:
  - `scripts/lang5_vm_scan_chunks.py`
  - outputs:
    - `work/scen_analysis/scen_vm_chunks.csv`
    - `work/scen_analysis/scen_vm_entries.csv`
    - `work/scen_analysis/scen2_vm_chunks.csv`
    - `work/scen_analysis/scen2_vm_entries.csv`
- VM text extraction and id linkage:
  - `scripts/lang5_vm_text_extract.py`
  - outputs:
    - `work/scen_analysis/scen_vm_texts.csv`
    - `work/scen_analysis/scen_vm_ff00_links.csv`
    - `work/scen_analysis/scen2_vm_texts.csv`
    - `work/scen_analysis/scen2_vm_ff00_links.csv`

## DuckStation runtime instrumentation

- DuckStation AppImage was extracted (`external/squashfs-root`) and runs
  reliably in headless CI-like conditions via `Xvfb` + `QT_QPA_PLATFORM=xcb`.
- GDB server is confirmed operational on `127.0.0.1:9012` when enabled in
  `settings.ini` (`[Debug] EnableGDBServer=true`).
- A deterministic low-level client is now available:
  - `scripts/lang5_gdb_remote.py`
  - Implements direct GDB-remote packets (`?`, `g`, `m`, `Z/z`, `c`, `^C`)
    without relying on `gdb-multiarch` front-end behavior.
- Confirmed protocol behavior from source:
  - on client connect, emulator is paused (`PauseSystem(true)`).
  - `c` resumes execution.
  - stop events arrive as `S00` packets.
- Current runtime result:
  - break/watch plumbing is verified end-to-end.
  - during automated key-input runs under `Xvfb`, execution breakpoints
    `0x8001CFA0/0x8001D198` were not hit yet.
  - this means those anchors are likely not reached in the automated flow
    (boot/menu path divergence), not that GDB instrumentation is broken.

Additional runtime watchpoint probe:
- New probe script:
  - `scripts/lang5_runtime_watch.py`
- Write-watchpoints were set on:
  - `0x800DBA1C` (script current)
  - `0x800DB90C` (script base)
  - `0x800DB8D4` (interpreter flag)
- For provided savestates (`SLPS-01819_1..4.sav`), this probe produced 0 hits.
  - Interpretation: these states are likely parked in a loop that does not
    mutate script pointers while sampled, so they are insufficient for dynamic
    opcode-path capture.
- Extended probe on new states (`SLPS-01819_5.sav`, `SLPS-01819_6.sav`) also
  produced 0 write-watch hits on these pointers.
- Execute-breakpoint traces on `SLPS-01819_6.sav` confirm active loop through:
  - `0x8001D19C`, `0x8001D1FC`, `0x8001D200`, `0x8001D208`,
    `0x80047888`, `0x8001D20C`, `0x8001D280`, `0x8001D29C`
  but still no transitions to `0x8001D354/0x8001D3D4/0x8001D4xx` in that
  runtime slice.

### DuckStation `.sav` (`DUCCS`) state-data extraction

From DuckStation source (`SAVE_STATE_HEADER`), `.sav` layout is:
- fixed header (`magic=DUCC`, version, serial/title, offsets/sizes)
- compressed `state_data` block at `offset_to_data`
- compression type enum:
  - `0=None`, `1=Deflate`, `2=Zstandard`, `3=XZ`

For provided Langrisser V savestates (`SLPS-01819_1..6.sav`):
- version: `83`
- data compression: `Zstandard`
- decompressed `state_data` size: typically `3,833,298` bytes

Deterministic RAM extraction:
- scan `state_data` for Bus MEMCTRL prefix:
  - `u32 exp1_base = 0x1F000000`
  - `u32 exp2_base = 0x1F802000`
- infer `ram_start = memctrl_offset - 0x200000`
- on current states, `ram_start` is stable: `0x1A62`

Tool:
- `scripts/lang5_duckstate_extract.py`
- outputs:
  - `work/scen_analysis/SLPS-01819_*_state_data.bin`
  - `work/scen_analysis/SLPS-01819_*_ram.bin`

### Runtime glyph-cache anchors (RAM)

Observed stable runtime anchors in extracted RAM:
- `0x800DB90C` -> context pointer (e.g. `0x80169040`)
- glyph-entry table pointer in nearby globals, currently at `0x800DB914`
  (e.g. `0x80108C68`)

Current extractor model:
- `context + 0x5C` exposes a VM-side `u16` list present in script data
  (observed in current states; semantics still under RE).
- glyph table rows are `4-byte` entries at `glyph_table_ptr + slot*4`.
- extracted deterministically from savestate RAM, no OCR/input needed.

Tool:
- `scripts/lang5_runtime_cache_dump.py`
- output:
  - `work/scen_analysis/runtime_cache_dump.csv`
  - includes:
    - `row_type=vm_u16_list` (VM-side `u16` list from context block)
    - `row_type=raw_entry` (full raw glyph table rows for low-level RE)

Note:
- VM-side `u16` list values are not yet proven to be direct script token ids or
  direct glyph-cache indices.
- exact semantic meaning of 4 bytes per glyph-entry is not finalized yet
  (field extraction is stable; interpretation is pending).

### Confirmed source stream builder (static, deterministic)

Given confirmed mapping:
- VM entry contains `FF00 <text_id>`
- `<text_id>` resolves into chunk-local VM text section record

we can produce a deterministic tokenized source stream without runtime input:
- first-seen `FF00` calls in VM entry order (`SCEN.DAT`)
- resolve each to exact `words_hex` payload

Tool:
- `scripts/lang5_build_confirmed_source.py`

Outputs:
- `work/scen_analysis/confirmed_source_tokenized.csv`
- `work/scen_analysis/confirmed_source_tokenized.txt`
