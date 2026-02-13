# Langrisser V PS1 Translation Reverse Status

## Done
- Verified FEIDIAN pipeline against `SYSTEM.BIN` using:
  - `php -d short_open_tag=1 feidian.php -r 12,12,32,57,0x0 /workspace/work/extracted/SYSTEM.BIN /workspace/work/font_probe/l512x12qg8`
- Confirmed encoding model from forum + binary:
  - token is little-endian word: `char + bank`
  - example verified in data: `ランフォード元帥{end}`
  - `C600 CD00 B200 8600 D100 A600 0E02 0F02 FFFF`
- Implemented/kept extraction scripts:
  - `scripts/lang5_scen_extract.py`
  - `scripts/lang5_story_extract.py`
  - `scripts/lang5_apply_font_ocr_map.py`
  - `scripts/lang5_system_extract.py`
- Recovered deterministic katakana map from SYSTEM table block (`0x008C02`) and saved in:
  - `scripts/lang5_token_map_manual.json`
- Confirmed many proper nouns decode correctly in `SCEN`/`SYSTEM`:
  - `ランフォード`, `ギザロフ`, `元帥`, `インフォルス`, `ローゼンシル`, etc.
- OCR/transcribed first provided in-game dialogue screenshots (human-readable Japanese lines captured in analysis outputs).

## Not Done Yet
- Full hiragana/kanji mapping for all active dialogue tokens is incomplete.
- First tutorial dialogue lines from screenshots are not yet 100% traced to exact token runs and offsets in `SYSTEM.BIN`.
- End-to-end pipeline `extract -> align JP source text -> insert EN -> build PPF` is not complete yet.

## Current Evidence Level
- Encoding structure: high confidence.
- Katakana + punctuation + selected kanji mapping: high confidence.
- General dialogue body (hiragana-heavy lines): partial decode only.

## Next Steps
1. Recover hiragana table deterministically (same method as katakana table block), or derive with strict token-line matching from known screenshot lines.
2. Extend manual map from screenshot-anchored lines with exact token offsets.
3. Re-run:
   - `scripts/lang5_apply_font_ocr_map.py`
   - `scripts/lang5_system_extract.py`
4. Produce validated JP source dump with per-line offsets + scenario/chunk IDs.
5. Start inserter constraints check (line length/control codes), then PPF generation.
