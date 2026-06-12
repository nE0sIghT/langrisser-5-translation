# Agent instructions

Toolkit for translating Langrisser V (PS1, SLPS-01818). Read `README.md`
first for the human translation workflow; `docs/PLAN.md` holds the verified
format notes. This file lists the rules that must not be broken.

## Hard invariants

- **File sizes never change.** The disc has CD audio right after the data
  track. Never call `iso_mode2.py` with `--allow-grow`; never let
  `SCEN.DAT`/`SCEN2.DAT`/`SYSTEM.BIN` grow. Text growth first uses the
  chunk's trailing zero padding; beyond that the fixed-size repack
  relocates chunks inside the file (validator status `REPACK` is fine as
  long as the file-level totals stay `OK`).
- **Font atlas ends at glyph 1820.** Tiles 1821+ in `SYSTEM.BIN` are a menu
  offset table, not glyphs. Writing there breaks menus.
- **Control words are sacred.** Every `<$XXXX>` tag ≥ `0xE000` (except the
  soft breaks `FFFC`/`FFFD` and highlight toggles `FFF4`/`FFF3`) and every
  argument word of `F600`/`FBxx` must survive translation in order.
  `lang5_validate_en.py` enforces this — keep it green.
- **SCEN and SCEN2 text blocks are byte-identical.** Translate
  `data/translation/en/SCEN/` only; the build syncs SCEN2.
- **No partially translated chunks in `data/translation/en/`.** Untranslated
  kanji whose glyph slots were sacrificed for Latin pairs fail the encode
  step and break the build. Work-in-progress lives in `work/wip_en/`
  (`lang5_tm_prefill.py` writes there).

## Mandatory checks before claiming success

```bash
python3 scripts/lang5_verify_roundtrip.py   # byte-identical no-edit pipeline
python3 scripts/lang5_rewrap.py             # window-width line wrapping
python3 scripts/lang5_validate_en.py        # tags, encodability, budgets
python3 scripts/lang5_build_ppf.py          # full build must succeed
```

## Translation conventions

- Source of meaning: the JP dump in `work/scriptdump/`. `translation.txt`
  (borgor's GameFAQs guide) may be copied verbatim where its wording fits
  the JP line and the byte budget; otherwise rephrase.
- Names and terms: `data/translation/names_base.csv` and
  `data/translation/glossary_names.csv` are canonical; follow the
  Langrisser fan canon for series terms.
- Text windows (dialogue, narration/briefing, quiz) are 21 cells wide
  (measured in-game) and the player-name macro `<$F600><$0000>` renders up
  to 8 cells (the name entry limit). The engine draws the speaker plate
  inline at the start of the window, so the re-wrapper reserves the widest
  plate of the chunk's speaker pool (its size comes from the chunk VM
  header in `SCEN.DAT`) on the first line of every page of spoken records.
  Keep speaker plate names at 5 cells or less so that reserve stays tight
  (titles like "Marshal" are dropped from plates, not from dialogue text).
  Pages of up to 4 lines are safe (the JP script uses them routinely).
  Choice records (`・...`) must stay single-line — a wrapped tail becomes
  a phantom selectable row. Multi-bullet objective records keep their
  structure.
- The font has no `; — – !? /`; use `,` and full-width `！？`. Ellipsis is
  the single-cell `…` (a trailing period merges into it: `…` not `….`).
  Write ordinary spaces in translated text; the encoder may fold them into
  narrow `space+letter` and `punctuation+space` glyphs when those assignments
  exist. Do not hand-remove spaces to save bytes.
- Tight chunks: if the validator says OVER BUDGET, shorten the text; never
  drop records or tags to make it fit.
- Compression debt: if byte-budget pressure forces wording that drops nuance,
  tone, tutorial detail, or lore detail, record the affected chunk/record in
  `docs/COMPRESSION_DEBT.md` before committing.

## Repository conventions

- Commit author: `Yuri Konotopov <ykonotopov@gmail.com>`. Include a
  `Co-Authored-By` trailer identifying the agent. Messages: functional
  English, present tense.
- No Russian (or other non-English) text in code, comments or data files.
- `work/`, `iso/`, `patches/`, `archive/`, `external/` are not in git;
  everything under `data/` and `scripts/` is.
- Work scenario by scenario, not by raw chunk number:
  `lang5_scenario.py list/chunks/dump/prefill` maps scenario K to its
  chunks (scene `44+K`, battle `K`, scene `86+K`; see
  `data/scenario_map.json`).
- After translating a chunk: rewrap → validate → build → regenerate review
  pages (`lang5_review_html.py`) → commit the chunk pair
  (`SCEN`+`SCEN2`) together.
