# Translation Compression Debt

This file tracks places where English wording was intentionally compressed or
where a later polish pass should restore lost nuance if the byte budget allows.
It is not a list of every short translation. Add an entry only when meaning,
character voice, tutorial clarity, lore detail, or narrative tone was knowingly
reduced to fit the current script budget.

## Policy

- Preserve the current build first: file sizes must not grow and validator
  checks must stay green.
- When a line must be shortened enough to drop nuance, add an item here before
  committing the scenario.
- During a polish pass, revisit the item, compare JP and EN in the review HTML,
  then either expand the line or mark the item closed with the reason.
- Prefer recovering meaning by better wording, new pair glyphs, or global
  repack slack before accepting permanent loss.

## Reviewed Range

Reviewed commits from `26448ea3ad309514013b8ad7c2e4f66e56c2a30c` through
`0c3259f`:

- `26448ea` AGENTS trailer policy only, no script compression.
- `73b0605` scenario 6 epilogue.
- `a0de094` control-aware rewrap/name pair encoding changes.
- `fcfecd0` through `0c3259f` scenarios 7 through 20.

The open items below are the concrete compression risks found during this pass.
Scenarios/chunks not listed here had no obvious meaning loss during this review,
though they still need normal playtest and style polish.

## Open Items

| ID | Scenario / chunk | Records | Risk | Revisit action |
| --- | --- | --- | --- | --- |
| CD-005 | Scenario 20, `chunk_020.txt` | `50` | Excalibur event is compressed. JP says there is a single red lotus, a beautiful woman appears on the lake surface while watching it, and grants the sword. Current EN drops "single" and "beautiful" and simplifies the apparition. | Restore imagery if budget allows. |
| CD-006 | Scenario 20, `chunk_020.txt` | `98-101` | Post-battle gratitude exchange is compressed. JP has a warmer back-and-forth about saving thanks until Kalxath is peaceful, and Clarett's happiness that everyone lends strength to the country. Current EN preserves the meaning but loses character warmth. | Polish dialogue after budget pressure is known. |
| CD-007 | Scenario 20, `chunk_020.txt` | `103` | Snow Dragon reward line is compressed. JP explicitly says the children grew healthy thanks to the party and the dragon came today to repay that debt. Current EN keeps this but is very terse. | Expand if possible, especially if CD-001 is also polished for consistency. |
| CD-008 | Scenario 11, `chunk_055.txt` | `31` | Glob strategy line is very terse. JP says if merely waiting improves the situation, there is no reason not to use it, and that Glob's plan seems to have succeeded. Current EN preserves the facts but loses rhetorical shape. | Restore the reasoning if budget allows. |
| CD-009 | Scenario 7, `chunk_093.txt` | `73` | Advice to stop brooding is compressed. JP says nothing changes while standing around thinking, so they should move first, then chase the swords. Current EN is correct but very blunt. | Polish if this scene needs stronger character voice. |
| CD-010 | Scenario 12, `chunk_098.txt` | `46` | Clarett introspection is compressed. JP includes self-questioning about fleeing from father/Jessica, relying on others' judgment, Brenda's criticism, the need to change, and a comparison with lively Caconsis. Current EN keeps the arc but loses introspective cadence and some detail. | Revisit as a high-priority character-voice item. |
| CD-011 | Scenario 12, `chunk_098.txt` | `75` | Commander's contingency line is compressed. JP says if the time comes they must act, and they may need the party's help. Current EN is accurate but minimal. | Low priority polish. |
| CD-012 | Scenario 16, `chunk_016.txt` | `14,17` | Gilmore-side tactical lines are compressed. JP includes "just received information" and "if needed, use the Teleport Ring received from King Gilmore to transfer the girl." Current EN keeps the function but drops attribution/detail. | Restore details if budget allows. |
| CD-013 | Scenario 20, `chunk_064.txt` | `16,18,22,24,35` | Lore exposition was shortened to fit budget. Core facts remain, but the JP has more explicit framing: Glob as one of Boser's demon generals, near-immortality, Chaos as the source of power, and Langrisser/Alhazard as the history of human-demon war. | Revisit as lore polish after the remaining scenarios are translated. |
| CD-014 | Scenario 4, `chunk_090.txt` | `29` | Wheeler's resignation speech was shortened during the scenario 14 budget pass. JP has him spell out that the king promised a general's post, that he has resented the captaincy from the very start, and that they will regret needing his soldiers later. Current EN keeps the facts but loses the bluster ("You will regret losing us！"). | Restore the bluster if chunk 90 budget allows (the chunk already needed a repack sector). |
| CD-015 | Scenario 5, `chunk_049.txt` | `8,10,12,22,24` | Highway family scene trimmed ~50 bytes to keep the repack inside the container (scenario 21 chunks pushed it one sector over). Alfred's "Family really is something, right？" lost the follow-up "Don't you think？"; minor softeners dropped elsewhere ("his old self" -> "himself", "Admiral Wheeler" -> "Wheeler" in narration). | Restore Alfred's double question if a later pass frees chunk 49 budget. |
| CD-016 | Scenario 24, `chunk_110.txt` | `55` | Lainforce's jab at Virash was compressed to keep the page under four lines. The current EN keeps the meaning that Lainforce would protect her even at personal cost, but loses some of the formal, needling tone of "I would never let her face danger" and "I would not lose to a man like this." | Restore the sharper, more formal insult if line budget allows. |
| CD-017 | Recap, `chunk_129.txt` | all recap records | The world-situation recap was translated very close to its fixed-size budget. No specific lost nuance has been proven yet, but the chunk is dense enough that wording may have been flattened or over-condensed compared with the JP digest. | Review `work/review/chunk_129.html` against the JP dump and expand important lore, chronology, or character framing if later budget allows. |
| CD-018 | Recap/bios, `chunk_130.txt` | all ending biography records | The character ending biographies are dense and were compressed to keep the fixed-size SCEN/SCEN2 repack inside the original file sizes. Core branch outcomes are preserved, but some ceremonial narration, repeated emphasis, and softer emotional phrasing were flattened. | Review `work/review/chunk_130.html` against the JP dump and expand character tone or epilogue detail if later budget is freed. |

## Closed Items

| ID | Scenario / chunk | Records | Resolution |
| --- | --- | --- | --- |
| CD-001 | Scenario 12, `chunk_012.txt` | `48` | Closed 2026-06-14. Restored the step-by-step Snow Dragon egg event, including the silent wait, sudden gust, falling egg catch, parent's return, formal thanks, and future-reward vow. |
| CD-002 | Scenario 12, `chunk_012.txt` | `104` | Closed 2026-06-14. Expanded Alfred's criticism to state that the villagers would have starved without the party and that they ran without trying to act. |
| CD-003 | Scenario 19, `chunk_019.txt` | `55` | Closed 2026-06-14. Restored Glob's miscalculation, the heirs-of-light ploy, Gilmore weakening mankind, the corpse pile, and Langrisser being in demon hands. |
| CD-004 | Scenario 19, `chunk_019.txt` | `135` | Closed 2026-06-14. Rephrased the Pondbag/Umagee recommendation with the amusement-hall framing and "interesting things" detail. |
| CD-019 | Scenario 2 battle, `chunk_002.txt` | `15,21,23,33,46,49,53,63,66,71,76,79,84,88,90,96,97,103,104,113` | Closed 2026-06-13. The fuller text was restored after the battle suffix alignment rule was confirmed: chunk `002` may shift its suffix when the new suffix start remains 4-byte aligned. In-game testing confirmed battle images/portraits stayed intact. |
