# Language Packs

Each target language lives in `data/lang/<lang>/` and is described by
`manifest.json`. The current complete packs are:

- `en` - English patch.
- `ru` - Russian patch.

Additional languages can be scaffolded with `scripts/lang5_init_lang.py` and use
the same extraction, validation, font and packaging pipeline.

Generated Japanese script and SYSTEM dumps stay in `work/scriptdump/` and
`work/systemdump/` and must not be committed.

A language pack contains only durable translation/editorial data: translated
SCEN chunks, SYSTEM.BIN strings, name/glossary tables, font slot assignments,
name-entry layout, review status, and graphic/cutscene transcript text that is
not recoverable by running the dumpers.

Target text uses language-neutral fields:

- `text` in name, glossary and non-reproducible JSON records;
- `char` in font assignments;
- stable id -> target text entries in `system_strings.json`.

`guide_en` is retained only as an explicit English reference column.
