# Langrisser V PS1 EN Translation Workspace

Goal: a working toolkit for translating Langrisser V (PS1, SLPS-01818),
modeled after the Langrisser 3 toolkit (`external/lang3`).

The legacy pipeline (removed 2026-06-11) parsed script record boundaries with
a +2 byte shift and used unusable auto-alignment data; see `docs/PLAN.md` for
the verified container format and the staged rebuild plan.

## Layout

- `iso/` — original BIN/CUE (not in git)
- `work/` — regenerable artifacts: extracted files, dumps, builds (not in git)
- `data/font_mapping/` — token->glyph table (`groups_report.csv`) and pending
  review proposals (`proposed_fixes.csv`)
- `data/translation/` — curated translation data only:
  - `manual_record_overrides.json` — proofread startup quiz lines
  - `system_menu_map.json` — menu/UI replacement dictionary
- `data/tables/lang5_jp.tbl` — JP insert table
- `translation.txt` — GameFAQs scene-by-scene EN script (borgor), the
  translation source
- `docs/PLAN.md` — current plan and verified format notes
- `external/` — third-party tools: DuckStation, Ghidra, lang3 reference
  toolkit (not in git)
- `archive/` — retired research artifacts (not in git)

## Working utilities

- `scripts/iso_mode2.py` — extract/inject files in the MODE2 BIN image
- `scripts/ppf3.py` — PPF3 patch writer
- `scripts/lang5_textcodec.py` — token<->text codec helpers (.tbl based)
- `scripts/lang5_build_en_font_and_tbl.py` — render EN glyphs into the
  SYSTEM.BIN font plane and build the EN table
- `scripts/lang5_patch_system_menu.py` — menu/UI run replacement in
  SYSTEM.BIN
- `scripts/lang5_font_review.py` — HTML visual review of the glyph mapping

Extraction (once):

```bash
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /L5/SCEN.DAT work/extracted/SCEN.DAT
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /L5/SCEN2.DAT work/extracted/SCEN2.DAT
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /L5/SYSTEM.BIN work/extracted/SYSTEM.BIN
```

The script dumper/inserter and PPF build entrypoint are being rewritten
around the verified text-block format (stage 1 in `docs/PLAN.md`).
