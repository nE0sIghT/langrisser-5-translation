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
