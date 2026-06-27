# Russian Translation Plan

## Goal

Produce a complete Russian translation directly from the Japanese game script
while verifying the existing English translation record by record.

Source priority is strict:

1. The generated Japanese dump under `work/` is authoritative.
2. `data/lang/en/` is a cross-check and must not replace reading the Japanese.
3. The GameFAQs guide and fan terminology are secondary references.
4. If English conflicts with Japanese, Japanese wins and English is corrected.

Generated Japanese SCEN and SYSTEM text is never committed. Image/audio source
text that cannot be reproduced by the text dumpers, such as the prologue poem
and Virash narration, may remain with the durable language assets.

## Current Baseline

- English content coverage is complete, but it is not yet certified by the new
  record-by-record Japanese cross-check.
- The Russian language pack is an intentionally untranslated scaffold using
  the accepted Spleen 6x12 bitmap font, which covers the complete Russian
  alphabet including `Ё/ё`.
- The multilingual EN pipeline builds successfully. The clean RU scaffold is
  intentionally not buildable until Stage 1 allocates its glyph slots and
  supplies its name grid.
- Completed reverse engineering and tooling are recorded in
  `docs/IMPLEMENTED.md`.

## Stage 1: Russian Font And Encoding

- [x] Verify all Russian letters, including `Ё/ё`, digits and required
  punctuation, in Spleen 6x12.
- [ ] Extend pair detection from ASCII-only words to Unicode Cyrillic words.
- [ ] Allocate mandatory single glyphs and frequency-ranked Russian pair
  glyphs.
- [ ] Render and review every allocated single/pair glyph.
- [ ] Prepare the Russian name-entry grid.
- [ ] Prove that a representative translated chunk fits and builds without
  using slots above 1820.

This stage blocks bulk translation: single-cell Cyrillic without pair glyphs is
not expected to fit the fixed SCEN budget.

## Stage 2: Three-Way Review Tooling

1. Generate a JP / existing EN / new RU view keyed by chunk and record.
2. Show speaker plate, control words and page boundaries for each record.
3. Flag missing records, control-signature differences and residual Japanese.
4. Track separate `RU translated` and `EN checked against JP` states.
5. Keep all generated review pages under `work/`.

## Stage 3: Russian Terminology

- [x] Approve and populate the core Russian character, place, faction and
  series terminology in `glossary.csv`.
- [ ] Populate Russian class, unit, item and spell names in `names.csv`.
- [ ] Verify names, countries, classes, items, spells and military terms
  against Japanese and the established series terminology.
- [ ] Treat existing English wording as evidence, not authority.
- [ ] Keep one canonical Russian rendering for every recurring term.

## Stage 4: Translation Order

Translate and cross-check in this order:

1. Startup quiz.
2. Tutorial.
3. Main scenarios 1-36.
4. Optional scenarios 38-42.
5. Recap and biography chunks 129-130.
6. SYSTEM/UI strings.
7. Prologue poem and Virash narration.

Work scenario by scenario, not by arbitrary chunk order.

## Per-Scenario Procedure

1. Generate or refresh the Japanese source dump from the original image.
2. Stage the scenario in `work/wip_ru/`.
3. Read every Japanese record and compare the corresponding English record.
4. Translate Japanese to Russian without using English as the sole source.
5. Correct English when Japanese confirms a meaning, subject, tone or
   terminology error.
6. Preserve all control words and argument words in order.
7. Rewrap both changed language packs and verify speakers, choices and pages.
8. Record any lost nuance caused by the fixed byte budget in
   `docs/COMPRESSION_DEBT.md` with the affected language.
9. Run validation and full builds for every changed language.
10. Move a Russian chunk into `data/lang/ru/SCEN/` only when the whole chunk is
    translated and validated.

## Scenario Completion Gate

A scenario is complete only when:

- every Japanese record has a Russian translation;
- every corresponding English record has been checked against Japanese;
- no untranslated Japanese remains in the Russian target;
- control signatures and argument words match the source;
- speaker-plate tests and line wrapping pass;
- terminology is consistent;
- compression debt is current;
- EN and RU validation/builds pass for all changed data.

## Progress

| Content | RU translated | EN checked against JP | Terms checked | Validate | Build |
| --- | --- | --- | --- | --- | --- |
| Startup quiz | No | No | No | No | No |
| Tutorial | No | No | No | No | No |
| Scenarios 1-36 | 0/36 | 0/36 | No | No | No |
| Optional scenarios 38-42 | 0/5 | 0/5 | No | No | No |
| Recap 129 | No | No | No | No | No |
| Bios 130 | No | No | No | No | No |
| SYSTEM/UI | No | No | No | No | No |
| Prologue poem | No | No | No | No | No |
| Virash narration | No | No | No | No | No |

## Final Gate

1. Confirm that every translatable JP record has a Russian target record.
2. Confirm that every existing English record has completed JP cross-check.
3. Confirm that no partial Russian chunk exists in durable data.
4. Run all mandatory checks for EN and RU.
5. Build both complete PPF patches without changing any disc-file size.
6. Revisit all open compression debt before release packaging.

Runtime playtesting is performed separately from this static translation and
build workflow.
