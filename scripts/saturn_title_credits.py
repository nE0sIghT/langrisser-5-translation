#!/usr/bin/env python3
"""Stamp the translator credit lines onto the Saturn title screen (TITLE1.DAT).

The visible title is not a linear bitmap: the container descriptor carries two
VDP2 tilemaps over one shared 8x8-cell store — an 80x28 hi-res overlay (logo,
"press start button", the (C) line; pixel value 255 is its transparent
background) and a 40x28 background plane (the stone art). A linear de-tile of
the cell store therefore looks like garbage; earlier credits stamped that way
landed on random cells.

PS1 draws its credits into the title art, so the Saturn analogue is the stone
background plane. Its cells in the band under the (C) line are referenced
exactly once (verified at run time), so the credit pixels are drawn straight
into those cells in place: no new cells are needed (the store has only two
free cells) and the file size is preserved.

Text rendering reuses the PS1 title-credit pipeline unchanged
(`lang5_imgdat.title_text_mask` / `title_alpha_table` / `paste_alpha_mask` and
the same credit lines), so the three lines carry the same anti-aliased look;
the vertical specs are compressed into the 24-pixel band y=192..216 (the
Saturn art is 224 lines tall vs 240 on PS1). The emitted preview composites
both planes the way the console does, for review.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from dataclasses import dataclass
from types import SimpleNamespace
from pathlib import Path

from PIL import Image

import saturn_container as sc
from lang5_binfmt import BE
from lang5_project import add_language_args, language_from_args

SCRIPTS = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("lang5_imgdat", SCRIPTS / "lang5_imgdat.py")
imd = importlib.util.module_from_spec(_spec)
sys.modules["lang5_imgdat"] = imd
_spec.loader.exec_module(imd)

CELL_BYTES = 64          # 8x8 pixels, 8bpp
CHAR_MASK = 0x0FFF       # pattern-name character index field


@dataclass(frozen=True)
class LineSpec:
    font_size: int
    stroke_width: float
    raw_height: int
    y: int


# The PS1 specs squeezed into the free stone band under the overlay's (C)
# line: rows 24..26 of the background plane, y=192..216.
SATURN_CREDIT_SPECS = [
    LineSpec(font_size=16, stroke_width=0.14, raw_height=7, y=193),
    LineSpec(font_size=14, stroke_width=0.12, raw_height=7, y=201),
    LineSpec(font_size=14, stroke_width=0.12, raw_height=7, y=209),
]


@dataclass
class Screen:
    """The two tilemaps and shared cell store behind the title screen."""

    desc: bytes
    cells: bytearray
    palette: list[tuple[int, int, int]]
    overlay: list[list[int]]      # cols1 x rows1 pattern-name entries
    background: list[list[int]]   # cols2 x rows2


def parse_screen(cont: sc.Container) -> Screen:
    desc = cont.sub(cont.entries[0])
    cells = bytearray(cont.sub(cont.entries[1]))
    cols1, rows1 = BE.u16(desc, 0x04), BE.u16(desc, 0x06)
    cols2, rows2 = BE.u16(desc, 0x08), BE.u16(desc, 0x0A)
    nt1 = BE.u32(desc, 0x14)
    nt2 = nt1 + cols1 * rows1 * 2
    total = BE.u32(desc, 0x00)
    if total != nt2 + cols2 * rows2 * 2:
        raise SystemExit(
            f"unexpected TITLE descriptor layout: total {total:#x} != "
            f"tables end {nt2 + cols2 * rows2 * 2:#x}"
        )
    clut = sc.image_clut_offset(desc)
    if clut is None:
        raise SystemExit("no image CLUT in the TITLE descriptor")
    palette = sc.read_clut(desc, clut)

    def table(off: int, cols: int, rows: int) -> list[list[int]]:
        return [
            [BE.u16(desc, off + (cy * cols + cx) * 2) for cx in range(cols)]
            for cy in range(rows)
        ]

    return Screen(desc, cells, palette,
                  table(nt1, cols1, rows1), table(nt2, cols2, rows2))


def cell_usage(screen: Screen) -> dict[int, int]:
    usage: dict[int, int] = {}
    for plane in (screen.overlay, screen.background):
        for row in plane:
            for entry in row:
                idx = entry & CHAR_MASK
                usage[idx] = usage.get(idx, 0) + 1
    return usage


def compose_plane(screen: Screen, plane: list[list[int]]) -> list[bytearray]:
    rows = [bytearray(len(plane[0]) * 8) for _ in range(len(plane) * 8)]
    for cy, entries in enumerate(plane):
        for cx, entry in enumerate(entries):
            idx = entry & CHAR_MASK
            tile = screen.cells[idx * CELL_BYTES:(idx + 1) * CELL_BYTES]
            for py in range(8):
                rows[cy * 8 + py][cx * 8:cx * 8 + 8] = tile[py * 8:py * 8 + 8]
    return rows


def credit_lines(args: argparse.Namespace) -> list[str]:
    if args.line:
        return list(args.line)
    version = args.version or "1"
    return imd.default_title_credit_lines(version, imd.git_short_hash())


def fitted_mask(line: str, font_path: str, spec: LineSpec, width: int) -> Image.Image:
    for size in range(spec.font_size, 7, -1):
        mask = imd.title_text_mask(line, font_path, size, spec.stroke_width)
        raw = mask.resize((mask.width, spec.raw_height), Image.Resampling.LANCZOS)
        if raw.width <= width:
            return raw
    raise SystemExit(f"credit line does not fit {width}px: {line!r}")


def dominant_index(rows: list[bytearray], y0: int, y1: int) -> int:
    counts: dict[int, int] = {}
    for y in range(y0, y1):
        for value in rows[y]:
            counts[value] = counts.get(value, 0) + 1
    return max(counts, key=counts.get)


def stamp_background(screen: Screen, lines: list[str], font_path: str) -> None:
    plane = screen.background
    width, height = len(plane[0]) * 8, len(plane) * 8
    rows = compose_plane(screen, plane)
    original = [bytes(row) for row in rows]

    band = (SATURN_CREDIT_SPECS[0].y,
            SATURN_CREDIT_SPECS[-1].y + SATURN_CREDIT_SPECS[-1].raw_height)
    shim = SimpleNamespace(width=width, height=height,
                           background_index=dominant_index(rows, *band))
    alpha_table = imd.title_alpha_table(screen.palette, shim,
                                        imd.TITLE_CREDIT_TARGET_RGB)
    for spec, line in zip(SATURN_CREDIT_SPECS, lines):
        raw = fitted_mask(line, font_path, spec, width)
        imd.paste_alpha_mask(rows, shim, raw,
                             (width - raw.width) // 2, spec.y, alpha_table)

    # Write the changed pixels back into the cells they came from. Every
    # touched cell must be referenced exactly once across both tilemaps,
    # otherwise the edit would also appear somewhere else on screen.
    usage = cell_usage(screen)
    for cy in range(len(plane)):
        for cx in range(len(plane[0])):
            changed = any(
                rows[cy * 8 + py][cx * 8:cx * 8 + 8]
                != original[cy * 8 + py][cx * 8:cx * 8 + 8]
                for py in range(8)
            )
            if not changed:
                continue
            idx = plane[cy][cx] & CHAR_MASK
            if usage[idx] != 1:
                raise SystemExit(
                    f"credit pixels hit shared cell {idx:#x} at "
                    f"({cx},{cy}); move the lines to uniquely-mapped rows"
                )
            for py in range(8):
                screen.cells[idx * CELL_BYTES + py * 8:
                             idx * CELL_BYTES + py * 8 + 8] = \
                    rows[cy * 8 + py][cx * 8:cx * 8 + 8]


def overlay_transparent_value(screen: Screen) -> int:
    """The overlay's transparent pixel value = its uniform filler tile.

    The filler differs per screen (255 on TITLE1, 254 on TITLE2), so it is
    derived from the most common overlay entry rather than hard-coded.
    """
    counts: dict[int, int] = {}
    for row in screen.overlay:
        for entry in row:
            counts[entry] = counts.get(entry, 0) + 1
    filler = max(counts, key=counts.get) & CHAR_MASK
    tile = screen.cells[filler * CELL_BYTES:(filler + 1) * CELL_BYTES]
    values = set(tile)
    if len(values) != 1:
        raise SystemExit("overlay filler tile is not uniform; cannot infer transparency")
    return tile[0]


def screen_preview(screen: Screen) -> Image.Image:
    """Composite both planes the way the console shows them (640x224)."""
    bg = compose_plane(screen, screen.background)
    fg = compose_plane(screen, screen.overlay)
    transparent = overlay_transparent_value(screen)
    width, height = len(fg[0]), len(fg)
    img = Image.new("RGB", (width, height))
    px = img.load()
    for y in range(height):
        for x in range(width):
            value = fg[y][x]
            if value == transparent:
                value = bg[y][x // 2]
            px[x, y] = screen.palette[value]
    return img


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    add_language_args(ap)
    ap.add_argument("--title", default="work/build/saturn/TITLE1.DAT")
    ap.add_argument("--out-title", default="work/build/saturn/TITLE1.ru.DAT")
    ap.add_argument("--out-preview", default="work/build/saturn/title_credits_preview.png")
    ap.add_argument("--font", default=None,
                    help="credit font (default: the PS1 title-credit font)")
    ap.add_argument("--line", action="append",
                    help="override a credit line (repeatable); default uses the PS1 credit set")
    ap.add_argument("--version", default=None)
    args = ap.parse_args()
    # language_from_args validates the pack even though credits are
    # language-independent, keeping the Saturn flow parallel to PS1.
    language_from_args(args)

    data = bytearray(Path(args.title).read_bytes())
    cont = sc.load(args.title)
    screen = parse_screen(cont)
    font_path = imd.resolve_title_font(args.font)
    lines = credit_lines(args)
    if len(lines) != len(SATURN_CREDIT_SPECS):
        raise SystemExit(f"expected {len(SATURN_CREDIT_SPECS)} credit lines, got {len(lines)}")
    stamp_background(screen, lines, font_path)

    cells_entry = cont.entries[1]
    assert len(screen.cells) == cells_entry.size, "cell store size must be preserved"
    data[cells_entry.offset:cells_entry.end] = screen.cells
    out = Path(args.out_title)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(bytes(data))
    assert len(out.read_bytes()) == len(Path(args.title).read_bytes()), \
        "TITLE1 size must be preserved"

    screen_preview(screen).save(args.out_preview)
    print(f"patched title -> {out}  (3 credit lines into the background plane)")
    print(f"screen preview -> {args.out_preview}")


if __name__ == "__main__":
    main()
