# Battle Chunk Suffix Notes

This document tracks the current reverse-engineering state for the non-text
payload that follows battle chunk text blocks. It exists because growing a
battle text block can move this payload and cause portrait/map asset
regressions even when the outer `SCEN.DAT` file size remains unchanged.

## Scope

- Applies to battle chunks `001` through `042` in `SCEN.DAT` and `SCEN2.DAT`.
- The text block still starts at `vm_off + vm_size`.
- The suffix starts at `text_block.base + text_block.size`.
- The diagnostic tool is `scripts/lang5_battle_suffix.py`.

## Confirmed Suffix Archive Shape

Every sampled battle chunk has an archive-like table at the suffix start:

```text
suffix+0x00  u32le payload_size
suffix+0x04  u32le first_data_offset_and_table_size
suffix+0x08  u32le offset[1]
...
suffix+0x04+table_size-4  u32le offset[N-1]
suffix+0x04+table_size    first payload bytes
```

The offset words are relative to `suffix+0x04`, not to `suffix+0x00`.
That interpretation is required because otherwise the first payload overlaps
the final table entry. For example, chunk `002` has:

```text
text_end             0x61A8
suffix_len           0x15E58
payload_size         0x15714
table_size           0x18
table offsets        0x18,0x4C88,0x7980,0xB308,0xECBC,0x10D04
trailing bytes       0x740
```

Payload starts at `suffix + 0x04 + table_size`, so chunk `002` payload starts
at `0x61C4`.

Some chunks contain repeated or out-of-order offset words, so the table should
not yet be treated as a simple ascending section list. Sorted unique offsets
are useful for reporting, but they are not a proven replacement table format.

## Langrisser III References

The old `external/lang3` tools and the newer
`external/langrisser3-english` project are useful as architectural references,
not as direct Langrisser V fixes.

Langrisser III Saturn `D00.DAT` has a top-level section table. The newer
project can rebuild a larger `D00.DAT` and then shift following ISO sectors,
updating ISO9660 directory records. That is safe for Langrisser III because
the project audited file access through directory lookup.

Langrisser V PS1 cannot use the same disc-level growth strategy here:

- The data track is followed by CD audio.
- The project invariant is that `SCEN.DAT`, `SCEN2.DAT`, `SYSTEM.BIN`, and the
  disc data track layout must not grow.
- The observed battle regression happens inside a fixed-size chunk when the
  suffix moves, before any disc-level file growth is involved.

## Current Safety Rule

For battle chunks, the safe rule is still:

```bash
python3 scripts/lang5_validate_en.py <chunk> --budget-mode block
```

This requires the translated records to fit inside the original text block,
keeping the suffix byte-identical at its original offset. Chunk-level or
file-level fixed-size repacking is not enough to protect battle suffix assets
until the runtime references into the suffix are understood.

## Open Questions

- Which VM or battle-engine fields select entries in the suffix archive?
- Are any suffix references stored as chunk-local absolute offsets instead of
  archive-relative offsets?
- Does the game rely on the suffix start being the original `text_end`, or on
  one or more asset sub-pointers derived from it?
- Can a relocation patch update all such references safely while preserving
  the original file size?

## Next Reverse-Engineering Steps

1. Compare original chunk `002` with a deliberately shifted text-block build
   and identify the first broken asset read in emulator logs or RAM traces.
2. Trace the battle asset loader paths around the invalid read PCs reported by
   DuckStation (`0x8003B46C`, `0x8003B570`, and later `0x800Bxxxx` paths).
3. Use `scripts/lang5_battle_suffix.py --scan-full` only as a noisy hint
   source; avoid treating arbitrary VM/text words as proven pointers.
4. Once the loader field is confirmed, add a relocation validator before
   allowing battle chunks to use normal fixed-size repack growth.
