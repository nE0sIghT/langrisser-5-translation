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
# the original lettering rows 11..17 and the underline row 18 are erased;
# the rows above keep their native tick shading untouched.
FACE_X0, FACE_X1 = 13, 110
TEXT_Y0, TEXT_Y1 = 11, 18
UNDERLINE_Y = 18
UL_X0, UL_X1 = 9, 110
FACE_Y0 = 7                     # top of the paintable face (new glyph tops)
BASELINE = 17                   # original caps sit on row 17
CAP_TOP = 9                     # drawn slightly taller than the original 11..17
# Colour-class luminance bounds on the plate: engraved stroke, plate midtone,
# bevel highlight.
DARK_LUM, BRIGHT_LUM = 25, 90
FONT = "data/fonts/LiberationSansNarrow-Bold.ttf"
SUPERSAMPLE = 4
STROKE_ALPHA, EDGE_ALPHA = 200, 95
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


def render_mask(text: str, font_path: str) -> Image.Image:
    """Antialiased 1x text alpha, caps on the plate's cap band.

    The glyphs are rendered supersampled and downsampled once, at the
    largest cap height (up to the band height) whose natural advance fits
    the face; the width is never squeezed afterwards, which would tear
    the thin strokes.
    """
    ss = SUPERSAMPLE
    max_w = (FACE_X1 - FACE_X0 - 4) * ss
    probe = Image.new("L", (8, 8))
    d = ImageDraw.Draw(probe)
    for cap in range(BASELINE - CAP_TOP + 1, 4, -1):
        font = None
        for cand in range(cap * ss // 2, cap * ss * 3):
            f = ImageFont.truetype(font_path, cand)
            bbox = d.textbbox((0, 0), "Н", font=f)
            if bbox[3] - bbox[1] >= cap * ss:
                font = f
                break
        if font is None:
            continue
        if d.textlength(text, font=font) > max_w:
            continue
        big = Image.new("L", (WIDTH * ss * 2, HEIGHT * ss), 0)
        bd = ImageDraw.Draw(big)
        bbox = bd.textbbox((0, 0), "Н", font=font)
        bd.text((WIDTH * ss // 2, BASELINE * ss - bbox[3]), text, fill=255, font=font)
        ink = big.getbbox()
        if ink is None:
            break
        x0 = ink[0] - ink[0] % ss
        x1 = ink[2] + (-ink[2]) % ss
        big = big.crop((x0, 0, x1, HEIGHT * ss))
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
                   for x in range(UL_X0, UL_X1))

    def nearest_used(target: float) -> int:
        return min(used, key=lambda i: (abs(luminance(palette[i]) - target),
                                        -used[i]))

    stroke_index = nearest_used(5)
    mid_index = nearest_used(28)
    edge_index = nearest_used(46)
    bevel_index = nearest_used(92)

    # Refill the lettering rows with synthesized plate texture: the per-row
    # median luminance of the letter-free pixels keeps the vertical shading,
    # and a smooth value-noise mottle replaces the scratched face. Random
    # per-pixel sampling reads as salt-and-pepper noise; the original mottle
    # is spatially coherent, so the noise must be too. The underline row has
    # no clean pixels of its own and borrows the row above.
    def hash01(i: int, j: int) -> float:
        return ((i * 73856093 ^ j * 19349663) % 65536) / 65536 - 0.5

    def smoothstep(t: float) -> float:
        return t * t * (3 - 2 * t)

    def mottle(x: int, y: int) -> float:
        gx, gy = x / 3.0, y / 2.0
        x0, y0 = int(gx), int(gy)
        fx, fy = smoothstep(gx - x0), smoothstep(gy - y0)
        top = hash01(x0, y0) * (1 - fx) + hash01(x0 + 1, y0) * fx
        bottom = hash01(x0, y0 + 1) * (1 - fx) + hash01(x0 + 1, y0 + 1) * fx
        return top * (1 - fy) + bottom * fy

    out = bytearray(pixels)
    for y in range(TEXT_Y0, UNDERLINE_Y + 1):
        row_src = y if y < UNDERLINE_Y else TEXT_Y1 - 2
        lums = sorted(lum_at(x, row_src) for x in range(FACE_X0, FACE_X1)
                      if DARK_LUM <= lum_at(x, row_src) <= BRIGHT_LUM)
        if len(lums) < 4:
            raise SystemExit(f"row {row_src} has no clean face pixels; wrong layout?")
        median = lums[len(lums) // 2]
        for x in range(FACE_X0 if y < UNDERLINE_Y else UL_X0,
                       FACE_X1 if y < UNDERLINE_Y else UL_X1):
            out[y * WIDTH + x] = nearest_used(median + mottle(x, y) * 16)

    mask = render_mask(text, args.font)
    mx0 = (FACE_X0 + FACE_X1 - mask.width) // 2
    alpha = mask.load()

    def paint(x: int, y: int, index: int) -> None:
        if UL_X0 <= x < UL_X1 and FACE_Y0 <= y <= UNDERLINE_Y:
            out[y * WIDTH + x] = index

    # Engraving: bevel highlight one pixel down-right of the stroke core,
    # only over free plate, then the antialiased stroke in three levels.
    def alpha_at(xx: int, yy: int) -> int:
        if 0 <= xx < mask.width and 0 <= yy < mask.height:
            return alpha[xx, yy]
        return 0

    for yy in range(mask.height):
        for xx in range(mask.width):
            if alpha[xx, yy] >= STROKE_ALPHA and alpha_at(xx + 1, yy + 1) < EDGE_ALPHA:
                paint(mx0 + xx + 1, yy + 1, bevel_index)
    for yy in range(mask.height):
        for xx in range(mask.width):
            value = alpha[xx, yy]
            if value >= STROKE_ALPHA:
                paint(mx0 + xx, yy, stroke_index)
            elif value >= 145:
                paint(mx0 + xx, yy, mid_index)
            elif value >= EDGE_ALPHA:
                paint(mx0 + xx, yy, edge_index)
    # Underline across the full face like the original; its shadow row 19
    # below is original art and already spans the same width. The original
    # underline end-curl also dented the bevel row 20; repair it with the
    # bevel pattern from a few pixels left.
    for x in range(UL_X0, UL_X1 - 3):
        paint(x, UNDERLINE_Y, stroke_index)
    for x in range(102, 109):
        out[20 * WIDTH + x] = out[20 * WIDTH + x - 8]

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
