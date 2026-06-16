#!/usr/bin/env python3
"""Translate the prologue poem graphic (IMG.DAT asset 12, image 0).

The poem is an 8bpp indexed bitmap (768x252) drawn on the title attract loop.
This redraws it from `data/translation/poem_prologue.txt` (three columns) into
the indexed bitmap and writes a patched IMG.DAT. The image keeps its size, so
the result can be injected into the BIN like any other IMG.DAT edit.

Glyphs use the original poem's colours: the body is the animated highlight
index (red in the canonical frame), the antialias edge a darker index, so the
title's per-line highlight palette cycling still applies.
"""
import argparse
import importlib.util
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

SCRIPTS = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("lang5_imgdat", SCRIPTS / "lang5_imgdat.py")
imd = importlib.util.module_from_spec(_spec)
sys.modules["lang5_imgdat"] = imd
_spec.loader.exec_module(imd)

ASSET_INDEX = 12
IMAGE_INDEX = 0
BG_INDEX = 0
# The original poem glyphs are a few shades of red over a black outline. Map the
# antialiased coverage to the poem palette's red ramp (bright core -> dark edge)
# and draw a black outline so the glyphs read over the starfield/monument behind
# them. These indices animate red<->cream with the title's palette cycling.
RED_RAMP = ((185, 89), (120, 176), (55, 209))  # alpha threshold -> index
OUTLINE_INDEX = 212      # black outline / shadow
FONT = "data/fonts/DejaVuSerif-Bold.ttf"
FONT_SIZE = 12
LINE_HEIGHT = 19
TOP_MARGIN = 18
SUPERSAMPLE = 4


def load_columns(path: Path) -> list[list[str]]:
    columns: list[list[str]] = [[]]
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            continue
        if line.strip() == "---":
            columns.append([])
        else:
            columns[-1].append(line)
    return [c for c in columns if any(s.strip() for s in c)]


def ramp_index(value: int) -> int | None:
    for threshold, index in RED_RAMP:
        if value >= threshold:
            return index
    return None


def stamp_line(rows: list[bytearray], width: int, height: int, text: str,
               center_x: int, top_y: int, font_path: str) -> None:
    if not text.strip():
        return
    big = Image.new("L", (width * SUPERSAMPLE, LINE_HEIGHT * SUPERSAMPLE), 0)
    draw = ImageDraw.Draw(big)
    font = ImageFont.truetype(font_path, FONT_SIZE * SUPERSAMPLE)
    text_w = draw.textlength(text, font=font)
    draw.text(((width * SUPERSAMPLE - text_w) / 2, SUPERSAMPLE), text, fill=255, font=font)
    small = big.resize((width, LINE_HEIGHT), Image.LANCZOS)
    glyph = small.load()
    outline = small.filter(ImageFilter.MaxFilter(3)).load()  # dilated for the outline
    edge_alpha = RED_RAMP[-1][0]
    for yy in range(LINE_HEIGHT):
        gy = top_y + yy
        if not 0 <= gy < height:
            continue
        for xx in range(width):
            gx = center_x - width // 2 + xx
            if not 0 <= gx < len(rows[gy]):
                continue
            index = ramp_index(glyph[xx, yy])
            if index is not None:
                rows[gy][gx] = index
            elif outline[xx, yy] >= edge_alpha:
                rows[gy][gx] = OUTLINE_INDEX


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--imgdat", default="work/extracted/IMG.DAT")
    ap.add_argument("--poem", default="data/translation/poem_prologue.txt")
    ap.add_argument("--out-imgdat", default="work/build/IMG.DAT.poem")
    ap.add_argument("--out-preview", default="work/build/poem_en_preview.png")
    ap.add_argument("--font", default=FONT)
    args = ap.parse_args()

    data = imd.read_img(args.imgdat)
    ent, asset = imd.get_asset(data, ASSET_INDEX)
    start, packets, width, block_rows = imd.image_groups(asset)[IMAGE_INDEX]
    height = len(imd.decode_image(asset, start, packets, width, block_rows))

    rows = [bytearray([BG_INDEX] * width) for _ in range(height)]
    columns = load_columns(Path(args.poem))
    if not columns:
        raise SystemExit("poem file has no columns")
    step = width // len(columns)
    for ci, lines in enumerate(columns):
        center_x = step * ci + step // 2
        for li, line in enumerate(lines):
            stamp_line(rows, width, height, line, center_x,
                       TOP_MARGIN + li * LINE_HEIGHT, args.font)

    patched_asset = imd.encode_image(asset, start, packets, width, block_rows, rows)
    imd.replace_asset(data, ASSET_INDEX, patched_asset)
    out = Path(args.out_imgdat)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)

    palettes = imd.clut_palettes(patched_asset)
    palette = imd.pick_palette(b"".join(bytes(r) for r in rows), palettes) or palettes[0]
    preview = Image.new("RGB", (width, height), (0, 0, 0))
    px = preview.load()
    for y, row in enumerate(rows):
        for x, value in enumerate(row):
            px[x, y] = palette[value]
    Path(args.out_preview).parent.mkdir(parents=True, exist_ok=True)
    preview.save(args.out_preview)
    print(f"patched IMG.DAT -> {out}")
    print(f"poem preview -> {args.out_preview}")


if __name__ == "__main__":
    main()
