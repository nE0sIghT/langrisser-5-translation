# Saturn Disc Format

This document records the current reverse-engineering status for the Sega
Saturn release of Langrisser V. It is intentionally separate from the PS1
format documents: the existing production patcher targets the PlayStation disc,
while the Saturn disc shares some content concepts but uses different physical
tracks, filenames, on-disc word order and executable code.

## Current Status

Working target image:

| Path | Size | CRC32 | SHA-1 prefix |
| --- | ---: | --- | --- |
| `iso/saturn/LANGRISSER_5.bin` | `507074736` | `5E63C92F` | `8ef76305fe27` |

The image is a Sega Saturn mixed-mode disc. Sector 0 user data starts with:

```text
SEGA SEGASATURN SEGA TP T-25
```

The ISO9660 primary volume descriptor is on track 1 at LBA 16 and has volume id
`LANGRISSER_5`.

Terminology note: when this document says `big-endian`, it means the on-disc
byte order needed to read multi-byte fields and `u16` tokens correctly. This is
equivalent to treating the relevant resource words as byte-swapped relative to
the existing PS1 little-endian tooling; it does not prove the Saturn runtime
uses big-endian memory access for these structures.

Read-only tooling added for this investigation:

| Tool | Purpose |
| --- | --- |
| `scripts/saturn_disc.py` | Parse the Saturn CUE, list/extract track-1 ISO files, summarize track-2 XA sectors |
| `scripts/saturn_system_dump.py` | Dump Saturn `SYSTEM.DAT` text groups using the confirmed on-disc word order |
| `scripts/saturn_scen_scan.py` | Scan Saturn `SCEN.DAT` catalog, chunk headers, record indices and token streams |
| `scripts/saturn_scen_text.py` | Dump the full Saturn `SCEN.DAT` scenario text pool with stable `(chunk, entry)` ids |
| `scripts/saturn_font.py` | Render Saturn `SYSTEM.DAT` glyph slots and diff them against the PS1 font |
| `scripts/saturn_scen.py` | Shared SCEN.DAT read/rebuild model (catalog, block header, field_3c text pool) |

The Saturn tools share the platform-agnostic core: `lang5_binfmt` (byte order),
`lang5_offsetgroups` (the SYSTEM group model), and the PS1 token codec, so no
common logic is duplicated between the PS1 and Saturn tooling.

Generated investigation output lives under `work/build/saturn/` and is not
tracked.

## Track Layout

From `iso/saturn/LANGRISSER_5.cue`:

| Track | Mode | INDEX 01 | LBA | Raw byte offset | Notes |
| --- | --- | --- | ---: | ---: | --- |
| 1 | `MODE1/2352` | `00:00:00` | `0` | `0` | Saturn boot sector and ISO9660 filesystem |
| 2 | `MODE2/2352` | `13:45:26` | `61901` | `145591152` | CD-XA/ADPCM payload sectors |
| 3 | `AUDIO` | `39:18:12` | `176862` | `415979424` | CD audio |
| 4 | `AUDIO` | `39:47:43` | `179068` | `421167936` | CD audio |
| 5 | `AUDIO` | `41:12:67` | `185467` | `436218384` | CD audio |
| 6 | `AUDIO` | `46:30:57` | `209307` | `492290064` | CD audio |

Confirmed sector user-data offsets:

| Mode | Raw sector size | User offset | User size used here |
| --- | ---: | ---: | ---: |
| `MODE1/2352` | `2352` | `16` | `2048` |
| `MODE2/2352` XA audio | `2352` | raw sector required | Form2 audio sectors, keep subheaders |

The current PS1 `scripts/iso_mode2.py` assumes a single `MODE2/2352` data track
with 2048-byte user data at offset 24. It is not suitable for Saturn track 1
or track 2 without a new track-aware backend.

## Track 1 ISO9660 Root

Track 1 is a normal ISO9660 filesystem. Root directory:

| Type | LBA | Size | Name |
| --- | ---: | ---: | --- |
| file | `214` | `232660` | `A0LANG5.BIN` |
| dir | `21` | `4096` | `ADPCM` |
| file | `27603` | `710656` | `ALLUSB.BIN` |
| file | `27950` | `761856` | `ALLUSW.BIN` |
| file | `35809` | `198656` | `BAR.BIN` |
| file | `36380` | `7555072` | `BGM.BIN` |
| file | `31761` | `8290304` | `BTLBG.BIN` |
| file | `28340` | `83604` | `BTLDAT.BIN` |
| file | `28381` | `6922240` | `BTLEFF.BIN` |
| file | `41306` | `242700` | `CAST.DAT` |
| file | `41296` | `18808` | `CLEAR.DAT` |
| file | `35906` | `15968` | `CUR.DAT` |
| file | `55666` | `721` | `GRAPHIC.DOC` |
| file | `55667` | `12613411` | `GRAPHIC.LZH` |
| file | `212` | `19` | `L5_ABS.TXT` |
| file | `213` | `480` | `L5_BIB.TXT` |
| file | `211` | `32` | `L5_CPY.TXT` |
| file | `41977` | `28000948` | `LANG5.CPK` |
| file | `35939` | `720896` | `MAG.BIN` |
| file | `40271` | `2099200` | `MAGSND.BIN` |
| file | `676` | `5474304` | `MAP.DAT` |
| file | `3349` | `26744832` | `MAP_C.DAT` |
| file | `28322` | `35860` | `MRCUSW.BIN` |
| file | `55651` | `28926` | `OMAKE.LZH` |
| file | `41685` | `351404` | `OPEN.DAT` |
| file | `328` | `508908` | `PROG1.BIN` |
| file | `577` | `78548` | `PROG2.BIN` |
| file | `55650` | `1542` | `READ_ME.TXT` |
| file | `16408` | `22910976` | `SCEN.DAT` |
| file | `35914` | `50736` | `SHOP.DAT` |
| file | `36295` | `36630` | `SND00.BIN` |
| file | `27595` | `15000` | `SNDDEB.BIN` |
| file | `36313` | `135220` | `SND_DAT.BIN` |
| file | `41425` | `531136` | `STAFF.DAT` |
| file | `616` | `121344` | `SYSTEM.DAT` |
| file | `41857` | `123944` | `TITLE1.DAT` |
| file | `41918` | `118888` | `TITLE2.DAT` |
| file | `40069` | `413696` | `TK_SC.BIN` |
| file | `36291` | `8192` | `WD_FONT.BIN` |

## Track 2 XA / ADPCM Area

Track 2 is not an ISO9660 volume. It is a contiguous XA/ADPCM sector area.

Confirmed over the useful payload range:

| Property | Value |
| --- | --- |
| Physical track start | LBA `61901` |
| First referenced XA logical extent | LBA `62126` |
| Logical-to-physical correction | subtract `225` sectors (`00:03:00` pregap) |
| Last referenced physical sector end | LBA `176712` |
| Referenced sectors | `114811` |
| XA files indexed from ISO | `6068` |
| ADPCM directories | `40` (`DIR_00` through `DIR_38`, plus `DIR_VAM`) |

The ISO `ADPCM/` directory entries point into track 2. Their extent LBA is a
logical value that includes the 225-sector pregap. To read from the raw BIN:

```text
physical_raw_sector_lba = iso_directory_extent_lba - 225
```

Examples:

| ISO entry | Logical LBA | Physical raw LBA | Size field | Physical first subheader |
| --- | ---: | ---: | ---: | --- |
| `ADPCM/DIR_00/P001.XA` | `62126` | `61901` | `69248` | `0000640400006404` |
| `ADPCM/DIR_00/P002.XA` | `62160` | `61935` | `31488` | `0000640400006404` |
| Last referenced sector | `176936` | `176711` | n/a | `0000e4040000e404` |

Subheader classification for the referenced track 2 area:

| Subheader | Meaning | Count |
| --- | --- | ---: |
| `0000640400006404` | XA audio Form2 sector | `107556` |
| `0000e4040000e404` | XA audio Form2 sector with EOF flag | `6067` |
| `0000640500006405` | XA audio Form2 sector, coding byte `0x05` | `1187` |
| `0000e4050000e405` | EOF variant for coding byte `0x05` | `1` |

The number of EOF sectors matches the number of `.XA` files (`6068`), which
confirms the directory-to-track mapping.

Reproducible commands:

```bash
python3 scripts/saturn_disc.py info
python3 scripts/saturn_disc.py list --json > work/build/saturn/iso_entries.json
python3 scripts/saturn_disc.py xainfo > work/build/saturn/xa_info.json
```

## Key File Mapping vs PS1

The Saturn disc is not a filename-level drop-in replacement for the PS1 disc.

| PS1 path / concept | PS1 size | Saturn counterpart | Saturn size | Status |
| --- | ---: | --- | ---: | --- |
| `/L5/SCEN.DAT` | `23480320` | `SCEN.DAT` | `22910976` | Related content, different container/index |
| `/L5/SCEN2.DAT` | `23463936` | none found | n/a | PS1 duplicate absent |
| `/L5/SYSTEM.BIN` | `98320` | `SYSTEM.DAT` | `121344` | Same text-table concept, swapped-word/on-disc BE and shifted |
| `/L5/IMG.DAT` | `3233792` | `TITLE1.DAT`, `TITLE2.DAT`, `OPEN.DAT`, etc. | varies | Different asset containers |
| `/SLPS_018.19` | `833536` | `A0LANG5.BIN`, `PROG1.BIN`, `PROG2.BIN` | varies | Different CPU/code platform |
| `/L5/VOICE.PAC`, `/L5/XA.PAC` | varies | `ADPCM/**/*.XA`, track 2 | `6068` clips | Different physical storage |

## `SYSTEM.DAT`

Confirmed:

- `SYSTEM.DAT` begins similarly to PS1 `SYSTEM.BIN` but diverges at offset
  `0x0E35`.
- The PS1 system dumper finds no groups when run unchanged because it assumes
  little-endian words and `SCAN_START = 0x8052`.
- A full scan finds 16 valid offset-table groups when multi-byte words are
  read in the confirmed swapped/on-disc BE order.
- The string token ids decode with the existing Japanese glyph table.

Group table summary:

| Group | Table offset | Entries | String base | End |
| ---: | ---: | ---: | ---: | ---: |
| 0 | `0x08084` | `292` | `0x082CC` | `0x09002` |
| 1 | `0x09004` | `44` | `0x0905C` | `0x094A6` |
| 2 | `0x094A8` | `190` | `0x09624` | `0x09FC6` |
| 3 | `0x09FC8` | `130` | `0x0A0CC` | `0x0A744` |
| 4 | `0x0A744` | `20` | `0x0A76C` | `0x0A854` |
| 5 | `0x0A854` | `33` | `0x0A896` | `0x0A992` |
| 6 | `0x0A994` | `65` | `0x0AA16` | `0x0AD22` |
| 7 | `0x0AD24` | `25` | `0x0AD56` | `0x0AE70` |
| 8 | `0x0AE70` | `96` | `0x0AF30` | `0x0B42E` |
| 9 | `0x0B430` | `330` | `0x0B6C4` | `0x0C624` |
| 10 | `0x0C624` | `330` | `0x0C8B8` | `0x0D764` |
| 11 | `0x0D764` | `252` | `0x0D95C` | `0x0FC08` |
| 12 | `0x0FC08` | `376` | `0x0FEF8` | `0x13790` |
| 13 | `0x13790` | `228` | `0x13958` | `0x15938` |
| 14 | `0x15A3C` | `140` | `0x15B54` | `0x16D3A` |
| 15 | `0x16D3C` | `88` | `0x16DEC` | `0x178F4` |

Total grouped strings found: `2639`.

Example decoded strings using the confirmed on-disc `u16` token order:

```text
table 0x08084 index 0: AT
table 0x08084 index 1: A+
table 0x08084 index 2: DF
table 0x08084 index 6: 体力
table 0x094A8 index 0: ファイター
table 0x09FC8 index 0: ソルジャー
```

### Correspondence to PS1 `SYSTEM.BIN`

The 16 Saturn groups map onto the 16 PS1 `SYSTEM.BIN` groups in the same order:

| Property | PS1 `SYSTEM.BIN` | Saturn `SYSTEM.DAT` |
| --- | ---: | ---: |
| Groups | `16` | `16` |
| Strings | `2620` | `2639` |

Per-group entry counts are identical for `14 / 16` groups; only group 0
(`292` vs `272`), group 1 (`44` vs `41`) and group 15 (`88` vs `92`) differ
slightly. Content aligns by index: in the unit-name group (Saturn `0x09FC8` /
PS1 `0x0A060`, both 130 entries), `127 / 130` strings are byte-identical, and
the only 3 differences (`較者` vs `聖者`) are the same kanji glyph-slot
reordering on an otherwise identical string.

This means the existing PS1 SYSTEM translation (unit/class names, menu labels,
descriptions) ports to Saturn by group+index alignment, exactly like the SCEN
text pool ports by `(chunk, entry)` alignment.

Implication for tooling: `lang5_system_dump.py` / `lang5_system_pack.py` can be
ported by adding an endian-aware mode and Saturn scan start/table offsets. The
PS1 runtime proof about `SYSTEM.BIN` index addressing does not automatically
apply to Saturn; the Saturn executable must be checked before allowing repack.

Reproducible command:

```bash
python3 scripts/saturn_disc.py extract SYSTEM.DAT work/build/saturn/SYSTEM.DAT
python3 scripts/saturn_system_dump.py \
  --system work/build/saturn/SYSTEM.DAT \
  --out work/build/saturn/system_strings.json
```

## `SCEN.DAT`

Confirmed:

- Size: `22910976`.
- Starts with a swapped-word / big-endian-on-disc top-level catalog. This
  describes byte order in the file, not a claim about the Saturn CPU runtime
  endianness.
- First word is `0x00000083`, the catalog entry count (`131`).
- The next `131` entries parse cleanly as `(u32 start_sector, u32 used_size)`.
  `start_sector` is relative to `SCEN.DAT` and uses `0x800`-byte sectors;
  `used_size` is the byte length of the block before zero padding:

```text
00000083
00000001 00009BD8
00000015 00021ADC
00000059 0001B130
00000090 0001DC58
...
```

Properties of this top-level table:

| Property | Value |
| --- | --- |
| Entry count | `131` |
| Pair size | `8` bytes |
| Catalog table size | `0x41C` |
| First payload start | `0x000800` |
| First payload padding after catalog | `0x3E4` bytes |
| `start_sector` order | ascending |
| Allocation unit | `0x800` bytes |
| `used_size <= allocated_size` | all `131` entries |
| Sector padding | all zero |

Payload block layout begins with a fixed `0x30`-byte header. The header values
are also stored in swapped-word / big-endian-on-disc order:

```text
u32 resource_table_offset
u16 category              # observed values: 1 and 6
u16 sub_id
u32 section0_offset       # always 0x30 in the current dump
u32 section1_offset
u32 record_index_offset
u32 resource_map_offset
u32 field_18              # unknown
u32 field_1c              # unknown flags/metadata
u32 field_20              # unknown
u32 field_24              # unknown
u32 field_28              # unknown
u32 field_2c              # unknown
```

The section offsets are valid for all `131` blocks and are ordered as:

```text
section0_offset <= section1_offset <= record_index_offset
  <= resource_map_offset <= resource_table_offset <= used_size
```

The `record_index` section is now confirmed:

```text
u32 record_count
repeat record_count:
    u32 record_id
    u32 record_offset      # relative to the start of this payload block
```

Validation over all payload blocks:

| Property | Value |
| --- | --- |
| Valid block headers | `131 / 131` |
| Valid record-index tables | `131 / 131` |
| Total indexed records | `1820` |
| Category counts | `1: 68`, `6: 63` |
| Empty record-index tables | `4` |
| Non-empty first record starts after table | `127 / 127` |
| All record offsets are in-range | `131 / 131` |

Record offsets are not globally sorted and may repeat, so record span recovery
must sort unique offsets inside each block and use `resource_map_offset` as the
end of the record payload area.

The `resource_map` section is confirmed as fixed 4-byte rows:

```text
repeat until resource_table_offset:
    u16 record_id
    u8  resource_slot
    u8  variant
```

Validation over all payload blocks:

| Property | Value |
| --- | --- |
| Valid resource-map sections | `131 / 131` |
| Total rows | `1362` |
| Row size | `4` bytes |
| Observed resource slots | `0..15` |
| Observed variants | `0`, `1`, `2`, `3` |
| Non-empty chunks with every indexed non-`FFFF` record id mapped | `51 / 127` |

Slot distribution:

```text
0:130 1:133 2:140 3:126 4:124 5:140 6:141 7:98
8:100 9:81 10:55 11:40 12:23 13:16 14:10 15:5
```

Variant distribution:

```text
0:1128 1:147 2:86 3:1
```

This section does not list every `record_index` record. It appears to map only
records that need a local resource/string association. Slots `14` and `15` are
real, so tooling must not hardcode a maximum slot of `13`.

The `resource_table` section is partially decoded. The first 14 `u32` values
are sorted offsets inside the same section and are in-range for all `131`
blocks. The next stable fields are:

```text
u32 first_14_offsets[14]
u32 field_38          # observed values 6..16, meaning unknown
u32 field_3c          # offset to the local index table described below
u32 field_40          # often FFFFFFFF, but not always a sentinel
```

`field_3c` points to a local indexed table inside `resource_table`:

```text
u32 total_size
u16 entry_offsets[count]
byte/word payload entries...
```

`count` is derived from the first offset:

```text
count = (entry_offsets[0] - 4) / 2
```

Validation over all payload blocks:

| Property | Value |
| --- | --- |
| Valid local index tables | `131 / 131` |
| Total indexed entries | `10071` |
| Entry count range per block | `8..372` |
| Local table `total_size` range | `100..25484` bytes |
| Entries whose span contains `FFFF`/`FFFE` terminator | `10068 / 10071` |

The first entries in many blocks are readable JP names when decoded with the
current token table, for example:

```text
0094 008D 00BB FFFF                  -> シグマ
00C6 00BD 009D FFFF                  -> ラムダ
008C 00C6 00C9 00A0 00A5 FFFF        -> クラレット
```

This is the scenario text pool. It is now confirmed as the store that holds
every speaker name and every dialogue/event line for the block, in reading
order, using the same broad control-word grammar as the PS1 script (`FFFC`
soft break, `FFFD`/`FFFE`/`FFFF` terminators, `FFF3`–`FFF8` inline markup,
`FB00`+speaker-byte name control). `scripts/saturn_scen_text.py` walks all
blocks and emits every entry with a stable `(chunk_index, entry_index)` id.

| Property | Value |
| --- | --- |
| Blocks parsed | `131 / 131` |
| Total text entries | `10071` |
| Terminated (real text) entries | `10068` |
| Control-only entries | `3` (single-word `F702` in chunk `38`) |

The three `F702` entries in chunk `38` sit between shop-style confirmation
prompts (`…でよろしいですか？`) and carry no text terminator. `F702` is a
standalone control/placeholder token, not a string. Every other entry is text.

### Correspondence to the PS1 script

The Saturn text pool maps directly onto the PS1 per-chunk record text:

| Property | PS1 `SCEN.DAT` | Saturn `SCEN.DAT` |
| --- | ---: | ---: |
| Chunks | `131` | `131` |
| Text records / entries | `10244` | `10071` |

Per-chunk entry counts match exactly for `95 / 131` blocks and are within `±2`
for `111 / 131`. All differences are small and negative (Saturn keeps a few
fewer entries per block, consistent with PS1 counting trailing blank or
differently-split records). The chunk ordering is 1:1. This means the existing
PS1 translation can be ported to Saturn by `(chunk, entry)` alignment with only
minor per-block reconciliation, without first solving the record-payload or
resource grammars.

Reproducible command:

```bash
python3 scripts/saturn_scen_text.py \
  --scen work/build/saturn/SCEN.DAT \
  --out work/build/saturn/scen_text.json \
  --out-csv work/build/saturn/scen_text.csv
```

### Record payloads are binary resource data, not text

The `record_index` records point at the payload area between the record-index
table and `resource_map_offset`. These payloads are **not** scenario text: they
are high-entropy binary resources (tilemaps / graphics / event VM data). For
example, chunk `24` record `0` begins `4D03 1420 2000 0200 0000 0657 0000 067D`
followed by a dense binary body, and its `resource_map` rows group record ids
into `(resource_slot, variant)` sets (e.g. ids `E1..EA` → slots `5..7`,
variant `1`). Translation work does not need to decode this area; all
translatable strings are in the `field_3c` text pool above.

Important negative facts:

- `resource_slot` is not proven to be a direct index into only the first 14
  offsets, because slots `14` and `15` exist.
- `field_40` must not be treated as a mandatory `FFFFFFFF` sentinel; many
  chunks contain values shaped like token data at that position.
- The exact relationship between `resource_map` rows, `record_index` payloads
  and `resource_table` local index entries is still open.

The PS1 text-block locator does not work:

- No little-endian PS1-style text blocks found in the first 1 MiB.
- No swapped-word/on-disc BE PS1-style text blocks found in the first 1 MiB.

However, scenario text/token streams are present. A read-only scan of
`0x000000..0x060000` finds `619` swapped-word/on-disc BE token-stream
candidates.
Inside payload/resource regions there are clear script tokens using the same
broad token model as PS1:

```text
offset 0x4D328:
0253 0254 0058 005C 029C 0031 0004 FFFC ...

decoded with the current PS1 JP table:
鞋弱には溶い.<$FFFC>...
```

```text
offset 0x4DC64:
0057 006E 0078 007D 0045 0070 005A 0034 ...
... FFFE FB00 0064 ...
```

```text
offset 0x4DE90:
004D 0038 0076 FFF5 FFF8 048C 048C 0004 FFFE FB00 0072 ...
```

These free-standing token streams are the same text captured by the `field_3c`
text pool above; the scanner simply finds them without the index-table walk.
The catalog, local record index, resource map and text pool are all mapped, and
the text-extraction path for translation is complete. The still-undecoded parts
(record-payload grammar and full `resource_table` resource semantics) are only
needed for graphics/map/event editing, not for text.

## Glyph Map vs PS1

Saturn script text uses swapped-word/on-disc BE `u16` tokens whose ids overlap
the PS1 Japanese table but are **not** a full match:

- **Kana is identical.** Katakana names decode exactly (`シグマ`, `クラレット`,
  `ランフォード…`, `レインフォルス`) and hiragana decodes cleanly.
- **Control words are identical** (`FFFC`, `FFFD`, `FFFE`, `FFFF`, `FFF3`–`FFF8`,
  `FB00`+arg).
- **Kanji slots are reordered/replaced.** Some kanji decode correctly, others
  do not. The root cause is the font plane itself (see the Font section): the
  Saturn `SYSTEM.DAT` glyph slot at a given id often holds a different kanji
  than PS1. Confirmed alignment against the PS1 script and font:

| Saturn token | PS1 glyph slot | Saturn glyph slot | Note |
| --- | --- | --- | --- |
| `0x020D` | 差 | 元 | `ランフォード元帥` (Lanford the Marshal) |
| `0x020E` | 元 | 帥 | Saturn slot holds a different kanji than PS1 |
| `0x0138` | 部 | 部 | identical slot — `部下` decodes correctly |
| `0x0122` | 下 | 下 | identical slot |

Because token ids are glyph-plane indices, the fix is a Saturn-specific glyph
table, derived by rendering the divergent Saturn slots (or by aligning Saturn
entries to matched PS1 records). This does **not** block the translation port:
kana + control structure decode correctly, which is enough to align Saturn text
entries with PS1 records structurally (see the per-chunk correspondence above),
and inserted target text will use a project-authored font/table regardless.

## Font (`SYSTEM.DAT` glyph plane)

The in-game text font is owned by `SYSTEM.DAT`, in the same format as PS1
`SYSTEM.BIN`:

| Property | Value |
| --- | --- |
| Cell | `12x12`, `1bpp`, `18` bytes/glyph, `12` bits/row MSB-first, rows packed continuously |
| Glyph address | `index * 18` from offset `0` |
| Glyph slots | `0..1820` (same as PS1) |
| Byte order | natural (glyph bytes are **not** byte-swapped, unlike the `u16` text tokens) |

Both the SYSTEM UI text and the SCEN dialogue index into this one plane: SCEN
token `0x0094` renders シ from the `SYSTEM.DAT` font, matching `シグマ` in the
script. `WD_FONT.BIN` (8 KiB) is not this font — it is repeating dither/window
pattern data (`0xAA`/`0x99`/`0x66`), not text glyphs.

Comparison of glyph slots `0..1820` against PS1 `SYSTEM.BIN`:

| Property | Value |
| --- | --- |
| Identical slots | `465` |
| Differing slots | `1356` |
| First differing slot | `0x00CA` (starts at byte `0xE34`; first differing byte `0xE35`, the known divergence point) |
| Main differing bands | `0x0185..0x025D`, `0x025F..0x02CA`, `0x02CC..0x05AC`, `0x05FC..0x071C` |

Kana, punctuation and the early shared range (slots `0x00..0xC9` and the
`0x00CB..0x0184` band) are byte-identical, which is why kana and some kanji
decode correctly. The large `0x0185+` kanji region is reordered/replaced.

Implication for tooling: the glyph format and slot layout match PS1 exactly, so
`lang5_build_font.py`'s slot-rewrite approach (draw the target alphabet into
slots `0..1820`) is directly portable to Saturn `SYSTEM.DAT`; only the file
offset of the glyph plane and the surrounding container differ.

Reproducible command:

```bash
python3 scripts/saturn_disc.py extract SCEN.DAT work/build/saturn/SCEN.DAT
python3 scripts/saturn_scen_scan.py \
  --scen work/build/saturn/SCEN.DAT \
  --out work/build/saturn/scen_scan.json
```

## Asset-Like `.DAT` Containers

Several Saturn `.DAT` files start with a swapped-word/on-disc BE
directory-like header:

```text
u32 count
repeat count:
    u32 a
    u32 b
```

Confirmed examples:

| File | Size | Count | First entries |
| --- | ---: | ---: | --- |
| `TITLE1.DAT` | `123944` | `2` | `(0x14, 0x1FD4)`, `(0x1FE8, 0x1C440)` |
| `TITLE2.DAT` | `118888` | `2` | `(0x14, 0x1FD4)`, `(0x1FE8, 0x1B080)` |
| `OPEN.DAT` | `351404` | `3` | `(0x1C, 0x6C1C)`, `(0x6C38, 0x3C440)`, `(0x43078, 0x12C34)` |
| `CAST.DAT` | `242700` | `5` | `(0x2C, 0x7430)`, `(0x745C, 0x26580)`, ... |
| `STAFF.DAT` | `531136` | `6` | `(0x34, 0x3E88)`, `(0x3EBC, 0x39400)`, ... |
| `SND_DAT.BIN` | `135220` | `2` | `(0x14, 0x67F2)`, `(0x6808, 0x1A82A)` |

The meaning of each pair is not fully proven. For title/open/cast/staff assets,
the `a` offset points to a descriptor/header block and the `b` offset points to
pixel payload bytes. Example `TITLE1.DAT` entry 0 descriptor:

```text
a = 0x14:
00001E60 0050001C 0028001C 00000020 00000200 00000420 000015A0 00000000
A100DFFF DBDFE7DF FBBED7DF DFBFEFBE ...
```

Partially decoded descriptor fields (all swapped-word/on-disc BE):

- `0x0050 x 0x001C` and `0x0028 x 0x001C` read as `width x height` pairs
  (`80x28`, `40x28`), followed by a series of `u32` sub-offsets
  (`0x20, 0x200, 0x420, 0x15A0`) into the payload.
- The trailing `A100DFFF DBDFE7DF …` words look like a 16bpp color block.

The `b` pixel payload for `TITLE1.DAT` begins `FFFF FFFF … 00FF FFFF 0000 FFFF`.
Read as `u16`, the `FFFF → 00FF → 0000` run at a shape edge looks like
antialiasing in **16bpp RGB555 direct colour** (white to black), which suggests
the payload is direct-colour pixels rather than CLUT indices. This is a strong
hypothesis, not yet confirmed: the exact pixel dimensions, row stride and how the
descriptor sub-offsets tile the payload are still undecoded.

These are not PS1 `IMG.DAT` records. A Saturn title/bitmap editor will need a
separate decoder; the container directory, descriptor `width x height` fields and
likely 16bpp payload are the current confirmed/hypothesised starting points.

## Insertion / Repack Model

Applying the translation is a **fixed-size repack**, exactly like the PS1 flow:
every file keeps its length (the disc layout forbids growth), and each text
structure is rebuilt in place with translated content that must fit its original
byte budget.

### SCEN scenario text — proven

The `field_3c` text pool is rebuilt in place per block. Its region layout is::

    u32 total_size
    u16 entry_offsets[count]      # relative to the region base, u16
    entry payloads (u16 tokens, FFFE/FFFF-terminated), concatenated
    zero padding to total_size

`saturn_scen.build_local_index_table` / `splice_local_index_table` rebuild the
region from a list of token entries and splice it back. The model is validated:

- Rebuilding all 131 blocks from their own parsed entries reproduces the file
  **byte-for-byte** (`131/131` identical), so the layout is fully understood.
- A modified entry keeps the file length, leaves every byte outside the region
  unchanged, and reads back correctly; other entries are identical up to their
  terminator (freed space becomes trailing zero padding after a terminator,
  which the engine never reads).

Constraints for insertion:

- Preserve entry **count and order** (entries are addressed through the
  regenerated offset array).
- The whole region must stay under `0xFFFF` bytes (offsets are `u16`).
- If the content fits the original `total_size`, nothing else in the block moves.

Growth (translated text longer than Japanese — the common case for Russian):
because the text table sits among other resources, it cannot grow in place, so
`saturn_scen.rebuild_block_text` **appends** the enlarged table at the block end
and repoints the `resource_table.field_3c` pointer to it (only that 4-byte
pointer changes; every other resource is byte-preserved). The block then grows,
and `saturn_scen.repack_scen` re-lays out all blocks at 0x800-sector alignment
and rewrites the top-level catalog (`count`, `start_sector`, `used_size`). This
is validated: appending a grown table reads the translated entries back
correctly with all other bytes intact, an empty repack reproduces the file
byte-for-byte, and applying the Russian pack grows the file and still re-parses
across all 131 blocks.

### Universality

The `data/lang/<code>` pack is console-agnostic: the same translation applies to
both PS1 and Saturn. Because the target alphabet occupies the same font slots on
both, a record's encoded token stream is identical; only the byte order and
container differ. `scripts/lang5_saturn_apply.py` reuses the PS1 dump
(`parse_dump_file`), codec (`Codec`) and `.tbl` unchanged, mapping Saturn block
`c` entry `e` to PS1 chunk `c` record `e+1`. Platform is therefore a build-time
choice, not a property of the pack. On the current RU pack it applies 89/131
blocks automatically; the remaining 36 have a per-chunk record-count delta that
needs mapping reconciliation (a data task, not a format gap), and 6 are empty.

### SYSTEM UI text — same offset-table repack

`SYSTEM.DAT` groups are the same offset-table structure as PS1, so the PS1
`--repack` path (regenerate each group's offset table, keep string indices)
ports via the shared `lang5_offsetgroups` model with the Saturn BE config.
Index addressing is proven on PS1 and structurally implied on Saturn (the
offset-table indirection exists precisely to allow it); a final guarantee needs
the Saturn executable, but the fixed-size in-place repack is safe regardless as
long as string indices and group layout are preserved.

### Font — slot rewrite

Cyrillic glyphs are drawn into `SYSTEM.DAT` glyph slots `0..1820` (same
12x12x18 format as PS1), so `lang5_build_font.py`'s slot-rewrite ports directly;
only the glyph-plane file offset differs.

### Still open for a shippable patch

- The Saturn↔PS1 mapping deltas (a few entries per chunk) must be reconciled so
  each Saturn entry pulls the right translated string.
- The patch/output format for a mixed-mode BIN/CUE after in-place edits (the PS1
  flow emits a PPF against a single `.bin`).

## Executable / Code Files

Likely code-bearing files:

| File | Size | Notes |
| --- | ---: | --- |
| `A0LANG5.BIN` | `232660` | Boot or early program module |
| `PROG1.BIN` | `508908` | Program code/data |
| `PROG2.BIN` | `78548` | Program code/data, references `LANG5.CPK` in plain ASCII |

The PS1 executable patching logic is not portable. Saturn uses a different CPU
and memory model; all runtime proofs and patches must be rediscovered in the
Saturn code.

## Applicability To The Current Project

Reusable with little conceptual risk:

- Existing English/Russian translation content as translation memory.
- Canonical terminology (`names.csv`, `glossary.csv`) after mapping Saturn
  source ids to PS1 ids.
- Review workflow concepts.
- Text token codec concepts: endian and record location are now solved; the
  Saturn SCEN text pool aligns to PS1 chunks 1:1 and the SYSTEM groups align to
  PS1 groups 1:1, so both text stores port from the existing translation.
- The slot-rewrite font builder (`lang5_build_font.py`): the Saturn font is the
  same 12x12x18 PS1 format in `SYSTEM.DAT`, so drawing the target alphabet into
  slots `0..1820` ports directly.

Partially reusable after platform adaptation:

- `SYSTEM.BIN` dumper/packer logic: same group concept, but Saturn
  `SYSTEM.DAT` uses swapped/on-disc BE words and shifted groups.
- Scenario validation concepts: control words match the PS1 model, but record
  payload/VM metadata is still undecoded (not needed for text).

Not directly reusable:

- PS1 `iso_mode2.py` as-is.
- PS1 `SCEN.DAT` chunk pointer / local record table parser.
- PS1 `IMG.DAT` title/poem/bitmap tooling.
- PS1 executable patches (`SLPS_018.19`) and all runtime addresses.
- PPF target assumptions for the PS1 `.bin`.

## Work Tracker

Current focus: the minimally-necessary text path for translation is complete —
both SCEN and SYSTEM text are located, deterministically dumpable, and mapped
1:1 to the PS1 script/UI, and the font format is confirmed PS1-compatible.
Remaining work is secondary to reading/porting the text: full title/bitmap
pixel decode, the Saturn-specific kanji table (to read JP kanji), and the
insertion/repack path (needs Saturn executable analysis for string addressing).
The record-payload and full `resource_table` grammars are only needed for
graphics/map/event editing, not for text.

### Milestones

- [x] Parse Saturn CUE and track layout.
- [x] Read track 1 as `MODE1/2352` ISO9660.
- [x] List and extract track-1 files without modifying the image.
- [x] Map ISO `ADPCM/**/*.XA` entries to track-2 physical sectors.
- [x] Confirm the 225-sector logical-to-physical XA correction.
- [x] Dump Saturn `SYSTEM.DAT` string groups using the confirmed on-disc word order.
- [x] Parse the `SCEN.DAT` top-level 131-entry table.
- [x] Scan low `SCEN.DAT` regions for swapped-word/on-disc BE token streams.
- [x] Map `SCEN.DAT` top-level catalog as `(start_sector, used_size)`.
- [x] Map `SCEN.DAT` fixed payload header and section offsets.
- [x] Map `SCEN.DAT` local `record_index` section.
- [x] Map `SCEN.DAT` `resource_map` row structure.
- [x] Map `SCEN.DAT` `resource_table.field_3c` local index table header.
- [x] Confirm `field_3c` local index table is the scenario text pool.
- [x] Build a deterministic Saturn script dump with stable `(chunk, entry)` ids.
- [x] Compare Saturn script entries against PS1 `work/scriptdump/` (131 chunks 1:1).
- [x] Confirm Saturn `SYSTEM.DAT` groups correspond 1:1 to PS1 `SYSTEM.BIN`.
- [x] Confirm the Saturn dialogue/control-word grammar (matches PS1 model).
- [x] Characterize the Saturn glyph map vs PS1 (kana identical, kanji reordered).
- [x] Classify the Saturn font storage and renderer cell model (`SYSTEM.DAT`, 12x12x18, PS1-compatible).
- [ ] Build the Saturn-specific kanji table (only needed to fully read JP kanji).
- [ ] Decode at least one Saturn title/bitmap container.
- [x] Define the SCEN insertion/repack model (fixed-size field_3c rebuild).
- [x] Validate the model by 131/131 byte-identical round-trip + substitution.
- [ ] Reconcile the Saturn<->PS1 per-chunk mapping deltas for string pull.
- [ ] Wire the Saturn build flow into the pipeline alongside PS1.
- [ ] Decode `SCEN.DAT` record-payload grammar (graphics/map/event editing only).
- [ ] Decode `SCEN.DAT` `resource_table` resource semantics (non-text editing only).

### Tested Hypotheses

| Hypothesis | Status | Evidence / Result |
| --- | --- | --- |
| Saturn track 1 can be read with the PS1 `iso_mode2.py` sector model. | Rejected | PS1 helper assumes MODE2 user offset 24; Saturn track 1 is MODE1 user offset 16. |
| Track 2 is a second ISO9660 filesystem. | Rejected | Track 2 has XA subheaders and no ISO PVD; ISO entries in `ADPCM/` point into it. |
| `ADPCM/**/*.XA` extents point directly to physical raw sectors. | Rejected | Physical sector is ISO extent minus the 225-sector pregap. |
| `SYSTEM.DAT` text tables are PS1-style little-endian groups. | Rejected | Little-endian scan finds no groups; swapped/on-disc BE scan finds 16 valid groups. |
| `SYSTEM.DAT` keeps the same broad text-table concept as PS1. | Confirmed | 16 swapped/on-disc BE groups decode to unit/menu/system strings; total 2639 strings. |
| Saturn `SYSTEM.DAT` groups correspond 1:1 to PS1 `SYSTEM.BIN` groups. | Confirmed | Both 16 groups in the same order; 14/16 have identical entry counts; the unit-name group is 127/130 byte-identical by index (3 diffs are glyph-slot reordering). |
| Saturn `SCEN.DAT` top-level entries are `(event id, pointer)`. | Rejected | First field multiplied by `0x800` gives every payload start; second field is always `used_size <= allocated_size`, with zero padding after it. |
| Saturn `SCEN.DAT` top-level catalog is `(start_sector, used_size)`. | Confirmed | All 131 entries validate; first payload starts at `0x800`, allocation is sector-aligned, all padding bytes are zero. |
| Saturn `SCEN.DAT` payloads have a fixed header with section offsets. | Confirmed | All 131 blocks have ordered section offsets from `0x30` through `resource_table_offset`. |
| Saturn `SCEN.DAT` has a local record index. | Confirmed | At `record_index_offset`: `u32 count`, then `(record_id, record_offset)` pairs; 1820 total indexed records, all offsets in range. |
| Saturn `SCEN.DAT` `resource_map` rows are 4-byte `(record_id, resource_slot, variant)` records. | Confirmed | All 131 sections validate as 4-byte rows; 1362 rows; slots 0..15 and variants 0..3 observed. |
| Saturn `SCEN.DAT` `resource_slot` is always below 14. | Rejected | Slots 14 and 15 occur in several chunks. |
| `resource_table + 0x40` is always an `FFFFFFFF` sentinel. | Rejected | 45 chunks have `FFFFFFFF`; the rest contain non-sentinel-looking values, often shaped like token data. |
| `resource_table.field_3c` points to a local indexed table. | Confirmed | All 131 blocks validate as `u32 total_size` plus `u16` offsets; 10071 entries total. |
| The `field_3c` local indexed table is the scenario text pool. | Confirmed | 10068/10071 entries are terminated text; the 3 exceptions are `F702` control-only entries in chunk 38. Names + dialogue + event lines in reading order, PS1 control grammar. |
| Saturn `SCEN.DAT` chunks correspond 1:1 to PS1 `SCEN.DAT` chunks. | Confirmed | Both have 131 chunks; per-chunk text counts match exactly for 95/131 and within ±2 for 111/131; all deltas small and negative. |
| Saturn `SCEN.DAT` record payloads are text records. | Rejected | Payloads between record-index and `resource_map` are high-entropy binary resources (tilemaps/graphics/VM); text lives only in the `field_3c` pool. |
| Saturn `SCEN.DAT` contains raw swapped-word/on-disc BE token streams. | Confirmed | Scanner finds 619 candidates; these are the same entries the `field_3c` walk yields. |
| PS1 JP token table is exact for Saturn scenario text. | Rejected (partial map) | Kana and control words match exactly; kanji slots are reordered (e.g. 元 is Saturn `0x020D` vs PS1 `0x020E`, while `部下` at `0x0138`/`0x0122` is unshifted). |
| Saturn `SYSTEM.DAT` uses the PS1 12x12x18 font format. | Confirmed | Glyph at `index*18`, 12 bits/row MSB-first; `下`/`部`/`シ` render correctly and are byte-identical to PS1. |
| The Saturn text font equals the PS1 font. | Rejected (partial) | 465/1821 glyph slots byte-identical; 1356 differ, all in the `0x0185+` kanji region; kana identical. |
| `WD_FONT.BIN` holds the in-game text font. | Rejected | It is repeating dither/window pattern data (`0xAA`/`0x99`/`0x66`), not 12x12 glyphs; SYSTEM.DAT owns the text font. |
| The SCEN `field_3c` text pool can be rebuilt in place at fixed size. | Confirmed | Rebuilding all 131 blocks from their parsed entries reproduces the file byte-for-byte; a substitution preserves length and every byte outside the region. |
| Saturn title/OPEN/CAST/STAFF `.DAT` files are PS1 `IMG.DAT` records. | Rejected | They use separate swapped-word/on-disc BE directory-like headers and different payload layout. |
| Saturn title assets store a descriptor block with `width x height` fields plus a pixel payload. | Confirmed (partial) | `TITLE1.DAT` entry-0 descriptor holds `80x28`/`40x28` dims and payload sub-offsets; the `a`/`b` directory splits descriptor from pixels. |
| The Saturn title pixel payload is 16bpp RGB555 direct colour. | Plausible / unconfirmed | `FFFF→00FF→0000` `u16` runs at shape edges look like white-to-black antialiasing; exact dims/stride not yet decoded. |

### Immediate Next Steps

1. Confirm whether Saturn `SYSTEM.DAT` runtime accesses strings by table index
   (like PS1) or by absolute offset — this gates SYSTEM/text repack.
2. Decode one Saturn title/bitmap container (`TITLE1.DAT`) for graphic assets.
3. Build the Saturn-specific kanji table by aligning Saturn entries with matched
   PS1 records, so JP kanji reads cleanly (optional: structural alignment already
   works without it).

## Next Reverse-Engineering Plan

Completed:

- Read-only Saturn disc explorer:
  - CUE parser;
  - MODE1 ISO extraction from track 1;
  - XA entry reader for `ADPCM/**/*.XA` with the 225-sector correction.
- Read-only Saturn SYSTEM dumper:
  - swapped-word/on-disc BE string groups;
  - Saturn scan start;
  - JSON output compatible with review/comparison scripts.
- Initial `SCEN.DAT` scanner:
  - top-level `(start_sector, used_size)` catalog parser;
  - swapped-word/on-disc BE token-stream candidate scan;
- `SCEN.DAT` catalog and local record index:
  - top-level `(start_sector, used_size)` catalog;
  - fixed per-payload section offsets;
  - local `(record_id, record_offset)` tables.
  - `resource_map` rows as `(record_id, resource_slot, variant)`;
  - derived record spans for payload grammar analysis.
- `SCEN.DAT` scenario text extraction:
  - `field_3c` local index table confirmed as the text pool;
  - deterministic dump with stable `(chunk, entry)` ids (`saturn_scen_text.py`);
  - 131-chunk 1:1 correspondence with the PS1 script;
  - glyph map characterized (kana identical, kanji piecewise-reordered).

Next:

1. Classify the Saturn font:
   - `SYSTEM.DAT` font-like prefix;
   - `WD_FONT.BIN`;
   - renderer cell size and glyph indexing.
3. Classify title/bitmap assets:
   - decode one `TITLE1.DAT` or `TITLE2.DAT` entry;
   - determine palette, dimensions and layout;
   - compare with PS1 title asset responsibilities.
4. Only after read-only dump parity is proven, design insertion/repack rules.

## Open Questions

Resolved for the translation text path:

- Scenario text is the `field_3c` local index pool; record payloads are binary
  resources, not text. Text streams are raw swapped-word tokens (uncompressed).
- Saturn chunks map 1:1 to PS1 chunks, so the existing translation can be ported
  by `(chunk, entry)` alignment.

Resolved for the font/render path:

- `SYSTEM.DAT` owns the text font (12x12x18, glyph at `index*18`, PS1-compatible
  slots `0..1820`); `WD_FONT.BIN` is dither/window pattern data. SCEN dialogue
  and SYSTEM UI share this one plane. The slot-rewrite font builder is portable.

Still open:

- What is the exact Saturn kanji slot ordering (needed only to read JP kanji)?
- Does Saturn `SYSTEM.DAT` runtime access strings by table index like PS1, or by
  absolute offset? (Gates SYSTEM repack.)
- What is the `resource_table`/record-payload grammar? (Graphics/map/event
  editing only, not text.)
- Which title asset corresponds to the PS1 `IMG.DAT` title-credit assets?
- What patch format is appropriate for Saturn mixed-mode BIN/CUE after edits?
