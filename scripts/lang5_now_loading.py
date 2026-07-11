#!/usr/bin/env python3
"""Translate the Now Loading plate (IMG.DAT asset 0, type-2 texture).

The plate is a 120x28 8bpp texture stored as two raw type-2 VRAM-upload
packets inside asset 0 (destination VRAM byte column 1664, row 456; found by
byte-matching a live VRAM dump against the disc files). The lettering is an
engraved stroke on a mottled metal face with an underline and corner rivets.
This erases only the inner face between the rivets, refills it with plate
texture sampled from clean rows, and redraws the target text with the
original stroke/bevel indices plus the underline.
"""
import argparse
import importlib.util
import struct
import sys
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from lang5_project import add_language_args, language_from_args

SCRIPTS = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("lang5_imgdat", SCRIPTS / "lang5_imgdat.py")
imd = importlib.util.module_from_spec(_spec)
sys.modules["lang5_imgdat"] = imd
_spec.loader.exec_module(imd)

ASSET_INDEX = 0
WIDTH, HEIGHT = 120, 28
# Type-2 packet header signature: VRAM destination and size of the plate.
VRAM_X_WORDS, VRAM_Y, WIDTH_WORDS, ROWS = 0x340, 0x1C8, 0x3C, 0x1C
# Inner plate face between the corner rivets (x 12-14/112-113 top,
# 6-7/110-111 bottom) and the frame highlights (x 6..12 and 110..114). Only
# the original lettering rows are repainted; the underline (rows 18-19, full
# face width) and the tick shading above the letters stay original.
FACE_X0, FACE_X1 = 13, 110
TEXT_Y0, TEXT_Y1 = 10, 18
UNDERLINE_Y = 18
FACE_Y0 = 7                     # top of the paintable face (new glyph tops)
BASELINE = 17                   # original caps sit on row 17
CAP_TOP = 7                     # taller than the original 11..17: the Cyrillic
                                # line needs the full face to match the English span
# The original lettering spans x 14..106; the new text is letter-spaced out
# to the same width.
TARGET_X0, TARGET_X1 = 14, 107
# Colour-class luminance bounds on the plate: engraved stroke, plate face
# mottle, bevel highlight. Pixels darker than the face floor are letter
# strokes or their antialias; brighter than the ceiling are bevel shine.
DARK_LUM, BRIGHT_LUM = 25, 90
FACE_LUM_FLOOR = 42
FONT = "data/fonts/DejaVuSerif-Bold.ttf"
SUPERSAMPLE = 4
STROKE_ALPHA, MID_ALPHA, EDGE_ALPHA = 190, 120, 70
CLUT_INDEX = 1                  # first grayscale CLUT of asset 0 (for classes/preview)


def luminance(color: tuple[int, int, int]) -> float:
    return (color[0] * 3 + color[1] * 6 + color[2]) / 10


def find_plate_packets(data: bytes, ent) -> list[list[int]]:
    """Adjacent packet pairs of the plate; asset 0 stores three copies."""
    offsets = []
    for off in range(ent.offset, ent.end, imd.PACKET_BYTES):
        t = struct.unpack_from("<16H", data, off)
        if (t[0] == imd.PACKET_MAGIC and t[3] == 2
                and t[8] == VRAM_X_WORDS and t[9] == VRAM_Y
                and t[10] == WIDTH_WORDS and t[11] == ROWS):
            offsets.append(off)
    pairs = [offsets[i : i + 2] for i in range(0, len(offsets), 2)]
    if not pairs or any(len(p) != 2 or p[1] != p[0] + imd.PACKET_BYTES for p in pairs):
        raise SystemExit(f"expected adjacent plate packet pairs, found {offsets}")
    return pairs


def read_plate(data: bytes, packs: list[int]) -> bytearray:
    body = bytearray()
    for off in packs:
        body += data[off + imd.PACKET_HEADER_BYTES : off + imd.PACKET_BYTES]
    return body[: WIDTH * HEIGHT]


def write_plate(data: bytearray, packs: list[int], pixels: bytes) -> None:
    pos = 0
    for off in packs:
        n = min(imd.PACKET_BYTES - imd.PACKET_HEADER_BYTES, len(pixels) - pos)
        data[off + imd.PACKET_HEADER_BYTES : off + imd.PACKET_HEADER_BYTES + n] = \
            pixels[pos : pos + n]
        pos += n


def render_mask(text: str, font_path: str, cap_top: int) -> Image.Image:
    """Antialiased 1x text alpha spanning the original lettering width.

    The glyphs are rendered supersampled at the plate's cap band height and
    letter-spaced out so the line covers the same span as the original
    English lettering; the width is never squeezed, which would tear the
    thin strokes.
    """
    ss = SUPERSAMPLE
    target_w = (TARGET_X1 - TARGET_X0) * ss
    probe = Image.new("L", (8, 8))
    d = ImageDraw.Draw(probe)
    for cap in range(BASELINE - cap_top + 1, 4, -1):
        font = None
        for cand in range(cap * ss // 2, cap * ss * 3):
            f = ImageFont.truetype(font_path, cand)
            bbox = d.textbbox((0, 0), "Н", font=f)
            if bbox[3] - bbox[1] >= cap * ss:
                font = f
                break
        if font is None:
            continue
        advances = [d.textlength(ch, font=font) for ch in text]
        natural = sum(advances)
        if natural > target_w:
            continue
        tracking = (target_w - natural) / max(1, len(text) - 1)
        big = Image.new("L", (target_w + 2 * ss, HEIGHT * ss), 0)
        bd = ImageDraw.Draw(big)
        bbox = bd.textbbox((0, 0), "Н", font=font)
        pen = 0.0
        for ch, advance in zip(text, advances):
            bd.text((ss + pen, BASELINE * ss - bbox[3]), ch, fill=255, font=font)
            pen += advance + tracking
        return big.resize((big.width // ss, HEIGHT), Image.LANCZOS)
    raise SystemExit(f"cannot fit {text!r} on the plate with {font_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_language_args(ap)
    ap.add_argument("--imgdat", default="work/extracted/IMG.DAT")
    ap.add_argument("--text", default=None)
    ap.add_argument("--out-imgdat", default="work/build/IMG.DAT.now_loading")
    ap.add_argument("--out-preview", default=None)
    ap.add_argument("--font", default=FONT)
    ap.add_argument("--cap-top", type=int, default=CAP_TOP)
    args = ap.parse_args()
    lang = language_from_args(args)
    text = args.text if args.text is not None else lang.now_loading
    if not text:
        raise SystemExit("no plate text: pass --text or set now_loading in the manifest")
    preview_path = (Path(args.out_preview) if args.out_preview
                    else lang.build_path("now_loading_{lang}_preview.png"))

    data = imd.read_img(args.imgdat)
    ent, asset = imd.get_asset(data, ASSET_INDEX)
    palette = imd.clut_palettes(asset)[CLUT_INDEX]
    pairs = find_plate_packets(data, ent)
    copies = [read_plate(data, pair) for pair in pairs]
    if any(c != copies[0] for c in copies[1:]):
        raise SystemExit("plate copies differ; refusing to patch them uniformly")
    pixels = copies[0]

    def lum_at(x: int, y: int) -> float:
        return luminance(palette[pixels[y * WIDTH + x]])

    # Palette indices already used on the plate, by luminance: the engraved
    # stroke core, two antialias midtones and the bevel highlight.
    used = Counter(pixels[y * WIDTH + x]
                   for y in range(FACE_Y0, UNDERLINE_Y + 2)
                   for x in range(FACE_X0, FACE_X1))

    def nearest_used(target: float) -> int:
        return min(used, key=lambda i: (abs(luminance(palette[i]) - target),
                                        -used[i]))

    stroke_index = nearest_used(5)
    mid_index = nearest_used(15)
    edge_index = nearest_used(32)

    # Paint over the original lettering with the plate's own open texture:
    # every letter-free run of the same row (the clear face left and right
    # of the strokes and the gaps between them) becomes clone material, and
    # each hole is covered by stitching whole runs picked by a position
    # hash. Real contiguous pixels keep the face's mottle and its vertical
    # shading; the underline rows below stay original.
    def clean_flags(y: int) -> list[bool]:
        return [FACE_LUM_FLOOR <= lum_at(x, y) <= BRIGHT_LUM
                for x in range(FACE_X0, FACE_X1)]

    def clean_runs(y: int, min_len: int) -> list[tuple[int, int]]:
        flags = clean_flags(y)
        runs = []
        x = 0
        while x < len(flags):
            if flags[x]:
                start = x
                while x < len(flags) and flags[x]:
                    x += 1
                if x - start >= min_len:
                    runs.append((start, x - start))
            else:
                x += 1
        return runs

    out = bytearray(pixels)
    for y in range(TEXT_Y0, TEXT_Y1):
        clean = clean_flags(y)
        # Clone material: this row's own clean runs, else a neighbor row's.
        src_y, runs = y, clean_runs(y, 3)
        if not runs:
            for dy in (1, -1, 2, -2):
                cand = y + dy
                if TEXT_Y0 - 3 <= cand < TEXT_Y1 and clean_runs(cand, 3):
                    src_y, runs = cand, clean_runs(cand, 3)
                    break
        if not runs:
            raise SystemExit(f"row {y} has no clean face runs; wrong layout?")
        x = 0
        while x < len(clean):
            if clean[x]:
                x += 1
                continue
            hole = x
            while x < len(clean) and not clean[x]:
                x += 1
            pos = hole
            while pos < x:
                start, length = runs[(pos * 2654435761 + y * 40503) % len(runs)]
                take = min(length, x - pos)
                src = (src_y * WIDTH + FACE_X0 + start)
                dst = (y * WIDTH + FACE_X0 + pos)
                out[dst : dst + take] = pixels[src : src + take]
                pos += take

    mask = render_mask(text, args.font, args.cap_top)
    mx0 = (TARGET_X0 + TARGET_X1 - mask.width) // 2
    alpha = mask.load()

    def paint(x: int, y: int, index: int) -> None:
        if FACE_X0 <= x < FACE_X1 and FACE_Y0 <= y <= UNDERLINE_Y + 1:
            out[y * WIDTH + x] = index

    # The antialiased stroke in three dark levels; the original's bevel
    # shine is too subtle at this size to reproduce without speckling the
    # letter counters, so the glyphs stay plain engraving.
    for yy in range(mask.height):
        for xx in range(mask.width):
            value = alpha[xx, yy]
            if value >= STROKE_ALPHA:
                paint(mx0 + xx, yy, stroke_index)
            elif value >= MID_ALPHA:
                paint(mx0 + xx, yy, mid_index)
            elif value >= EDGE_ALPHA:
                paint(mx0 + xx, yy, edge_index)
    for pair in pairs:
        write_plate(data, pair, bytes(out))
    out_path = Path(args.out_imgdat)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)

    preview = Image.new("RGB", (WIDTH * 4, HEIGHT * 8), (0, 0, 0))
    for pi, pix in enumerate((pixels, out)):
        frame = Image.new("RGB", (WIDTH, HEIGHT))
        frame.putdata([palette[v] for v in pix])
        preview.paste(frame.resize((WIDTH * 4, HEIGHT * 4), Image.NEAREST), (0, pi * HEIGHT * 4))
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview.save(preview_path)
    print(f"patched IMG.DAT -> {out_path}")
    print(f"plate preview -> {preview_path}")


if __name__ == "__main__":
    main()
