# Speaker plate test set

In-game–verified speaker plates. `scripts/lang5_check_speakers.py` asserts that
`semantic_plate_slots` (the per-record plate extractor used by the line wrapper)
resolves each record below to the listed speaker. A mismatch means the plate
reserve — and therefore the line wrapping — is wrong for that record, so this is
a **mandatory** check (see AGENTS.md).

How to use it:

- Run `python3 scripts/lang5_check_speakers.py`; it must print `OK`.
- When you confirm a plate in game (the name shown on a dialogue window), add a
  row here. Each row is `| record | speaker | phrase |` under its `## Chunk N`
  heading. `record` is the record index in `data/translation/en/SCEN/chunk_N.txt`;
  `speaker` is the exact English plate name; `phrase` is the line, for humans.
- A failure here is a real bug in the extractor, not a reason to edit the test:
  fix `semantic_plate_slots`, do not relax the expected value.

Background and the decoded mechanism are in `docs/SPEAKER_NAME_EXTRACTION.md`.

## Chunk 69

Name pool: Sigma, Mariandel, Clarett, Alfred, Brenda, Lanford, Virash.
Mariandel is the blue-haired girl.

| record | speaker | phrase |
|---|---|---|
| 20 | Mariandel | Did something happen between you and that man? |
| 26 | Mariandel | But what reason could he have to attack a village? |
| 31 | Mariandel | I can't believe there was such a terrible war… |
| 46 | Alfred | …Reynolds… don't tell me… Brother joined without knowing Lainforce's true aim… |
| 47 | Brenda | He's likely being used. |
| 48 | Alfred | Everyone, lend me your strength this time. |
| 49 | Virash | Right. Stopping the Three-Country Alliance also means… |
