#!/usr/bin/env python3
"""Translate the SCENARIO CLEAR banner (IMG.DAT asset 9).

The banner is stored as three identical 224x72 8bpp images (the three CLUTs
animate the orb shine; the lettering indices are constant across them). The
lettering sits on a plain black field between the mechanical rods, flanked by
small bracket ornaments that stay untouched. This erases only the lettering
rectangle and redraws the target text there, transferring colours from the
original letters pixel-by-pixel (nearest sample in the same row), so the
vertical gradient and the horizontal green-to-gold drift both survive.
"""
import argparse
import bisect
import importlib.util
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from lang5_project import add_language_args, language_from_args

SCRIPTS = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("lang5_imgdat", SCRIPTS / "lang5_imgdat.py")
imd = importlib.util.module_from_spec(_spec)
sys.modules["lang5_imgdat"] = imd
_spec.loader.exec_module(imd)

ASSET_INDEX = 9
BG_INDEX = 255            # the field behind the lettering is plain black
# Lettering rectangle (the bracket ornaments at x~18 and x~206 stay outside).
TEXT_X0, TEXT_X1 = 22, 205
TEXT_Y0, TEXT_Y1 = 30, 50
# Original caps: ink rows 31..48, so cap height 16 on a row-48 baseline.
CAP_TOP, BASELINE = 32, 48
# Diacritics may rise into the black gap above the letters and a descender may
# dip one row below, but never into the rods.
PAINT_Y0, PAINT_Y1 = 28, 51
# Colour-class luminance bounds: bright letter fill vs antialias midtones.
BRIGHT_LUM, MID_LUM = 110, 45
FONT = "data/fonts/DejaVuSerif-Bold.ttf"
SUPERSAMPLE = 4
BRIGHT_ALPHA, MID_ALPHA = 160, 70


def luminance(color: tuple[int, int, int]) -> float:
    return (color[0] * 3 + color[1] * 6 + color[2]) / 10


def collect_row_samples(rows: list[bytearray], palette: list[tuple[int, int, int]]
                        ) -> tuple[dict[int, list[tuple[int, int]]], dict[int, list[tuple[int, int]]]]:
    """Per-row (x, index) samples of the original letter fill and midtones."""
    bright: dict[int, list[tuple[int, int]]] = {}
    mid: dict[int, list[tuple[int, int]]] = {}
    for y in range(TEXT_Y0, TEXT_Y1):
        for x in range(TEXT_X0, TEXT_X1):
            index = rows[y][x]
            if index == BG_INDEX:
                continue
            lum = luminance(palette[index])
            if lum > BRIGHT_LUM:
                bright.setdefault(y, []).append((x, index))
            elif lum > MID_LUM:
                mid.setdefault(y, []).append((x, index))
    return bright, mid


def nearest_sample(samples: dict[int, list[tuple[int, int]]], y: int, x: int) -> int | None:
    """Index of the sample nearest to (x, y): same row first, else nearest row."""
    for dy in range(0, TEXT_Y1 - PAINT_Y0):
        for yy in (y - dy, y + dy) if dy else (y,):
            row = samples.get(yy)
            if not row:
                continue
            pos = bisect.bisect_left(row, (x,))
            best = None
            for cand in (row[pos - 1] if pos else None,
                         row[pos] if pos < len(row) else None):
                if cand and (best is None or abs(cand[0] - x) < abs(best[0] - x)):
                    best = cand
            return best[1]
    return None


def render_mask(text: str, font_path: str) -> Image.Image:
    """Text alpha mask sized to the banner, caps on the original cap band."""
    ss = SUPERSAMPLE
    cap_target = (BASELINE - CAP_TOP) * ss
    size = cap_target
    font = None
    probe = Image.new("L", (8, 8))
    d = ImageDraw.Draw(probe)
    for cand in range(cap_target // 2, cap_target * 2):
        f = ImageFont.truetype(font_path, cand)
        bbox = d.textbbox((0, 0), "H", font=f)
        if bbox[3] - bbox[1] >= cap_target:
            font, size = f, cand
            break
    if font is None:
        raise SystemExit(f"cannot reach cap height {cap_target} with {font_path}")
    width, height = 224 * ss, (PAINT_Y1 - PAINT_Y0) * ss
    big = Image.new("L", (width * 2, height), 0)
    d = ImageDraw.Draw(big)
    bbox = d.textbbox((0, 0), "H", font=font)
    baseline_y = (BASELINE - PAINT_Y0) * ss
    d.text((width // 2, baseline_y - bbox[3]), text, fill=255, font=font)
    ink = big.getbbox()
    if ink is None:
        raise SystemExit("banner text rendered empty")
    big = big.crop((ink[0], 0, ink[2], height))
    max_w = (TEXT_X1 - TEXT_X0 - 4) * ss
    new_w = min(big.width, max_w)
    return big.resize((new_w // ss, height // ss), Image.LANCZOS)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_language_args(ap)
    ap.add_argument("--imgdat", default="work/extracted/IMG.DAT")
    ap.add_argument("--text", default=None)
    ap.add_argument("--out-imgdat", default="work/build/IMG.DAT.scenario_clear")
    ap.add_argument("--out-preview", default=None)
    ap.add_argument("--font", default=FONT)
    args = ap.parse_args()
    lang = language_from_args(args)
    text = args.text if args.text is not None else lang.scenario_clear
    if not text:
        raise SystemExit("no banner text: pass --text or set scenario_clear in the manifest")
    preview_path = (Path(args.out_preview) if args.out_preview
                    else lang.build_path("scenario_clear_{lang}_preview.png"))

    data = imd.read_img(args.imgdat)
    ent, asset = imd.get_asset(data, ASSET_INDEX)
    groups = imd.image_groups(asset)
    palettes = imd.clut_palettes(asset)
    if not groups or not palettes:
        raise SystemExit("asset 9 has no decodable images or palettes")

    start, packets, width, block_rows = groups[0]
    rows = imd.decode_image(asset, start, packets, width, block_rows)
    bright, mid = collect_row_samples(rows, palettes[0])
    if not bright:
        raise SystemExit("no letter fill samples found; wrong asset layout?")

    for y in range(TEXT_Y0, TEXT_Y1):
        for x in range(TEXT_X0, TEXT_X1):
            rows[y][x] = BG_INDEX

    mask = render_mask(text, args.font)
    mx0 = (TEXT_X0 + TEXT_X1 - mask.width) // 2
    alpha = mask.load()
    for yy in range(mask.height):
        y = PAINT_Y0 + yy
        for xx in range(mask.width):
            value = alpha[xx, yy]
            if value < MID_ALPHA:
                continue
            samples = bright if value >= BRIGHT_ALPHA else mid
            index = nearest_sample(samples, y, mx0 + xx)
            if index is not None:
                rows[y][mx0 + xx] = index

    patched = asset
    for start, packets, width, block_rows in groups:
        patched = imd.encode_image(patched, start, packets, width, block_rows, rows)
    imd.replace_asset(data, ASSET_INDEX, patched)
    out = Path(args.out_imgdat)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)

    height = len(rows)
    preview = Image.new("RGB", (width * 2, height * 2 * len(palettes)), (0, 0, 0))
    for pi, palette in enumerate(palettes):
        frame = Image.new("RGB", (width, height))
        frame.putdata([palette[v] for row in rows for v in row])
        preview.paste(frame.resize((width * 2, height * 2), Image.NEAREST), (0, pi * height * 2))
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview.save(preview_path)
    print(f"patched IMG.DAT -> {out}")
    print(f"banner preview -> {preview_path}")


if __name__ == "__main__":
    main()
