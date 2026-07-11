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
# 6-7/110-111 bottom) and the frame highlights (x 6..12 and 110..114); the
# top rivet rows keep a margin around the rivet box, and the underline row
# 18 runs wider, from x 8 to 107.
FACE_X0, FACE_X1 = 13, 110
RIVET_ROWS_X0 = 15              # rows 7..10: stay right of the top-left rivet
FACE_Y0, FACE_Y1 = 7, 18
UNDERLINE_Y = 18
UL_X0, UL_X1 = 9, 110
CLEAN_ROWS = (8, 9, 10)         # letter-free face rows used as fill texture
BASELINE = 17                   # original caps sit on row 17
CAP_TOP = 9                     # drawn slightly taller than the original 11..17
# Colour-class luminance bounds on the plate: engraved stroke, plate midtone,
# bevel highlight.
DARK_LUM, BRIGHT_LUM = 25, 90
FONT = "data/fonts/LiberationSansNarrow-Bold.ttf"
SUPERSAMPLE = 4
STROKE_ALPHA, EDGE_ALPHA = 150, 70
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
    ss = SUPERSAMPLE
    cap_target = (BASELINE - CAP_TOP + 1) * ss
    probe = Image.new("L", (8, 8))
    d = ImageDraw.Draw(probe)
    font = None
    for cand in range(cap_target // 2, cap_target * 3):
        f = ImageFont.truetype(font_path, cand)
        bbox = d.textbbox((0, 0), "Н", font=f)
        if bbox[3] - bbox[1] >= cap_target:
            font = f
            break
    if font is None:
        raise SystemExit(f"cannot reach cap height {cap_target} with {font_path}")
    big = Image.new("L", (WIDTH * ss * 2, HEIGHT * ss), 0)
    d = ImageDraw.Draw(big)
    bbox = d.textbbox((0, 0), "Н", font=font)
    d.text((WIDTH * ss // 2, BASELINE * ss - bbox[3]), text, fill=255, font=font)
    ink = big.getbbox()
    if ink is None:
        raise SystemExit("plate text rendered empty")
    big = big.crop((ink[0], 0, ink[2], HEIGHT * ss))
    max_w = (FACE_X1 - FACE_X0 - 6) * ss
    new_w = min(big.width, max_w)
    return big.resize((new_w // ss, HEIGHT), Image.LANCZOS)


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

    # Original stroke / bevel indices from the lettering zone.
    dark = Counter()
    bright = Counter()
    for y in range(FACE_Y0, FACE_Y1):
        for x in range(FACE_X0, FACE_X1):
            index = pixels[y * WIDTH + x]
            lum = luminance(palette[index])
            if lum < DARK_LUM:
                dark[index] += 1
            elif lum > BRIGHT_LUM:
                bright[index] += 1
    if not dark or not bright:
        raise SystemExit("no stroke/bevel samples found; wrong plate layout?")
    stroke_index = dark.most_common(1)[0][0]
    bevel_index = bright.most_common(1)[0][0]

    # Refill the inner face by tiling a repaired band of the clean face rows:
    # tiling whole rows keeps the horizontal mottle coherent, and repairing
    # the band first (left-neighbor fill over stray marks) keeps stroke and
    # highlight pixels out of the texture.
    band = [bytearray(pixels[row * WIDTH : (row + 1) * WIDTH]) for row in CLEAN_ROWS]
    for row in band:
        for x in range(UL_X0, UL_X1):
            if not DARK_LUM <= luminance(palette[row[x]]) <= BRIGHT_LUM:
                row[x] = row[x - 1]
    out = bytearray(pixels)
    for y in range(FACE_Y0, FACE_Y1):
        src = band[(y - FACE_Y0) % len(band)]
        for x in range(RIVET_ROWS_X0 if y <= 10 else FACE_X0, FACE_X1):
            out[y * WIDTH + x] = src[x]
    src = band[(UNDERLINE_Y - FACE_Y0) % len(band)]
    for x in range(UL_X0, UL_X1):
        out[UNDERLINE_Y * WIDTH + x] = src[x]

    mask = render_mask(text, args.font)
    mx0 = (FACE_X0 + FACE_X1 - mask.width) // 2
    alpha = mask.load()

    def paint(x: int, y: int, index: int) -> None:
        if UL_X0 <= x < UL_X1 and FACE_Y0 <= y <= UNDERLINE_Y:
            out[y * WIDTH + x] = index

    # Engraving: bevel highlight offset one pixel down-right, then the stroke.
    for yy in range(mask.height):
        for xx in range(mask.width):
            if alpha[xx, yy] >= STROKE_ALPHA:
                paint(mx0 + xx + 1, yy + 1, bevel_index)
    for yy in range(mask.height):
        for xx in range(mask.width):
            if alpha[xx, yy] >= STROKE_ALPHA:
                paint(mx0 + xx, yy, stroke_index)
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
