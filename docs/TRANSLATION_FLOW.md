# Translation Flow

## Goal

Build a full EN patch for Langrisser V PS1:
- script (`SCEN.DAT`, `SCEN2.DAT`)
- menu/UI (`SYSTEM.BIN`)
- executable title (`SLPS_018.19`)

Output:
- `patches/langrisser_v_en.ppf`

## Pipeline

1. Extract source files from BIN
2. Build JP source dump from canonical alphabet map
3. Build EN dump from mapping JSON (+ manual overrides)
4. Reinsert EN dump into SCEN/SCEN2
5. Patch SYSTEM menu/UI runs
6. Patch executable title
7. Generate PPF3

## Commands

### Extract
```bash
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /L5/SCEN.DAT work/extracted/SCEN.DAT
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /L5/SCEN2.DAT work/extracted/SCEN2.DAT
python3 scripts/iso_mode2.py iso/SLPS-01818-9-B.bin extract /L5/SYSTEM.BIN work/extracted/SYSTEM.BIN
```

### Build source dump
```bash
python3 scripts/lang5_dump_scenarios_from_groups_report.py \
  --scen work/extracted/SCEN.DAT \
  --scen2 work/extracted/SCEN2.DAT \
  --groups-report data/font_mapping/groups_report.csv \
  --out-dir work/scriptdump_groups
```

### Build full PPF
```bash
python3 scripts/make_langrisser_v_ppf.py
```

## Key data files

- `data/font_mapping/groups_report.csv`
- `data/translation/jp_en_full_records.json`
- `data/translation/manual_record_overrides.json`
- `data/translation/system_menu_map.json`

## Notes

- Repack keeps original container size constraints (`--max-size-mode original`).
- Text insertion is token-level and preserves control-token placement.
- Long EN lines are truncated to available printable slots in each record.
