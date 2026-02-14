# Langrisser V Script Toolchain (Dump/Insert)

Tooling analogous to `lang3` is now available for `SCEN.DAT` / `SCEN2.DAT`.

## Files

- `scripts/lang5_scrscendump.py`
- `scripts/lang5_scrsceninsert.py`
- `scripts/lang5_textcodec.py`

## Dump

```bash
python3 scripts/lang5_scrscendump.py \
  --scen work/extracted/SCEN.DAT \
  --scen2 work/extracted/SCEN2.DAT \
  --tbl work/tables/lang5.tbl \
  --out-dir work/scriptdump
```

Outputs:

- `work/tables/lang5.tbl` (token table, auto-created if missing)
- `work/scriptdump/SCEN/chunk_XXX.txt`
- `work/scriptdump/SCEN2/chunk_XXX.txt`

Text format per line:

- `record_index<TAB>text`
- unknown/control tokens are represented as tags: `<$HHHH>`

Example:

```text
23	<$0016><$0216><$0225><$0054><$0046><$0003>ギザロフ様。<$FFFE><$FB00>
```

## Insert / Repack

```bash
python3 scripts/lang5_scrsceninsert.py \
  --scen work/extracted/SCEN.DAT \
  --scen2 work/extracted/SCEN2.DAT \
  --dump-dir work/scriptdump \
  --tbl work/tables/lang5.tbl \
  --out-scen work/build/SCEN.DAT \
  --out-scen2 work/build/SCEN2.DAT
```

Behavior:

- Re-encodes edited text lines back to token streams.
- Rebuilds per-chunk local offset tables.
- Rebuilds container pointer table.
- Default guard: output size must not exceed original (`--max-size-mode original`).

## Roundtrip guarantee

Current implementation has been verified with exact roundtrip:

- `dump -> insert` with no edits produces bit-identical `SCEN.DAT` and
  `SCEN2.DAT`.

## Limits

- Output still depends on current `.tbl` coverage.
- Unknown tokens must stay as `<$HHHH>` unless mapped in `.tbl`.
- If edits grow data too much, size guard will fail; reduce expansion or
  disable size guard (`--max-size-mode off`) for research builds.
