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
- The Russian language pack uses Terminus 6x12, which
  covers the complete Russian alphabet including `Ё/ё`.
- The startup quiz, tutorial, complete SYSTEM/UI text, name-entry grid and
  language-specific title credits are translated into Russian.
- Both EN and RU pipelines build successfully. Russian scenarios 1-22 are
  complete; scenarios 23 onward remain untranslated.
- Completed reverse engineering and tooling are recorded in
  `docs/IMPLEMENTED.md`.

## Stage 1: Russian Font And Encoding

- [x] Verify all Russian letters, including `Ё/ё`, digits and required
  punctuation, in Terminus 6x12.
- [x] Extend pair detection from ASCII-only words to Unicode Cyrillic words.
- [x] Allocate mandatory single glyphs and frequency-ranked Russian pair
  glyphs.
- [x] Accept Terminus 6x12 as the Russian base font and review its rendered
  Cyrillic glyphs.
- [x] Prepare the Russian name-entry grid.
- [x] Prove that a representative translated chunk fits and builds without
  using slots above 1820.

The allocator is additive and idempotent. It derives additional Cyrillic pair
glyphs from the accepted Terminus face as the translated corpus grows.

## Stage 2: Three-Way Review Tooling

- [x] Generate a JP / existing EN / new RU view keyed by chunk and record.
- [x] Show speaker plate, control words and page boundaries for each record.
- [x] Flag missing records, control-signature differences and residual
  Japanese.
- [x] Track separate `RU translated` and `EN checked against JP` states.
- [x] Keep all generated review pages under `work/`.

## Stage 3: Russian Terminology

- [x] Approve and populate the core Russian character, place, faction and
  series terminology in `glossary.csv`.
- [x] Populate Russian class, unit, item and spell names in `names.csv`.
- [x] Verify names, countries, classes, items, spells and military terms
  against Japanese and the established series terminology.
- [x] Treat existing English wording as evidence, not authority.
- [x] Keep one canonical Russian rendering for every recurring term.

## Stage 4: Translation Order

Translate and cross-check in this order:

1. Prologue poem.
2. Complete startup flow: quiz and tutorial.
3. SYSTEM/UI strings.
4. Main scenarios 1-36.
5. Optional scenarios 38-42.
6. Recap and biography chunks 129-130.
7. Virash narration.

Work scenario by scenario, not by arbitrary chunk order.

The poem pass reads the original Japanese image text, checks every line of the
existing English verse against it, and produces a Russian poetic rendering
without dropping meaning for rhyme. Layout is reviewed as one continuous
scroll before it is split back into the three game panels.

The startup-flow pass covers every quiz and tutorial record, including choices,
results, control words and related SYSTEM labels. Existing Russian preview text
does not count as complete until its Japanese meaning and the corresponding
English line have both been checked record by record.

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
| Prologue poem | Yes | Yes | Yes | Yes | Yes |
| Startup quiz | Yes | Yes | Yes | Yes | Yes |
| Tutorial | Yes | Yes | Yes | Yes | Yes |
| Scenario 1 | Yes | Yes | Yes | Yes | Yes |
| Scenario 2 | Yes | Yes | Yes | Yes | Yes |
| Scenario 3 | Yes | Yes | Yes | Yes | Yes |
| Scenario 4 | Yes | Yes | Yes | Yes | Yes |
| Scenario 5 | Yes | Yes | Yes | Yes | Yes |
| Scenario 6 | Yes | Yes | Yes | Yes | Yes |
| Scenario 7 | Yes | Yes | Yes | Yes | Yes |
| Scenario 8 | Yes | Yes | Yes | Yes | Yes |
| Scenario 9 | Yes | Yes | Yes | Yes | Yes |
| Scenario 10 | Yes | Yes | Yes | Yes | Yes |
| Scenario 11 | Yes | Yes | Yes | Yes | Yes |
| Scenario 12 | Yes | Yes | Yes | Yes | Yes |
| Scenario 13 | Yes | Yes | Yes | Yes | Yes |
| Scenario 14 | Yes | Yes | Yes | Yes | Yes |
| Scenario 15 | Yes | Yes | Yes | Yes | Yes |
| Scenario 16 | Yes | Yes | Yes | Yes | Yes |
| Scenario 17 | Yes | Yes | Yes | Yes | Yes |
| Scenario 18 | Yes | Yes | Yes | Yes | Yes |
| Scenario 19 | Yes | Yes | Yes | Yes | Yes |
| Scenario 20 | Yes | Yes | Yes | Yes | Yes |
| Scenario 21 | Yes | Yes | Yes | Yes | Yes |
| Scenario 22 | Yes | Yes | Yes | Yes | Yes |
| Scenario 23 | No | No | No | No | No |
| Scenario 24 | No | No | No | No | No |
| Scenario 25 | No | No | No | No | No |
| Scenario 26 | No | No | No | No | No |
| Scenario 27 | No | No | No | No | No |
| Scenario 28 | No | No | No | No | No |
| Scenario 29 | No | No | No | No | No |
| Scenario 30 | No | No | No | No | No |
| Scenario 31 | No | No | No | No | No |
| Scenario 32 | No | No | No | No | No |
| Scenario 33 | No | No | No | No | No |
| Scenario 34 | No | No | No | No | No |
| Scenario 35 | No | No | No | No | No |
| Scenario 36 | No | No | No | No | No |
| Optional scenario 38 | No | No | No | No | No |
| Optional scenario 39 | No | No | No | No | No |
| Optional scenario 40 | No | No | No | No | No |
| Optional scenario 41 | No | No | No | No | No |
| Optional scenario 42 | No | No | No | No | No |
| Recap 129 | No | No | No | No | No |
| Bios 130 | No | No | No | No | No |
| SYSTEM/UI | Yes | Yes | Yes | Yes | Yes |
| Title credits | Yes | N/A | Yes | Yes | Yes |
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
