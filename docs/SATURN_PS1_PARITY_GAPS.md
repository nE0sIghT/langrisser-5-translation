# Saturn vs PS1 Build Parity Gaps

This document is a delta report, not another format description. The baseline
format details remain in:

- `README.md` and `AGENTS.md` for the PS1 translation workflow and invariants.
- `docs/SYSTEM_BIN_FORMAT.md` for PS1 SYSTEM text and UI constraints.
- `docs/IMG_DAT_FORMAT.md` for PS1 IMG.DAT graphics.
- `docs/SATURN_DISC_FORMAT.md` for Saturn disc, SCEN, SYSTEM and graphics
  container findings.

The parity target is strict: the Saturn flow should cover the same translation
tasks as the PS1 flow, with shared logic in common modules and only container /
platform adapters kept platform-specific. Extra features such as staff/cast
screens or Virash overlay subtitles are not parity requirements unless the PS1
release flow also patches them.

## Current Matrix

| PS1 flow task | PS1 path | Saturn path | Saturn status | Gap reason | Proposed action |
| --- | --- | --- | --- | --- | --- |
| Source extraction | `iso_mode2.py` extracts PS1 files to `work/extracted/` | `saturn_disc.py extract` extracts Saturn files to `work/build/saturn/` | Partial | Saturn extraction exists, but there is no single Saturn equivalent to the PS1 release/extract bootstrap. | Add a Saturn extraction/bootstrap command or document the required extraction set in one release/build script. |
| No-edit roundtrip | `lang5_verify_roundtrip.py` covers PS1 SCEN/SYSTEM no-edit paths | SCEN no-edit model is documented; SYSTEM and graphics have individual tooling | Partial | Roundtrip proofs are split across tools/docs instead of one mandatory build gate. | Add a Saturn no-edit verification driver that calls the existing per-container checks. |
| Font slots | `lang5_assign_font_slots.py` -> generated assignments -> `lang5_build_font.py` | Saturn build now runs the same generated-assignment stage, then writes `SYSTEM.DAT` glyphs | Implemented | The shared assignment stage uses the PS1 common source and a Saturn build-copy table. | Keep platform-specific SYSTEM overlays sparse; extend allocator source handling only when real Saturn-only strings are added. |
| SCEN text | `lang5_sceninsert.py --fixed-size-repack` writes all PS1 SCEN/SCEN2 text | `lang5_saturn_apply.py` writes Saturn `SCEN.DAT` field_3c pools through strict platform mapping | Strict gated (`100/131` auto, 6 service skipped, 25 blocked) | The remaining blocks are real PS1/Saturn entry-order/content differences. | Add durable `data/platforms/saturn/scen_mapping.json` entries and sparse language overrides where a Saturn entry has no PS1 equivalent. |
| SYSTEM text | `lang5_system_dump.py` -> resolver -> reflow -> strict `lang5_system_pack.py --repack` | `lang5_saturn_system_pack.py` packs all Saturn groups through explicit platform mapping | Implemented (`16/16`) | Saturn-only RAM/save strings and compact Saturn-only class labels are stored as sparse overlays. | Add runtime review rows if any Saturn-only SYSTEM string needs wording changes. |
| Build-copy wrapping | PS1 build rewraps `work/build/translation.<lang>/` with the exact generated `.tbl` | Saturn build rewraps `work/build/translation.<lang>.saturn/` with the Saturn `.tbl` | Implemented | The tracked language pack is never rewritten. | None. |
| Translation validation | PS1 build validates control words, encodability and budgets under exact `.tbl` | Saturn build validates the same generated translation copy under the Saturn `.tbl` | Implemented for common PS1-based text | Platform-specific override validation still depends on adding real override files. | Add validation for sparse Saturn override chunks when they are populated. |
| SYSTEM UI validation | `lang5_validate_system_ui.py` checks atlas rows and fixed-width fields | Saturn build runs the common PS1 SYSTEM UI validator on common strings | Implemented for common strings | Saturn-only SYSTEM overlays are still absent. | Add Saturn-specific constraints when overlays are added or runtime proves a different geometry. |
| Name-entry screen | `lang5_patch_name_entry.py` patches SYSTEM grid and PS1 executable input table | `saturn_name_entry.py` patches two tables in `SYSTEM.DAT` | Static implemented | Display and input tables are located; runtime cursor / OK / cancel behaviour still needs confirmation. | Runtime-check only those behaviours. If it passes, treat the adapter as parity-complete. |
| Title credits | `lang5_imgdat.py title-credits` patches IMG.DAT title assets | `saturn_title_credits.py` patches `TITLE1.DAT` | Implemented | None known for parity; platform container differs. | Keep shared text rendering in common code; keep only detile/retile in Saturn adapter. |
| Prologue poem | `lang5_poem_translate.py` patches IMG.DAT poem assets using shared renderer | `saturn_poem_translate.py` patches `OPEN.DAT[2]` using shared renderer | Implemented | None known for parity; platform container differs. | Keep shared renderer; keep run-atlas packing Saturn-specific. |
| Scenario-clear banner | `lang5_scenario_clear.py` patches IMG.DAT asset 9 using shared banner renderer | `saturn_scenario_clear.py` patches `CLEAR.DAT` | Implemented | None known for parity; platform container differs. | Keep shared banner renderer; keep CLUT/texture container Saturn-specific. |
| Now Loading plate | `lang5_now_loading.py` patches IMG.DAT asset 0 | `saturn_now_loading.py` patches a compressed `SYSTEM.DAT` stream | Static implemented, runtime pending | The codec round-trips and fits, but the edited stream has not been runtime-confirmed after the latest review. | User runtime-checks the translated plate. If it does not appear, locate the alternate source/cache path before changing docs to "done". |
| Disc output | PS1 injects fixed-size files into a copied BIN and emits PPF3 | Saturn remasters mixed-mode BIN/CUE | Partial | Current Saturn output grows track 1 because translated `SCEN.DAT` grows; cue track indices change. | Run a fixed-size audit. If fixed-size is possible, keep cue unchanged; otherwise release xdelta plus generated cue. |
| Release packaging | `scripts/release.sh` emits PPFs, hashes and manifest | No Saturn release script | Missing | Saturn patch format and fixed-size decision are not finalized. | Use xdelta for the Saturn BIN; include the generated cue only if track layout changes. |

## SCEN Divergence Report

The strict Saturn mapper applies 97 blocks by prefix, 3 blocks by unique
stable-token signature (`3`, `9`, `15`), explicitly preserves 6 service chunks,
and fails on 25 real misaligned blocks. Counts below compare Saturn `SCEN.DAT`
field_3c entries with PS1 `SCEN.DAT` text records. No source text is stored
here.

| Chunk | Saturn entries | PS1 records | Delta (`PS1-Saturn`) | First prefix failure | Stable-signature result | Preliminary reason | Proposed analysis |
| ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| 0 | 200 | 204 | +4 | entry 8 speaker differs (`30` vs none) | no exact alignment | PS1-only difficulty selection (`NORMAL`/`HARD`) removed on Saturn. | Map Saturn entries around the deleted records; no Saturn override required. |
| 4 | 130 | 130 | 0 | entry 107 speaker differs (none vs `44`) | no exact alignment | Same count but order/content diverges near the end. | Compare stable-token windows around entries 100-115; likely local reorder or source revision. |
| 10 | 169 | 177 | +8 | entry 78 speaker differs (`96` vs `97`) | no exact alignment | Multiple PS1-only records or Saturn merges before entry 78. | Build an LCS map and inspect unmatched PS1 records. |
| 11 | 142 | 146 | +4 | entry 58 speaker differs (`71` vs `72`) | ambiguous (`>=2`) | Stable tokens are insufficiently unique. | Add stronger alignment features: speaker, control signature and record length. |
| 16 | 140 | 156 | +16 | entry 46 speaker differs (`72` vs `83`) | no exact alignment | Large PS1/Saturn record-count delta. | Classify whether PS1 has extra tutorial/event records or Saturn combines them. |
| 17 | 113 | 116 | +3 | entry 98 speaker differs (`75` vs `71`) | ambiguous (`>=2`) | Small delta but repeated stable signatures. | Resolve with speaker/control-aware dynamic alignment. |
| 19 | 153 | 157 | +4 | entry 32 speaker differs (`178` vs none) | no exact alignment | PS1-only non-spoken or service entries likely start before entry 32. | Identify unmatched records and decide whether translation unit exists on Saturn. |
| 20 | 114 | 122 | +8 | entry 16 speaker differs (`39` vs none) | no exact alignment | Early record-count delta. | Compare early event/control records and classify PS1-only material. |
| 21 | 105 | 111 | +6 | entry 83 speaker differs (`26` vs none) | no exact alignment | Late PS1-only/service records likely. | Inspect around entries 75-90 with control signatures. |
| 22 | 123 | 127 | +4 | entry 75 speaker differs (`64` vs none) | no exact alignment | Delta appears after first half. | LCS by stable tokens plus speaker IDs. |
| 24 | 254 | 255 | +1 | entry 95 speaker differs (`54` vs none) | no exact alignment | Single PS1-only record breaks index alignment. | Find the lone unmatched record; this should be a high-priority easy map. |
| 25 | 137 | 139 | +2 | entry 41 speaker differs (`115` vs none) | no exact alignment | Small early/mid delta. | Locate two unmatched PS1 records and classify. |
| 26 | 151 | 155 | +4 | entry 37 speaker differs (`99` vs none) | no exact alignment | Small early/mid delta. | LCS by stable tokens plus control signature. |
| 27 | 106 | 110 | +4 | entry 74 speaker differs (`29` vs none) | no exact alignment | Delta appears late. | Inspect unmatched tail records. |
| 28 | 139 | 144 | +5 | entry 45 speaker differs (`65` vs `81`) | no exact alignment | Speaker sequence diverges, not only non-spoken records. | Treat as potential source revision; compare speaker timeline. |
| 29 | 200 | 201 | +1 | entry 60 speaker differs (`163` vs none) | no exact alignment | Single PS1-only record breaks index alignment. | Find the lone unmatched record; likely easy map. |
| 30 | 103 | 105 | +2 | entry 21 speaker differs (`78` vs `50`) | no exact alignment | Early speaker sequence diverges. | Compare speaker/control timeline; check for platform text revision. |
| 31 | 129 | 136 | +7 | entry 30 speaker differs (`91` vs `93`) | no exact alignment | Medium early delta. | LCS and unmatched-record classification. |
| 32 | 99 | 112 | +13 | entry 15 speaker differs (`16` vs none) | no exact alignment | Large early delta. | Do not auto-map until source difference is classified. |
| 33 | 130 | 140 | +10 | entry 32 speaker differs (`35` vs none) | no exact alignment | Medium early delta. | LCS and source-difference classification. |
| 34 | 95 | 100 | +5 | entry 29 speaker differs (`46` vs `176`) | no exact alignment | Speaker sequence diverges. | Compare speaker timeline; possible event/source revision. |
| 35 | 82 | 86 | +4 | entry 19 speaker differs (`20` vs none) | no exact alignment | Early PS1-only/service records likely. | Inspect early unmatched records. |
| 38 | 372 | 371 | -1 | entry 371 has no PS1 record | no exact alignment | Saturn has one extra record. | Classify Saturn-only entry; do not drop it silently. |
| 40 | 126 | 135 | +9 | entry 63 speaker differs (`44` vs none) | no exact alignment | Mid-script delta. | LCS and unmatched-record classification. |
| 80 | 292 | 307 | +15 | entry 9 speaker differs (`1` vs none) | no exact alignment | Large early delta. | High-priority source-difference analysis; likely many PS1-only service/event records. |

Service chunks that are intentionally not language-pack chunks:

| Chunk | Saturn entries | PS1 records | Current state | Action |
| ---: | ---: | ---: | --- | --- |
| 43 | 8 | 8 | Name-pool/dummy block: Sigma, Lambda, Clarett, Alfred, Brenda, Lanford Marshal, two bullet terminators. | Listed in `empty_chunks`; preserved. |
| 44 | 8 | 8 | Same service block. | Listed in `empty_chunks`; preserved. |
| 81 | 8 | 8 | Same service block. | Listed in `empty_chunks`; preserved. |
| 123 | 8 | 8 | Same service block. | Listed in `empty_chunks`; preserved. |
| 127 | 8 | 8 | Same service block. | Listed in `empty_chunks`; preserved. |
| 128 | 8 | 8 | Same service block. | Listed in `empty_chunks`; preserved. |

## SYSTEM Divergence Report

The Saturn SYSTEM packer now translates all 16 text tables in strict mode. The
tables below were the structural blockers and are now covered by
`data/platforms/saturn/system_mapping.json`. Table numbers are only local report
indices; use offsets for durable references.

| Saturn table | PS1 table | Saturn count | PS1 count | Resolved action | Notes |
| ---: | ---: | ---: | ---: | --- | --- |
| `0x08084` | `0x08052` | 292 | 291 | Mixed direct PS1 map, explicit `preserve` for the name-entry grid/control runs, and Saturn overlays for `START`/RAM labels. | `saturn_name_entry.py` rewrites the preserved grid after SYSTEM packing. |
| `0x09004` | `0x08FAE` | 44 | 41 | Saturn-only RAM/save text overlay. | Decorative separator entry is preserved. |
| `0x0A854` | `0x0A8EC` | 33 | 33 | Direct map plus two compact Saturn-only RU labels to fit the fixed group budget. | The group now fits in 159 words. |
| `0x16D3C` | `0x16DC0` | 88 | 92 | Four explicit PS1 range mappings covering the reordered command-help blocks. | No Saturn-only target text needed. |

## Common-Layer Refactor Targets

These are analysis findings, not implementation steps already taken.

| Area | Current state | Gap | Target shape |
| --- | --- | --- | --- |
| Font assignment | Both PS1 and Saturn builds generate build-copy assignments. | Saturn-only overlay strings are not yet fed into assignment source. | Add platform overlay source handling when real overrides are populated. |
| Rewrap/validate | Both PS1 and Saturn builds rewrap/validate build copies with the exact generated table. | Sparse platform override chunks are not yet validated because none are populated. | Validate platform override chunks when added. |
| SYSTEM resolving | Saturn build regenerates the PS1 common SYSTEM source/resolved map before packing. | Implemented for current known Saturn SYSTEM deltas. | Extend `data/platforms/saturn/system_mapping.json` only if new Saturn-only SYSTEM strings are identified. |
| Graphics rendering | Title, poem, clear and Now Loading already reuse several render cores. | Container adapters still import PS1 image helpers directly in places. | Keep rendering/palette helpers common; keep only container decode/encode per platform. |
| Release | PS1 has `release.sh`; Saturn has only ad-hoc remastered BIN/CUE output. | No reproducible release artifact. | Add Saturn release mode after fixed-size audit; use xdelta as the binary patch format. |

## Fixed-Size vs Remaster Audit

The PS1 invariant is that edited files keep their file-level size and the `.cue`
does not change. The current Saturn remaster grows `SCEN.DAT`, which shifts
track indices. That may be a current strategy rather than a hard requirement.

Required analysis before deciding release shape:

1. Measure the translated size pressure per Saturn SCEN block after all mapping
   gaps are resolved.
2. Check whether Saturn `SCEN.DAT` has enough internal padding / reallocatable
   block space for a fixed-size file-level repack.
3. Check whether `SYSTEM.DAT`, `TITLE1.DAT`, `OPEN.DAT`, `CLEAR.DAT` and the Now
   Loading stream stay fixed-size after final parity changes.
4. If all edited files can stay fixed-size, emit xdelta for the `.bin` and keep
   the original `.cue`.
5. If `SCEN.DAT` must grow, emit xdelta for the remastered `.bin` and distribute
   the generated `.cue`.

## Runtime Checks Needed

Only checks with real remaining risk are listed:

| Area | Real risk | Check owner |
| --- | --- | --- |
| Saturn name entry | Display grid and input table might not cover cursor order, OK/cancel, or a hidden whitelist. | Runtime check by user. |
| Saturn Now Loading | Static stream decode/encode is implemented, but edited stream use is not yet confirmed after review. | Runtime check by user. |
| Remastered Saturn image | If fixed-size is not achieved and tracks shift, the generated cue/remaster must boot and reach affected scenes. | Runtime check by user after build artifact exists. |

## Patch Format

Use `xdelta3` for Saturn. It works for both fixed-size and remastered/grown BIN
outputs. The release shape depends on the fixed-size audit:

- Fixed-size output: `langrisser_v_saturn_<lang>.xdelta`; original `.cue`
  unchanged.
- Remastered output: `langrisser_v_saturn_<lang>.xdelta` plus generated
  `langrisser_v_saturn_<lang>.cue`.

PPF is not the preferred Saturn release format because the current Saturn path
may change BIN size and cue track indices. BPS is possible but less attractive
for large CD images.

## Next Analysis Tasks

1. Fill `data/platforms/saturn/scen_mapping.json` for the 25 strict SCEN
   failures.
2. Add validation for populated sparse platform override chunks/strings.
3. Re-run strict `python3 scripts/lang5_saturn_build.py --lang <lang>`; use
   `--allow-unmapped` only to exercise downstream container stages.
