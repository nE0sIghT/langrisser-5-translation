#!/usr/bin/env python3
"""Stamp the translator credit lines onto the Saturn title screen (TITLE1.DAT).

This mirrors the PS1 title-credit path (`lang5_imgdat.draw_title_credits`): the
original Japanese/English title art is kept and the fan-translation credit lines
are drawn into it. The Saturn title is the big VDP2-cell image inside the
`TITLE1.DAT` container (see `saturn_container.py` / docs/SATURN_DISC_FORMAT.md),
so the flow is: de-tile the cells -> draw the lines in the linear bitmap ->
re-tile only the cells touched, splicing them back so the file size is preserved.

The image's 256-colour CLUT is in the container descriptor (the second of its two
palettes; see `saturn_container.image_clut_offset`), so the credit ink index is
chosen the same way the PS1 build does — `nearest_palette_index` to a light
target — instead of being hard-coded. `--ink` overrides it; `--y0` places the
lines. A colour preview is emitted from the real palette for review.

The 1-bit text rasteriser and the palette match are reused from the PS1 tooling
(`lang5_imgdat.text_mask`, `nearest_palette_index`); no logic is duplicated.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from PIL import Image, ImageFont

import saturn_container as sc
from lang5_project import add_language_args, language_from_args

SCRIPTS = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("lang5_imgdat", SCRIPTS / "lang5_imgdat.py")
imd = importlib.util.module_from_spec(_spec)
sys.modules["lang5_imgdat"] = imd
_spec.loader.exec_module(imd)

FONT = "data/fonts/DejaVuSerif-Bold.ttf"
CREDIT_TARGET_RGB = (240, 240, 240)   # light ink, matched into the title palette
DEFAULT_FONT_SIZE = 11
DEFAULT_LINE_STEP = 12       # vertical spacing between credit lines
DEFAULT_Y0 = 186             # first credit baseline; 3 lines fit inside 224


def credit_lines(args: argparse.Namespace) -> list[str]:
    if args.line:
        return list(args.line)
    version = args.version or "1"
    commit = imd.git_short_hash()
    return imd.default_title_credit_lines(version, commit)


def fit_mask(line: str, font_path: str, font_size: int, width: int) -> Image.Image:
    """Render `line` at `font_size`, shrinking the font until it fits `width`."""
    for size in range(font_size, 5, -1):
        mask = imd.text_mask(line, ImageFont.truetype(font_path, size))
        if mask.width <= width:
            return mask
    raise SystemExit(f"credit line does not fit {width}px even at the minimum size: {line!r}")


def stamp(pixels: bytearray, width: int, lines: list[str], font_path: str,
          y0: int, ink: int, font_size: int, step: int) -> None:
    height = len(pixels) // width
    for i, line in enumerate(lines):
        mask = fit_mask(line, font_path, font_size, width)
        x0 = (width - mask.width) // 2
        y = y0 + i * step
        if y + mask.height > height:
            raise SystemExit(f"credit line {i + 1} falls below the image ({y + mask.height}>{height})")
        pix = mask.load()
        for my in range(mask.height):
            row = (y + my) * width
            for mx in range(mask.width):
                if pix[mx, my]:
                    pixels[row + x0 + mx] = ink


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_language_args(ap)
    ap.add_argument("--title", default="work/build/saturn/TITLE1.DAT")
    ap.add_argument("--out-title", default="work/build/saturn/TITLE1.ru.DAT")
    ap.add_argument("--out-preview", default="work/build/saturn/title_credits_preview.png")
    ap.add_argument("--font", default=FONT)
    ap.add_argument("--ink", type=int, default=None,
                    help="ink palette index (default: nearest to a light colour)")
    ap.add_argument("--y0", type=int, default=DEFAULT_Y0)
    ap.add_argument("--font-size", type=int, default=DEFAULT_FONT_SIZE)
    ap.add_argument("--line-step", type=int, default=DEFAULT_LINE_STEP)
    ap.add_argument("--cols", type=int, default=sc.DEFAULT_CELL_COLS)
    ap.add_argument("--asset", type=int, default=None,
                    help="image sub-asset index (default: the container's first image)")
    ap.add_argument("--line", action="append",
                    help="override a credit line (repeatable); default uses the PS1 credit set")
    ap.add_argument("--version", default=None)
    args = ap.parse_args()
    # language_from_args validates the pack is well-formed even though the credit
    # text is language-independent, keeping the Saturn flow parallel to PS1.
    language_from_args(args)

    data = bytearray(Path(args.title).read_bytes())
    cont = sc.load(args.title)
    images = cont.images()
    if not images:
        raise SystemExit(f"{args.title}: no image sub-asset found")
    desc, img = images[0] if args.asset is None else next(
        ((d, e) for d, e in images if e.index == args.asset),
        (None, None))
    if img is None:
        raise SystemExit(f"{args.title}: no image sub-asset {args.asset}")

    clut_off = sc.image_clut_offset(cont.sub(desc))
    if clut_off is None:
        raise SystemExit(f"{args.title}: no image CLUT in the descriptor")
    palette = sc.read_clut(cont.sub(desc), clut_off)
    ink = args.ink if args.ink is not None else imd.nearest_palette_index(
        palette, CREDIT_TARGET_RGB)

    cells = cont.sub(img)
    pixels, width, _ = sc.detile(cells, args.cols)
    lines = credit_lines(args)
    stamp(pixels, width, lines, args.font, args.y0, ink,
          args.font_size, args.line_step)

    # Re-tile only the full cell-rows and splice them back, so the trailing
    # partial cell and every byte outside the edit are preserved (fixed size).
    retiled = sc.retile(pixels, width, args.cols)
    new_cells = retiled + cells[len(retiled):]
    assert len(new_cells) == len(cells), "cell payload size must be preserved"
    data[img.offset:img.end] = new_cells
    out = Path(args.out_title)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(bytes(data))
    assert len(out.read_bytes()) == len(Path(args.title).read_bytes()), "TITLE1 size must be preserved"

    # Colour preview from the image's real palette.
    prev_px, _, prev_h = sc.detile(new_cells, args.cols)
    preview = Image.new("RGB", (width, prev_h))
    preview.putdata([palette[v] for v in prev_px])
    preview.save(args.out_preview)
    print(f"patched title -> {out}  (lines: {len(lines)}, ink {ink}, y0 {args.y0})")
    print(f"colour preview -> {args.out_preview}")


if __name__ == "__main__":
    main()
