# Langrisser V PS1 EN Patch Workspace

Canonical patch name:
- `patches/langrisser_v_en.ppf`

This repository is intentionally reduced to the production translation flow:
1. alphabet/font mapping data
2. source text extraction
3. translation insertion/repack
4. final PPF creation

All exploratory/research tooling was moved to:
- `archive/legacy_20260219/`

## Canonical Flow

### 1) Extract game files (once)
```bash
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /L5/SCEN.DAT work/extracted/SCEN.DAT
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /L5/SCEN2.DAT work/extracted/SCEN2.DAT
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /L5/SYSTEM.BIN work/extracted/SYSTEM.BIN
```

### 2) Dump source script (JP, token-safe)
```bash
python3 scripts/lang5_dump_scenarios_from_groups_report.py \
  --scen work/extracted/SCEN.DAT \
  --scen2 work/extracted/SCEN2.DAT \
  --groups-report data/font_mapping/groups_report.csv \
  --out-dir work/scriptdump_groups
```

### 3) Build full EN patch data + PPF
```bash
python3 scripts/make_langrisser_v_ppf.py
```

This command performs:
- EN dump build from `data/translation/jp_en_full_records.json`
- manual startup overrides from `data/translation/manual_record_overrides.json`
- SCEN/SCEN2 repack
- SYSTEM menu/UI patch via `data/translation/system_menu_map.json`
- SLPS title replacement
- final `PPF3` build

## Kept Scripts (production only)
- `scripts/iso_mode2.py`
- `scripts/ppf3.py`
- `scripts/lang5_textcodec.py`
- `scripts/lang5_scrscendump.py`
- `scripts/lang5_scrsceninsert.py`
- `scripts/lang5_build_en_font_and_tbl.py`
- `scripts/lang5_build_en_dump_full.py`
- `scripts/lang5_patch_system_menu.py`
- `scripts/lang5_dump_scenarios_from_groups_report.py`
- `scripts/lang5_build_script_ppf.py`
- `scripts/make_langrisser_v_ppf.py`

## Documentation
- `docs/TRANSLATION_FLOW.md` — practical pipeline only
- `docs/INTERNAL_DATA_FORMATS.md` — discovered internal formats
- `docs/DISASM_SUMMARY.md` — structured disassembly conclusions for text control flow
