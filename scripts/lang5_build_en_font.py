#!/usr/bin/env python3
"""Patch EN glyphs into the SYSTEM.BIN font plane and emit the EN table.

Slot assignments come from data/font_mapping/en_slot_assignments.csv
(sacrificed rare-kanji slots chosen by usage analysis). The emitted .tbl
contains the full JP map minus sacrificed chars plus the EN additions and
the space token, so untouched JP lines still encode.
"""
import argparse
import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

GLYPH_W = 12
GLYPH_H = 12
GLYPH_BYTES = 18

# Spleen 6x12 (BSD) is a bitmap font drawn exactly on a 6x12 grid:
# ascent 9 + descent 3 = 12 rows, two glyphs tile a 12x12 cell perfectly
# and the x-height is taller than PixelMplus10. PixelMplus10 kept as an
# alternative.
FONT_CANDIDATES = [
    "data/fonts/spleen-6x12.bdf",
    "data/fonts/PixelMplus10-Regular.ttf",
]
# The game's native A-Z/digit glyphs put their ink bottom on row 9, so EN
# letter bodies must end there too or mixed words jitter by 1px. Baseline
# row 10 achieves that; descenders get squashed from 3px to 2px, which is
# the lesser evil.
BASELINE_ROW = 10


def pick_fonts(path: str, size: int) -> list[ImageFont.FreeTypeFont]:
    """All available candidate fonts; the first is primary, the rest are
    per-glyph fallbacks for characters the primary lacks (e.g. ♀/♂ live in
    PixelMplus but not in Spleen)."""
    fonts = []
    for cand in ([path] if path else []) + FONT_CANDIDATES:
        if cand and Path(cand).exists():
            fonts.append(ImageFont.truetype(cand, size=12 if cand.endswith(".bdf") else size))
    if not fonts:
        raise SystemExit("no usable TTF found")
    return fonts


def font_has(font: ImageFont.FreeTypeFont, ch: str) -> bool:
    # A char missing from the font renders as the same mask as a codepoint
    # that is guaranteed to be absent.
    def mask_bytes(c: str) -> bytes:
        mask = font.getmask(c)
        return bytes(mask) if mask.size[0] else b""
    return mask_bytes(ch) != mask_bytes("\U000E0000")


def render_tile(text: str, fonts: list[ImageFont.FreeTypeFont]) -> bytes:
    """Render 1 or 2 characters into one 12x12 tile on a common baseline.

    Pairs are drawn at a 6px pitch (PixelMplus halfwidth glyphs are 5px
    wide), which is what makes EN text as dense as the JP original and
    removes the huge inter-letter gaps of one-letter-per-cell text.
    Single lowercase/punctuation is left-aligned so word tails join up.
    """
    img = Image.new("L", (GLYPH_W, GLYPH_H), 255)
    d = ImageDraw.Draw(img)
    for k, ch in enumerate(text[:2]):
        font = next((f for f in fonts if font_has(f, ch)), fonts[0])
        ascent, _descent = font.getmetrics()
        bbox = d.textbbox((0, 0), ch, font=font)
        d.text((k * 6 - bbox[0], BASELINE_ROW - ascent), ch, font=font, fill=0)
    img = img.point(lambda v: 0 if v < 140 else 255)
    px = img.load()
    out = bytearray(GLYPH_BYTES)
    for i in range(GLYPH_W * GLYPH_H):
        if px[i % GLYPH_W, i // GLYPH_W] == 0:
            out[i // 8] |= 1 << (7 - (i % 8))
    return bytes(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--groups-report", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--assignments", default="data/font_mapping/en_slot_assignments.csv")
    ap.add_argument("--system-bin", default="work/extracted/SYSTEM.BIN")
    ap.add_argument("--out-system-bin", default="work/build/SYSTEM.BIN.en")
    ap.add_argument("--out-tbl", default="work/tables/lang5_en.tbl")
    ap.add_argument("--font", default="")
    ap.add_argument("--font-size", type=int, default=10)
    args = ap.parse_args()

    assignments: dict[int, str] = {}
    for row in csv.DictReader(open(args.assignments, encoding="utf-8")):
        idx = int(row["index_dec"])
        if idx > 1820:
            raise SystemExit(
                f"slot {idx} is beyond the font plane (glyphs end at 1820; "
                "tiles 1821+ hold menu data)"
            )
        assignments[idx] = row["en_char"]

    tok2char: dict[int, str] = {}
    for row in csv.DictReader(open(args.groups_report, encoding="utf-8")):
        if row["index_dec"].isdigit() and len((row["char"] or "")) == 1:
            tok2char[int(row["index_dec"])] = row["char"]
    # An assigned char must win over a native glyph with the same label
    # (the JP font has its own a/m/p for am/pm clocks; they are styled
    # fullwidth and clash visually with the rendered lowercase). The
    # encoder takes the lowest token per char, so drop the duplicates.
    assigned_chars = set(assignments.values())
    for tok in [t for t, c in tok2char.items() if c in assigned_chars]:
        del tok2char[tok]
    for tok, ch in assignments.items():
        tok2char[tok] = ch
    tok2char[0x0000] = " "
    # ASCII normalization targets for EN text on native fullwidth glyphs.
    tok2char.setdefault(0x0005, "？")
    tok2char.setdefault(0x0006, "！")

    fonts = pick_fonts(args.font, args.font_size)
    data = bytearray(Path(args.system_bin).read_bytes())
    for tok, ch in assignments.items():
        data[tok * GLYPH_BYTES : (tok + 1) * GLYPH_BYTES] = render_tile(ch, fonts)

    out_bin = Path(args.out_system_bin)
    out_bin.parent.mkdir(parents=True, exist_ok=True)
    out_bin.write_bytes(bytes(data))

    lines = ["# Langrisser V EN insert table (generated)", "# Format: HHHH=c"]
    for tok in sorted(tok2char):
        lines.append(f"{tok:04X}={tok2char[tok]}")
    out_tbl = Path(args.out_tbl)
    out_tbl.parent.mkdir(parents=True, exist_ok=True)
    out_tbl.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"glyphs_patched={len(assignments)} out_bin={out_bin} out_tbl={out_tbl}")


if __name__ == "__main__":
    main()
