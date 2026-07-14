#!/usr/bin/env python3
"""Repair natively-encoded glyphs whose Saturn font slot differs from PS1.

The translation encodes some characters through *native* tokens taken from the
PS1 slot->char map (`data/font_map`): `○` in "Нажмите ○", the standalone
hyphen, digits, latin. The Saturn `SYSTEM.DAT` glyph plane holds a different
glyph at many of those slots (the kanji region is reordered; the tail is
shifted), so on Saturn such characters render as unrelated kanji — the
"sigma/lambda hieroglyph" bug.

This step runs on the font-stage SYSTEM file: for every character the
translated content actually encodes through a native token, it compares the
Saturn slot bitmap against the PS1 slot bitmap and, when they differ, copies
the PS1 12x12 glyph into the Saturn slot (both planes share the 18-byte cell
format). Slots owned by the font build itself (Cyrillic assignments, native
visual overrides) are excluded. Only characters the translation uses are
touched, so untranslated Saturn strings keep their original glyphs elsewhere.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from lang5_build_font import GLYPH_BYTES, NATIVE_VISUAL_OVERRIDES
from lang5_project import add_language_args, language_from_args

TAG_RE = re.compile(r"<\$[0-9A-Fa-f]{4}>")


def content_chars(translation_root: Path, string_maps: list[Path],
                  grid: Path | None) -> set[str]:
    chars: set[str] = set()
    for fp in sorted(translation_root.glob("*/chunk_*.txt")):
        for raw in fp.read_text(encoding="utf-8").splitlines():
            if "\t" in raw and not raw.startswith("#"):
                chars.update(TAG_RE.sub("", raw.split("\t", 1)[1]))
    for mp in string_maps:
        if not mp.exists():
            continue
        data = json.loads(mp.read_text(encoding="utf-8"))
        values = data.values() if isinstance(data, dict) else (
            e.get("text") or "" for e in data)
        for text in values:
            if text and text != "{BLANK}":
                chars.update(text)
    if grid is not None and grid.exists():
        for run in json.loads(grid.read_text(encoding="utf-8"))["runs"]:
            chars.update(run)
    chars.discard(" ")
    chars.discard("\t")
    return chars


def char_to_native_token(tbl: Path, assigned: set[int]) -> dict[str, int]:
    """Lowest single-char token per char from the generated tbl, natives only."""
    best: dict[str, int] = {}
    for line in tbl.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if len(key) != 4 or len(value) != 1:
            continue
        try:
            tok = int(key, 16)
        except ValueError:
            continue
        if tok in assigned or tok in NATIVE_VISUAL_OVERRIDES or tok == 0:
            continue
        if value not in best or tok < best[value]:
            best[value] = tok
    return best


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_language_args(ap)
    ap.add_argument("--system-in", required=True,
                    help="Font-stage Saturn SYSTEM file to fix in place or copy.")
    ap.add_argument("--system-out", default=None)
    ap.add_argument("--ps1-system", default="work/extracted/SYSTEM.BIN")
    ap.add_argument("--tbl", required=True)
    ap.add_argument("--assignments", required=True,
                    help="Build font slot assignments CSV (owned slots are skipped).")
    ap.add_argument("--translation-root", required=True)
    ap.add_argument("--strings", action="append", default=[],
                    help="Translated string map JSONs (repeatable).")
    args = ap.parse_args()
    lang = language_from_args(args)

    assigned = {
        int(r["index_dec"])
        for r in csv.DictReader(open(args.assignments, encoding="utf-8"))
    }
    chars = content_chars(
        Path(args.translation_root),
        [Path(p) for p in args.strings],
        lang.name_entry_grid,
    )
    natives = char_to_native_token(Path(args.tbl), assigned)

    data = bytearray(Path(args.system_in).read_bytes())
    ps1 = Path(args.ps1_system).read_bytes()
    fixed: list[str] = []
    for ch in sorted(chars):
        tok = natives.get(ch)
        if tok is None:
            continue  # assigned pairs/singles or unencodable; not a native slot
        lo, hi = tok * GLYPH_BYTES, (tok + 1) * GLYPH_BYTES
        if hi > min(len(data), len(ps1)):
            raise SystemExit(f"native token {tok:#06x} ({ch!r}) beyond the glyph plane")
        if data[lo:hi] != ps1[lo:hi]:
            data[lo:hi] = ps1[lo:hi]
            fixed.append(f"{tok:#06x}={ch!r}")

    out = Path(args.system_out) if args.system_out else Path(args.system_in)
    out.write_bytes(bytes(data))
    print(f"native glyphs copied from PS1: {len(fixed)} -> {out}")
    if fixed:
        print("  " + " ".join(fixed))


if __name__ == "__main__":
    main()
