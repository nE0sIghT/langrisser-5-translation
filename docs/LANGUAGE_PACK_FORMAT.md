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
  system_layout.json
  title_credits.json
  names.csv
  glossary.csv
  name_entry_grid.json
  manual_record_overrides.json
  review_status.csv
  poem_prologue.txt
  poem_prologue_jp.txt
  virash_monologue.json
```

`SCEN/` contains only completed translated chunks. Work-in-progress chunks live
in `work/wip_<code>/SCEN/`.

Language-specific data uses neutral target fields:

- `font_slot_assignments.csv`: `index_dec,char,replaced_char`;
- `names.csv`: `jp,text,alt` (`alt` is an optional target-language short form);
- `glossary.csv`: `jp,guide_en,text,note`;
- `system_strings.json`: object mapping generated stable ids to target text;
- `system_layout.json`: default and per-stable-id SYSTEM line-growth limits;
- `title_credits.json`: one to three language-specific title-credit templates;
- `virash_monologue.json`: each cue stores its translation in `text`.
- `review_status.csv`: record-level target completion and reference-vs-JP
  review decisions.

`guide_en` is explicitly an English reference-source field, not the selected
language's output field.

`system_strings.json` intentionally contains no extracted Japanese text or
offset metadata. `lang5_system_dump.py` regenerates those fields under
`work/systemdump/system_strings.json`; the packer joins the durable overlay to
that source by ids such as `table:08052:1` and `offset:176A0`.

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
| `system_layout` | Relative path to SYSTEM.BIN line-growth constraints JSON. |
| `title_credits` | Relative path to title-credit templates JSON. |
| `names` | Relative path to name table CSV. |
| `glossary` | Relative path to glossary CSV. |
| `name_entry_grid` | Relative path to name-entry layout JSON. |
| `manual_record_overrides` | Relative path to quiz/bootstrap overrides. |
| `review_status` | Relative path to record-level translation review CSV. |
| `poem` | Relative path to translated prologue poem text. |
| `poem_source` | Relative path to recognized original poem text. |
| `virash_monologue` | Relative path to Virash monologue cue JSON. |
| `font` | Font path for rendering target glyph slots, relative to the language root. |
| `font_size` | TTF render size for font-slot rendering. |
| `single_chars` | Optional alphabet characters to allocate even before script text exists. |
| `forced_pairs` | Optional two-character glyphs that must be allocated, such as compact UI labels. |
| `window_width` | Dialogue window width in cells. |
| `choice_width` | Choice-row width in cells. |
| `max_lines` | Safe page height for rewrap checks. |

Relative manifest paths are resolved from the language directory.

## Record Review Status

`review_status.csv` is a sparse or complete list with this fixed header:

```csv
chunk,record,target_done,reference_checked,note
```

- `target_done`: `1` only after the target record is translated and reviewed;
- `reference_checked`: `1` only after the existing reference-language record
  has been checked against the Japanese source;
- `note`: optional editorial context.

Missing rows mean both states are pending. The review generator validates
booleans, duplicate keys and stale full-run keys. These states are editorial
decisions and are intentionally independent from automatic checks for missing
records, control-signature differences and residual Japanese.

Generate a scenario-oriented three-way review with:

```bash
python3 scripts/lang5_review_html.py --lang ru --scenario 1
```

The JP dump drives the records, English is the default reference language, and
all HTML output stays under `work/review/<lang>/`.

## SYSTEM Layout Constraints

`system_layout.json` prevents one translated UI line from becoming
unexpectedly wider merely because its offset-table group has enough storage:

```json
{
  "default_max_grow": 4,
  "overrides": {
    "table:08052:262": 6
  }
}
```

Values are additional encoded words beyond the original line length. Overrides
use the same generated stable ids as `system_strings.json`; unknown ids,
negative values and loose strings are rejected. Loose strings have no
regenerable offset table and always remain within their original fixed budget.
Keep the default conservative and add only display-verified exceptions.

`lang5_system_pack.py --max-grow N` is a diagnostic override for the default;
stable-id overrides still take precedence. The normal build does not pass this
option and reads all limits from the language pack.

## Creating A Pack

```bash
python3 scripts/lang5_init_lang.py ru --label Russian
```

The initializer copies source structure while clearing target values. It leaves
`SCEN/` empty unless `--copy-script` is explicitly passed.

The full PPF build completes the tracked assignment baseline into a generated
`work/build/font_slot_assignments.<lang>.csv`, then rebuilds the font, rewraps
a copy under `work/build/translation.<lang>/` and validates it before
insertion. The build never rewrites tracked translation sources. This makes
newly required pairs part of the actual build instead of an optional
maintenance step.

After generating the final table, the build also checks shared engine layout
constraints from `data/common/system_ui_constraints.json`. In particular,
startup-menu labels may not cross a 9-cell VRAM-atlas row.

To persist newly derived assignments in the language pack for review, run:

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
