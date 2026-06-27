# Language Packs

Each target language lives in `data/lang/<lang>/` and is described by
`manifest.json`. Generated Japanese script dumps stay in `work/scriptdump/` and
must not be committed.

A language pack contains only durable translation/editorial data: translated
SCEN chunks, SYSTEM.BIN strings, name/glossary tables, font slot assignments,
name-entry layout, and graphic/audio transcript text that is not recoverable by
running the script dumper.

The `ru` directory is a scaffold. It intentionally starts with copied structure
and empty `SCEN/`; translate it before building a release patch.

Target text uses language-neutral fields (`text` in name, glossary and
non-reproducible JSON records; `char` in font assignments). SYSTEM translations
are stored as a stable-id-to-text object with no extracted JP source.
`guide_en` is retained only as an explicit English reference column.
