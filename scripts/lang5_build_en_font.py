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

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def pick_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    for cand in ([path] if path else []) + FONT_CANDIDATES:
        if cand and Path(cand).exists():
            return ImageFont.truetype(cand, size=size)
    raise SystemExit("no usable TTF found")


def render_tile(ch: str, font: ImageFont.FreeTypeFont) -> bytes:
    """Render with a common baseline so letters do not jump vertically."""
    img = Image.new("L", (GLYPH_W, GLYPH_H), 255)
    d = ImageDraw.Draw(img)
    ascent, _descent = font.getmetrics()
    baseline = 10  # leaves 2 rows for descenders
    bbox = d.textbbox((0, 0), ch, font=font)
    x = (GLYPH_W - (bbox[2] - bbox[0])) // 2 - bbox[0]
    d.text((x, baseline - ascent), ch, font=font, fill=0)
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
    ap.add_argument("--font-size", type=int, default=11)
    args = ap.parse_args()

    assignments: dict[int, str] = {}
    for row in csv.DictReader(open(args.assignments, encoding="utf-8")):
        assignments[int(row["index_dec"])] = row["en_char"]

    tok2char: dict[int, str] = {}
    for row in csv.DictReader(open(args.groups_report, encoding="utf-8")):
        if row["index_dec"].isdigit() and len((row["char"] or "")) == 1:
            tok2char[int(row["index_dec"])] = row["char"]
    for tok, ch in assignments.items():
        tok2char[tok] = ch
    tok2char[0x0000] = " "

    font = pick_font(args.font, args.font_size)
    data = bytearray(Path(args.system_bin).read_bytes())
    for tok, ch in assignments.items():
        data[tok * GLYPH_BYTES : (tok + 1) * GLYPH_BYTES] = render_tile(ch, font)

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
