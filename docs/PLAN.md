# Russian Translation Plan

## Goal

Produce a complete Russian translation directly from the Japanese game script
while verifying the existing English translation record by record. The current
coverage baseline is complete; the active goal is now an artistic Russian pass
over the completed text, scenario by scenario.

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
- Both EN and RU pipelines build successfully. All Russian scenario, recap, biography and epilogue chunks are complete.
- Completed reverse engineering and tooling are recorded in
  `docs/IMPLEMENTED.md`.
- Active editorial work is a Russian artistic pass: preserve Japanese meaning
  and Langrisser terminology while making the prose read naturally in Russian.

## World And Style Brief

Langrisser V is a tactical fantasy RPG set in the Langrisser world: kingdoms,
armies, temples, demon forces and ancient holy/demonic weapons shape the visible
conflict, while magical technology, cloning experiments and moon-born Crimzonian
history drive the deeper plot. The story moves between battlefield command,
court politics, military travel, laboratories, ancient ruins and personal
confrontations.

The Russian text should therefore read like grounded fantasy-adventure prose,
not literal subtitle copy. Use clear natural Russian for soldiers, mercenaries
and companions; reserve elevated diction for narration, legends, oaths, royal
or religious speech, and the Crimzonian myth/history material. Scientific and
laboratory scenes may be colder and more technical, but should still avoid
modern bureaucratic phrasing unless the source deliberately sounds mechanical.

Recurring tone targets:

- Location captions should sound like RPG places: "Покои Бренды" is preferable
  to hospital-like "Палата Бренды" when the scene does not need a medical
  institution feel.
- Military dialogue should be concise and command-like, not overly literary.
- Court and noble dialogue may be more formal, but not stiff.
- Comic optional scenarios may keep eccentric speech patterns and verbal quirks.
- Lore narration may be poetic and weighty, provided no factual detail is lost.
- Machine/system speech should remain direct and slightly cold.

Editorial changes must not weaken canon terminology from `names.csv` and
`glossary.csv`, must not drop Japanese meaning, and must not hide a changed
meaning behind smoother Russian.

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

## Stage 5: Russian Artistic Pass

The artistic pass is separate from translation coverage. A scenario marked
translated remains translated even before this pass; it is not release-polished
until this pass is complete.

This is not a second translation pass. The editor starts from the existing
Russian text and changes only lines that sound dry, literal, stylistically
wrong, or meaningfully off. Japanese is consulted to verify every substantial
rewording and to prevent semantic drift; English is only a secondary
cross-check when it helps clarify context.

Work one scenario at a time:

1. Generate the scenario dump with `lang5_scenario.py --lang ru dump N`.
2. Read the current Russian scenario first as Russian prose.
3. Identify literal or stiff Russian turns, especially in visible location
   captions and emotionally important dialogue.
4. For every non-trivial rewrite, check the Japanese source before accepting it.
5. Use the English line only as context, never as the authority for a rewrite.
6. Rewrite only where the Russian can improve without changing source meaning.
7. Preserve speaker voice: military, noble, comic, machine, narrator and lore
   registers must not collapse into one neutral style.
8. Keep control tags, speaker plates and page structure intact.
9. Rewrap, validate, build and regenerate review pages for the edited scenario.
10. Record compression debt only if a byte-budget fix forces loss of nuance.
11. Commit each completed scenario pass separately.

Review order:

1. Main scenarios 1-36 in order.
2. Optional scenarios 38-42 in order.
3. Recap and biography chunks 129-130.
4. Virash narration, poem and SYSTEM/UI as final visible-text polish.

Known first editorial target:

- Scenario 25, chunk 069, record 8: replace the overly clinical "Палата
  Бренды" with a setting-appropriate caption such as "Покои Бренды", after
  checking line fit.

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
| Scenario 23 | Yes | Yes | Yes | Yes | Yes |
| Scenario 24 | Yes | Yes | Yes | Yes | Yes |
| Scenario 25 | Yes | Yes | Yes | Yes | Yes |
| Scenario 26 | Yes | Yes | Yes | Yes | Yes |
| Scenario 27 | Yes | Yes | Yes | Yes | Yes |
| Scenario 28 | Yes | Yes | Yes | Yes | Yes |
| Scenario 29 | Yes | Yes | Yes | Yes | Yes |
| Scenario 30 | Yes | Yes | Yes | Yes | Yes |
| Scenario 31 | Yes | Yes | Yes | Yes | Yes |
| Scenario 32 | Yes | Yes | Yes | Yes | Yes |
| Scenario 33 | Yes | Yes | Yes | Yes | Yes |
| Scenario 34 | Yes | Yes | Yes | Yes | Yes |
| Scenario 35 | Yes | Yes | Yes | Yes | Yes |
| Scenario 36 | Yes | Yes | Yes | Yes | Yes |
| Optional scenario 38 | Yes | Yes | Yes | Yes | Yes |
| Optional scenario 39 | Yes | Yes | Yes | Yes | Yes |
| Optional scenario 40 | Yes | Yes | Yes | Yes | Yes |
| Optional scenario 41 | Yes | Yes | Yes | Yes | Yes |
| Optional scenario 42 | Yes | Yes | Yes | Yes | Yes |
| Recap 129 | Yes | Yes | Yes | Yes | Yes |
| Bios 130 | Yes | Yes | Yes | Yes | Yes |
| SYSTEM/UI | Yes | Yes | Yes | Yes | Yes |
| Title credits | Yes | N/A | Yes | Yes | Yes |
| Epilogue chunks 124-126 | Yes | Yes | Yes | Yes | Yes |
| Virash narration | Yes | Yes | Yes | Yes | Yes |

## Artistic Pass Progress

| Content | Artistic RU pass | Notes |
| --- | --- | --- |
| Scenario 1 | Done | Artistic pass complete for chunks 045, 001 and 087; no compression debt. |
| Scenario 2 | Done | Artistic pass complete for chunks 046, 002 and 088; no compression debt. |
| Scenario 3 | Done | Artistic pass complete for chunks 047, 003 and 089; no compression debt. |
| Scenario 4 | Done | Artistic pass complete for chunks 048, 004 and 090; no compression debt. |
| Scenario 5 | Done | Artistic pass complete for chunks 049, 005 and 091; no compression debt. |
| Scenario 6 | Done | Artistic pass complete for chunks 050, 006 and 092; no compression debt. |
| Scenario 7 | Done | Artistic pass complete for chunks 051, 007 and 093; no compression debt. |
| Scenario 8 | Done | Artistic pass complete for chunks 052, 008 and 094; no compression debt. |
| Scenario 9 | Done | Artistic pass complete for chunks 053, 009 and 095; no compression debt. |
| Scenario 10 | Done | Artistic pass complete for chunks 054, 010 and 096; no compression debt. |
| Scenario 11 | Done | Artistic pass complete for chunks 055, 011 and 097; no compression debt. |
| Scenario 12 | Done | Artistic pass complete for chunks 056, 012 and 098; no compression debt. |
| Scenario 13 | Pending |  |
| Scenario 14 | Pending |  |
| Scenario 15 | Pending |  |
| Scenario 16 | Pending |  |
| Scenario 17 | Pending |  |
| Scenario 18 | Pending |  |
| Scenario 19 | Pending |  |
| Scenario 20 | Pending |  |
| Scenario 21 | Pending |  |
| Scenario 22 | Pending |  |
| Scenario 23 | Pending |  |
| Scenario 24 | Pending |  |
| Scenario 25 | Pending | First known issue: "Палата Бренды" -> "Покои Бренды". |
| Scenario 26 | Pending |  |
| Scenario 27 | Pending |  |
| Scenario 28 | Pending |  |
| Scenario 29 | Pending |  |
| Scenario 30 | Pending |  |
| Scenario 31 | Pending |  |
| Scenario 32 | Pending |  |
| Scenario 33 | Pending |  |
| Scenario 34 | Pending |  |
| Scenario 35 | Pending |  |
| Scenario 36 | Pending |  |
| Optional scenario 38 | Pending | After main scenarios. |
| Optional scenario 39 | Pending |  |
| Optional scenario 40 | Pending |  |
| Optional scenario 41 | Pending |  |
| Optional scenario 42 | Pending |  |
| Recap 129 | Pending | After optional scenarios. |
| Bios 130 | Pending | After optional scenarios. |
| SYSTEM/UI | Pending | Final visible-text polish. |
| Prologue poem | Pending | Final visible-text polish. |
| Virash narration | Pending | Final visible-text polish. |

## Final Gate

1. Confirm that every translatable JP record has a Russian target record.
2. Confirm that every existing English record has completed JP cross-check.
3. Confirm that no partial Russian chunk exists in durable data.
4. Complete the Russian artistic pass or explicitly mark any skipped content.
5. Run all mandatory checks for EN and RU.
6. Build both complete PPF patches without changing any disc-file size.
7. Revisit all open compression debt before release packaging.

Runtime playtesting is performed separately from this static translation and
build workflow.
