# Langrisser V PS1 patch workspace

This repository contains reproducible scripts to build a `PPF3` patch for the
`SLPS-01818-9-B` PlayStation image.

Canonical documentation:
- `STATUS.md`: current project status and next steps.
- `docs/LANGRISSER_V_DATA_FORMAT.md`: confirmed format findings and RE notes.
- `docs/ENVIRONMENT_BOOTSTRAP.md`: tool bootstrap for environment resets.
- `docs/TUTORIAL_SCREEN_ANCHORS.md`: screenshot-confirmed tutorial text anchors.
- `docs/DUCKSTATION_RUNTIME_PLAN.md`: deterministic runtime-debug plan for
  text/script decode in DuckStation.
- `docs/ALL_TEXT_EXTRACTION.md`: canonical offline extraction workflow from
  game data files (`SCEN/SCEN2/SYSTEM/SLPS`) without savestates.
- `docs/LANG5_SCRIPT_TOOLCHAIN.md`: `lang3`-style dump/insert workflow for
  `SCEN.DAT` / `SCEN2.DAT` with `.tbl` and `<$HHHH>` tags.

Current patch status:
- `patches/langrisser_v_en.ppf` is generated from the clean image.
- Current demo patch replaces executable title string `ラングリッサー５`
  with `LANGRISSER V`.

## Build

```bash
python3 scripts/make_langrisser_v_ppf.py
```

Inputs:
- `iso/SLPS-01818-9-B.bin`

Outputs:
- `work/build/SLPS-01818-9-B.en.bin`
- `patches/langrisser_v_en.ppf`

## Environment bootstrap (after reset)

```bash
./scripts/bootstrap_env.sh
```

## Utility scripts

- `scripts/iso_mode2.py`: list/extract/inject files inside PS1 `MODE2/2352` BIN.
- `scripts/ppf3.py`: generate a `PPF3` patch from original and modified BIN.
- `scripts/make_langrisser_v_ppf.py`: end-to-end patch builder for this project.
- `scripts/lang5_scen_extract.py`: reverse/analyze `SCEN*.DAT` and export
  chunk/record/token data for script work.
- `scripts/lang5_story_extract.py`: export scenario-ordered tokenized dialogue
  and rough JP↔EN sequential alignment.
- `scripts/lang5_infer_lexicon.py`: infer speaker-token prefixes and generate
  partially labeled JP token stream with seed-based token substitutions.
- `scripts/lang5_make_source_dump.py`: build canonical scenario-ordered source
  dump (tokenized JP + aligned EN).
- `scripts/lang5_chunk_probe.py`: inspect records near a chunk-relative offset
  with current token map decoding.
- `scripts/lang5_anchor_report.py`: generate focused report for records with
  anchor names (`ギザロフ`, `ランフォード`) to drive token-map expansion.
- `scripts/lang5_ingame_ocr.py`: OCR helper for `work/ingame` screenshots to
  create reproducible JP anchor text (`work/scen_analysis/ingame_ocr.csv`).
- `scripts/lang5_chunk_struct_probe.py`: inspect runtime-relevant chunk fields
  (`base0`, `+0x30/+0x34/+0x38/+0x3C`) and derived pointers for a target chunk.
- `scripts/lang5_extract_text_segments.py`: extract likely visible script text
  segments using VM text windows (`0003..0004`) from `records.csv`.
- `scripts/lang5_build_tutorial_subset.py`: build screenshot-anchored tutorial
  source subset mapping (`chunk 56` record ids -> JP lines with confidence).
- `scripts/slps_runtime_probe.py`: static probe of `SLPS_018.19` runtime
  interpreter anchors and breakpoint candidates.
- `scripts/lang5_system_table_probe.py`: probe token-like 4-byte lookup tables
  in `SYSTEM.BIN` and compare them with extracted SCEN token sets.
- `scripts/lang5_gdb_remote.py`: minimal DuckStation GDB-remote client for
  deterministic breakpoint/watchpoint setup and RAM/register dumps.
- `scripts/lang5_ram_extract.py`: extract readable token runs from `work/ram.bin`
  using current token map.
- `scripts/lang5_match_runtime_to_records.py`: match runtime token windows from
  savestates back to static `records.csv` entries.
- `scripts/lang5_vm_probe.py`: probe runtime VM entry records from RAM dumps
  (`base+u16-offset` entry model around `0x8001D354`).
- `scripts/lang5_vm_layout_dump.py`: dump VM block layout from `SCEN.DAT`
  (section pointer table, `u16` entry lists, entry headers/opcodes).
- `scripts/lang5_vm_dispatch_dump.py`: dump runtime-populated VM dispatch
  tables (`0x010200`, `0x010250`) from RAM dumps.
- `scripts/lang5_vm_scan_chunks.py`: scan all `SCEN/SCEN2` chunks for VM
  headers and export normalized VM entry lists (no runtime needed).
- `scripts/lang5_vm_text_extract.py`: extract VM-attached text sections and
  resolve `FF00` text ids to record payloads from static `SCEN/SCEN2` data.
- `scripts/lang5_duckstate_extract.py`: parse DuckStation `.sav` (`DUCCS`)
  files, decompress state payload, and extract deterministic 2MB RAM dumps.
- `scripts/lang5_runtime_cache_dump.py`: dump runtime glyph-cache rows from RAM
  (`row_type=vm_u16_list/raw_entry`) for font-table reverse engineering.
- `scripts/lang5_state_struct_dump.py`: offline dump of key runtime text/VM
  globals and pointed buffers from extracted `*_ram.bin` files.
- `scripts/lang5_build_confirmed_source.py`: build deterministic tokenized
  source lines from static VM `FF00 -> text_id` linkage
  (`confirmed_source_tokenized.{csv,txt}`).
- `scripts/lang5_extract_all_texts.py`: unified offline extractor of
  text-bearing token streams from `SCEN.DAT`, `SCEN2.DAT`, `SYSTEM.BIN`,
  and `SLPS_018.19`.
- `scripts/lang5_scrscendump.py`: dump `SCEN/SCEN2` records to editable text
  (`chunk_XXX.txt`) using `.tbl` mapping and `<$HHHH>` tags.
- `scripts/lang5_scrsceninsert.py`: insert edited chunk text files back and
  rebuild `SCEN/SCEN2` containers (offset/pointer tables).
- `scripts/lang5_build_script_ppf.py`: end-to-end script-patch builder
  (`dump edits -> rebuilt SCEN/SCEN2 -> BIN inject -> PPF`).
- `scripts/lang5_runtime_trace_decoder.py`: runtime trace helper for decoder
  control flow from savestates (breakpoint/step modes via DuckStation GDB).
- `scripts/lang5_runtime_watch.py`: runtime write-watchpoint probe for script
  pointers/flags (`0x800DBA1C`, `0x800DB90C`, `0x800DB8D4`).
- `scripts/lang5_build_merged_tbl.py`: build bootstrap `lang5` table from
  `lang3.tbl` with local confirmed token overrides.
- `scripts/bootstrap_env.sh`: one-shot environment recovery after resets.

## Extract script structure and storyline mapping

```bash
python3 scripts/lang5_scen_extract.py
python3 scripts/lang5_story_extract.py
python3 scripts/lang5_infer_lexicon.py
python3 scripts/lang5_make_source_dump.py
```

Outputs in `work/scen_analysis`:

- `summary.json`: high-level findings (diff chunks, magic presence, hints).
- `chunks.csv`: one line per chunk with offsets, table location, FB counts.
- `records.csv`: record-level word streams (hex words) for scripting research.
- `dialogue_candidates.csv`: record subset with strong text-token characteristics.
- `story_map.csv`: practical linkage `Scenario N` -> chunk index.
- `story_ordered.json`: scenario-ordered tokenized JP stream
  (`[XXXX]` tokens + control markers).
- `story_alignment_preview.csv`: sequence-level alignment between
  `story_ordered` records and `translation.txt` lines.
- `speaker_lexicon.json`: inferred speaker-name token prefixes from aligned rows.
- `story_alignment_partial_decode.csv`: same alignment with partial speaker
  labeling plus confirmed JP token substitutions
  (currently seeded from `ランフォード元帥`).
- `source_script_tokenized.txt` and `source_script_tokenized.csv`:
  canonical source dump in scenario order.
- `text_segments.csv` and `text_segments.txt`: text-window extracted source
  segments with chunk/record offsets and `FB00` labels.
