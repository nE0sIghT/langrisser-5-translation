# Language Pack Format

Target-language data lives under `data/lang/<code>/`. The build does not read
translated chunks, SYSTEM strings, name tables or font slots from global EN
paths; it resolves them through `manifest.json`.

Generated source dumps stay under `work/`:

- `work/scriptdump/` — JP SCEN/SCEN2 script dump.
- `work/systemdump/` — SYSTEM.BIN string inspection dumps.
- `work/extracted/` — files extracted from the original BIN.

Do not commit those generated dumps. They are reproducible from the user's own
disc image.

## Required Files

```text
data/lang/<code>/
  manifest.json
  SCEN/
  font_slot_assignments.csv
  system_strings.json
  names.csv
  glossary.csv
  name_entry_grid.json
  manual_record_overrides.json
  poem_prologue.txt
  poem_prologue_jp.txt
  virash_monologue.json
```

`SCEN/` contains only completed translated chunks. Work-in-progress chunks live
in `work/wip_<code>/SCEN/`.

Language-specific data uses neutral target fields:

- `font_slot_assignments.csv`: `index_dec,char,replaced_char`;
- `names.csv`: `jp,text,alt`;
- `glossary.csv`: `jp,guide_en,text,note`;
- `system_strings.json`: each entry stores its translation in `text`;
- `virash_monologue.json`: each cue stores its translation in `text`.

`guide_en` is explicitly an English reference-source field, not the selected
language's output field.

## Manifest

Fields currently consumed by the tools:

| Field | Meaning |
| --- | --- |
| `lang` | Language code. |
| `label` | Human-readable language name. |
| `patch_suffix` | Output suffix: `langrisser_v_<suffix>.ppf`, table `lang5_<suffix>.tbl`. |
| `patch_description` | PPF3 description string. |
| `script_dir` | Relative path to translated SCEN chunks, normally `SCEN`. |
| `font_assignments` | Relative path to target glyph assignments CSV. |
| `system_strings` | Relative path to SYSTEM.BIN UI translation JSON. |
| `names` | Relative path to name table CSV. |
| `glossary` | Relative path to glossary CSV. |
| `name_entry_grid` | Relative path to name-entry layout JSON. |
| `manual_record_overrides` | Relative path to quiz/bootstrap overrides. |
| `poem` | Relative path to translated prologue poem text. |
| `poem_source` | Relative path to recognized original poem text. |
| `virash_monologue` | Relative path to Virash monologue cue JSON. |
| `font` | Font path for rendering target glyph slots, relative to the language root. |
| `font_size` | TTF render size for font-slot rendering. |
| `single_chars` | Optional alphabet characters to allocate even before script text exists. |
| `window_width` | Dialogue window width in cells. |
| `choice_width` | Choice-row width in cells. |
| `max_lines` | Safe page height for rewrap checks. |

Relative manifest paths are resolved from the language directory.

## Creating A Pack

```bash
python3 scripts/lang5_init_lang.py ru --label Russian
```

The initializer copies durable editorial scaffolding from an existing language
pack but leaves `SCEN/` empty unless `--copy-script` is explicitly passed.

After editing the manifest and adding target text, update glyph slots:

```bash
python3 scripts/lang5_assign_font_slots.py --lang ru
python3 scripts/lang5_build_font.py --lang ru
```

## Build Outputs

For language suffix `<s>`:

- `work/tables/lang5_<s>.tbl`
- `work/build/SCEN.<s>.DAT`
- `work/build/SCEN2.<s>.DAT`
- `work/build/SYSTEM.BIN.<s>`
- `work/build/IMG.DAT.<s>`
- `work/build/SLPS_018.19.<s>`
- `work/build/langrisser_v_<s>.bin`
- `patches/langrisser_v_<s>.ppf`

All outputs are generated and untracked.
