#!/usr/bin/env python3
"""Translate the prologue poem graphic (IMG.DAT asset 12, image 0).

The poem is an 8bpp indexed bitmap (768x252) drawn on the title attract loop.
The engine treats the three 256px-wide panels as one tall scroll (panel 0 on
top, then 1, then 2) and pans it upward. This redraws the poem from
the selected language pack's poem text onto that continuous strip (height*3, no
gap between panels), then slices it back into the three panels at the exact
panel boundaries, so a line straddling a boundary rejoins seamlessly. The image
keeps its size, so the result can be injected into the BIN like any other
IMG.DAT edit.

Glyphs use the original poem's colours: the body is the animated highlight
index (red in the canonical frame), the antialias edge a darker index, so the
title's per-line highlight palette cycling still applies.
"""
import argparse
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from lang5_project import add_language_args, language_from_args

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
LINE_HEIGHT = 18         # stamp canvas height per rendered line
TOP_MARGIN = 24          # first line top, matching the original poem (~25)
BOTTOM_EMPTY = 44        # blank tail on the last screen, so it can be read
MAX_PITCH = 20           # original line pitch; compress only if the text is taller
MIN_PITCH = 14
SUPERSAMPLE = 4


@dataclass(frozen=True)
class LineStamp:
    rows: list[bytearray]
    bbox_top: int
    bbox_bottom: int


def load_lines(path: Path) -> list[str]:
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            continue
        if line.strip() == "---":
            continue
        lines.append(line)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def find_overflow_group(asset: bytes, main_start: int, main_packets: int,
                        width_word: int) -> tuple[int, int, int]:
    """Locate the poem's `type=2` overflow block right after the main image.

    The poem image continues past the main group (VRAM rows 256-507) into a
    short `type=2` block (VRAM rows 508-511, same width): the bottom scanlines of
    every column live there, so the columns are taller than the main image. The
    engine treats the whole thing as one image, so these rows must be rewritten,
    not blanked. Returns (start_offset, packet_count, block_rows); count 0 if
    there is no overflow block.
    """
    off = main_start + main_packets * imd.PACKET_BYTES
    start, packets, block_rows = off, 0, 0
    while (off + imd.PACKET_HEADER_BYTES <= len(asset)
           and imd._u16(asset, off) == imd.PACKET_MAGIC
           and imd._u16(asset, off + 0x06) == 2
           and imd._u16(asset, off + 0x14) == width_word):
        if packets == 0:
            block_rows = imd._u16(asset, off + 0x16)
        packets += 1
        off += imd.PACKET_BYTES
    return start, packets, block_rows


def ramp_index(value: int) -> int | None:
    for threshold, index in RED_RAMP:
        if value >= threshold:
            return index
    return None


def make_line_stamp(text: str, width: int, font_path: str) -> LineStamp:
    stamp = [bytearray([BG_INDEX] * width) for _ in range(LINE_HEIGHT)]
    if not text.strip():
        return LineStamp(stamp, 0, 0)
    big = Image.new("L", (width * SUPERSAMPLE, LINE_HEIGHT * SUPERSAMPLE), 0)
    draw = ImageDraw.Draw(big)
    font = ImageFont.truetype(font_path, FONT_SIZE * SUPERSAMPLE)
    text_w = draw.textlength(text, font=font)
    draw.text(((width * SUPERSAMPLE - text_w) / 2, SUPERSAMPLE), text, fill=255, font=font)
    small = big.resize((width, LINE_HEIGHT), Image.LANCZOS)
    glyph = small.load()
    outline = small.filter(ImageFilter.MaxFilter(3)).load()  # dilated for the outline
    edge_alpha = RED_RAMP[-1][0]
    bbox_top = LINE_HEIGHT
    bbox_bottom = 0
    for yy in range(LINE_HEIGHT):
        for xx in range(width):
            index = ramp_index(glyph[xx, yy])
            if index is not None:
                stamp[yy][xx] = index
                bbox_top = min(bbox_top, yy)
                bbox_bottom = max(bbox_bottom, yy + 1)
            elif outline[xx, yy] >= edge_alpha:
                stamp[yy][xx] = OUTLINE_INDEX
                bbox_top = min(bbox_top, yy)
                bbox_bottom = max(bbox_bottom, yy + 1)
    if bbox_bottom == 0:
        return LineStamp(stamp, 0, 0)
    return LineStamp(stamp, bbox_top, bbox_bottom)


def paint_stamp(rows: list[bytearray], stamp: LineStamp, top_y: int) -> None:
    height = len(rows)
    for yy, stamp_row in enumerate(stamp.rows):
        gy = top_y + yy
        if not 0 <= gy < height:
            continue
        dst = rows[gy]
        for xx, index in enumerate(stamp_row):
            if index != BG_INDEX:
                dst[xx] = index


def split_blocks(lines: list[str], stamps: list[LineStamp | None]) -> list[list[LineStamp]]:
    blocks: list[list[LineStamp]] = []
    block: list[LineStamp] = []
    for line, stamp in zip(lines, stamps):
        if not line.strip():
            if block:
                blocks.append(block)
                block = []
            continue
        if stamp is None:
            raise ValueError("missing line stamp")
        block.append(stamp)
    if block:
        blocks.append(block)
    return blocks


def layout_strip(lines: list[str], stamps: list[LineStamp | None],
                 width: int, strip_height: int) -> tuple[int, list[bytearray]]:
    """Place every line on a single uniform pitch in one continuous scroll strip.

    The engine scrolls the strip upward as one image, so there is no gap between
    screens: a line that straddles a panel boundary is simply split and rejoined.
    Blank lines (the block separators) are kept as empty slots, so the whole poem
    sits on one uniform grid. The pitch is the original 20px unless the (longer)
    Translated text must be compressed to keep a readable blank tail at the bottom of
    the last screen.
    """
    last_slot = max(1, len(lines) - 1)
    usable = strip_height - TOP_MARGIN - LINE_HEIGHT - BOTTOM_EMPTY
    pitch = max(MIN_PITCH, min(MAX_PITCH, usable // last_slot))
    rows = [bytearray([BG_INDEX] * width) for _ in range(strip_height)]
    for slot, (line, stamp) in enumerate(zip(lines, stamps)):
        if stamp is None or not line.strip():
            continue
        paint_stamp(rows, stamp, TOP_MARGIN + slot * pitch)
    return pitch, rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_language_args(ap)
    ap.add_argument("--imgdat", default="work/extracted/IMG.DAT")
    ap.add_argument("--poem", default=None)
    ap.add_argument("--out-imgdat", default="work/build/IMG.DAT.poem")
    ap.add_argument("--out-preview", default=None)
    ap.add_argument("--font", default=FONT)
    args = ap.parse_args()
    lang = language_from_args(args)
    poem_path = Path(args.poem) if args.poem else lang.poem
    preview_path = (Path(args.out_preview) if args.out_preview
                    else lang.build_path("poem_{lang}_preview.png"))

    data = imd.read_img(args.imgdat)
    ent, asset = imd.get_asset(data, ASSET_INDEX)
    main_start, main_packets, width, main_br = imd.image_groups(asset)[IMAGE_INDEX]
    main_h = len(imd.decode_image(asset, main_start, main_packets, width, main_br))

    # The poem image continues past the main group into a `type=2` overflow block
    # (VRAM rows 508-511): the bottom scanlines of every column live there, so a
    # column is `col_h` (= main_h + overflow rows) tall, not just main_h.
    width_word = imd._u16(asset, main_start + 0x14)
    ov_start, ov_packets, ov_br = find_overflow_group(asset, main_start, main_packets, width_word)
    ov_h = len(imd.decode_image(asset, ov_start, ov_packets, width, ov_br)) if ov_packets else 0
    col_h = main_h + ov_h

    lines = load_lines(poem_path)
    if not any(s.strip() for s in lines):
        raise SystemExit("poem file has no text lines")

    panels = 3
    panel_w = width // panels
    # The engine stacks the three columns (col 0, then 1, then 2) into one
    # continuous vertical scroll of full-height columns, no gap between them.
    strip_h = col_h * panels
    stamps = [
        make_line_stamp(line, panel_w, args.font) if line.strip() else None
        for line in lines
    ]
    blocks = split_blocks(lines, stamps)
    if len(blocks) != 4:
        raise SystemExit(f"expected four poem blocks, got {len(blocks)}")

    pitch, strip_rows = layout_strip(lines, stamps, panel_w, strip_h)

    # Fold the scroll strip back into the stored width x col_h image, slicing each
    # column at its exact boundary so the engine re-stacks them into a seamless
    # scroll: a line straddling a column boundary is split between a column's
    # overflow rows and the top of the next column, and rejoins with no gap.
    full = [bytearray([BG_INDEX] * width) for _ in range(col_h)]
    for panel in range(panels):
        src_y = panel * col_h
        dst_x = panel * panel_w
        for y in range(col_h):
            full[y][dst_x:dst_x + panel_w] = strip_rows[src_y + y]

    # The main image holds rows 0..main_h-1 of every column; the overflow block
    # holds the remaining bottom rows. Write both so boundary-crossing lines keep
    # their bottom slivers.
    patched_asset = imd.encode_image(asset, main_start, main_packets, width, main_br, full[:main_h])
    if ov_packets:
        patched_asset = imd.encode_image(
            patched_asset, ov_start, ov_packets, width, ov_br, full[main_h:col_h])
    imd.replace_asset(data, ASSET_INDEX, patched_asset)
    out = Path(args.out_imgdat)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)

    palettes = imd.clut_palettes(patched_asset)
    palette = imd.pick_palette(b"".join(bytes(r) for r in full), palettes) or palettes[0]
    preview = Image.new("RGB", (width, col_h), (0, 0, 0))
    px = preview.load()
    for y, row in enumerate(full):
        for x, value in enumerate(row):
            px[x, y] = palette[value]
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview.save(preview_path)
    print(f"patched IMG.DAT -> {out}")
    print(f"poem preview -> {preview_path}")
    print(
        "poem layout: "
        f"pitch={pitch} lines={len(lines)} blocks={[len(b) for b in blocks]} "
        f"col_h={col_h} (main {main_h} + overflow {ov_h}) strip_h={strip_h} panel_w={panel_w}"
    )


if __name__ == "__main__":
    main()
