#!/usr/bin/env python3
"""Point natively-encoded characters at the real Saturn glyph slots.

The translation encodes some characters through *native* tokens taken from the
PS1 slot->char map (`data/font_map`): `○`, the standalone hyphen, arrows, `×`.
The Saturn `SYSTEM.DAT` glyph plane is reordered in that region, so the PS1
token often points at a different Saturn glyph — the "sigma/lambda hieroglyph"
bug. The Saturn font already contains most of those glyphs, just at other
slots (`○` at 0x5F4, `-` at 0x380, ...), and those slots must not be handed
out as sacrificial Cyrillic slots.

Two subcommands around the font build:

- `plan` (before slot assignment): collect every character the translated
  content encodes through a native token, compare the PS1 and Saturn bitmaps
  at that token, and locate the exact PS1 bitmap elsewhere in the *original*
  Saturn plane. Emits a JSON plan `{char, ps1_token, saturn_slot|null}`; the
  found slots feed `lang5_assign_font_slots --exclude-slots` so the assigner
  keeps them.
- `apply` (after the font build): remap the generated `.tbl` so each planned
  character encodes to its Saturn slot (stale mappings removed); characters
  whose glyph exists nowhere in the Saturn plane (`saturn_slot: null`, e.g.
  `×` — the Saturn original spells 2割/3付4 instead) get the PS1 12x12 bitmap
  copied into the PS1-map slot (both planes share the 18-byte cell format).

Runs before anything encodes with the `.tbl`, so reflow, rewrap, SYSTEM/SCEN
pack and name-entry all use the corrected slots.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from lang5_build_font import GLYPH_BYTES, NATIVE_VISUAL_OVERRIDES
from lang5_project import COMMON_FONT_MAP, add_language_args, language_from_args

TAG_RE = re.compile(r"<\$[0-9A-Fa-f]{4}>")
PLANE_SLOTS = 1835   # both fonts end at slot 1834; Saturn data follows


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


def ps1_native_tokens(groups_report: Path) -> dict[str, int]:
    """Lowest PS1-map slot per single character (the encoder's choice)."""
    best: dict[str, int] = {}
    for row in csv.DictReader(open(groups_report, encoding="utf-8")):
        if not row["index_dec"].isdigit():
            continue
        tok = int(row["index_dec"])
        ch = row["char"]
        if len(ch) != 1 or tok == 0 or tok in NATIVE_VISUAL_OVERRIDES:
            continue
        if ch not in best or tok < best[ch]:
            best[ch] = tok
    return best


def glyph(plane: bytes, tok: int) -> bytes:
    return plane[tok * GLYPH_BYTES:(tok + 1) * GLYPH_BYTES]


def cmd_plan(args: argparse.Namespace, lang) -> None:
    chars = content_chars(
        Path(args.translation_root),
        [Path(p) for p in args.strings],
        lang.name_entry_grid,
    )
    natives = ps1_native_tokens(Path(args.groups_report))
    sat = Path(args.saturn_orig).read_bytes()
    ps1 = Path(args.ps1_system).read_bytes()
    plan: list[dict] = []
    taken: set[int] = set()
    for ch in sorted(chars):
        tok = natives.get(ch)
        if tok is None:
            continue
        want = glyph(ps1, tok)
        if glyph(sat, tok) == want:
            continue
        slot = next((s for s in range(PLANE_SLOTS)
                     if s not in taken and s != 0
                     and s not in NATIVE_VISUAL_OVERRIDES
                     and glyph(sat, s) == want), None)
        if slot is not None:
            taken.add(slot)
        plan.append({"char": ch, "ps1_token": tok, "saturn_slot": slot})
    out = Path(args.plan)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    found = sum(1 for p in plan if p["saturn_slot"] is not None)
    print(f"native glyph plan: {found} on existing Saturn slots, "
          f"{len(plan) - found} need PS1 copies -> {out}")


def cmd_apply(args: argparse.Namespace) -> None:
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    assigned = {
        int(r["index_dec"])
        for r in csv.DictReader(open(args.assignments, encoding="utf-8"))
    }
    clash = [p for p in plan
             if p["saturn_slot"] is not None and p["saturn_slot"] in assigned]
    if clash:
        raise SystemExit(
            "planned Saturn glyph slots were assigned to Cyrillic tiles "
            f"(pass the plan to lang5_assign_font_slots --exclude-slots): {clash}")

    tbl_path = Path(args.tbl)
    lines = tbl_path.read_text(encoding="utf-8").splitlines()
    remap = {p["ps1_token"]: (p["saturn_slot"], p["char"])
             for p in plan if p["saturn_slot"] is not None}
    stale_keys = {f"{slot:04X}" for slot, _ in remap.values()}
    out_lines: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0] if "=" in line else ""
        if len(key) == 4 and not line.startswith("#"):
            try:
                tok = int(key, 16)
            except ValueError:
                tok = -1
            if tok in remap:
                continue              # stale PS1 mapping for the moved char
            if key.upper() in stale_keys:
                continue              # PS1-map char sitting on the reused slot
        out_lines.append(line)
    for old, (new, ch) in sorted(remap.items()):
        out_lines.append(f"{new:04X}={ch}")
    tbl_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    data = bytearray(Path(args.system_in).read_bytes())
    ps1 = Path(args.ps1_system).read_bytes()
    copied = []
    for p in plan:
        if p["saturn_slot"] is None:
            tok = p["ps1_token"]
            lo, hi = tok * GLYPH_BYTES, (tok + 1) * GLYPH_BYTES
            data[lo:hi] = ps1[lo:hi]
            copied.append(f"{tok:#06x}={p['char']!r}")
    Path(args.system_in).write_bytes(bytes(data))
    print(f"native glyphs: remapped {len(remap)} to existing Saturn slots"
          + (f", copied {len(copied)} from PS1 ({' '.join(copied)})" if copied else ""))
    if remap:
        print("  " + " ".join(f"{old:#06x}->{new:#06x}={ch!r}"
                              for old, (new, ch) in sorted(remap.items())))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_language_args(ap)
    ap.add_argument("command", choices=["plan", "apply"])
    ap.add_argument("--plan", required=True, help="Plan JSON path.")
    ap.add_argument("--ps1-system", default="work/extracted/SYSTEM.BIN")
    ap.add_argument("--saturn-orig", default=None,
                    help="plan: original (untranslated) Saturn SYSTEM.DAT.")
    ap.add_argument("--groups-report", default=str(COMMON_FONT_MAP))
    ap.add_argument("--translation-root", default=None)
    ap.add_argument("--strings", action="append", default=[],
                    help="plan: translated string map JSONs (repeatable).")
    ap.add_argument("--tbl", default=None, help="apply: .tbl remapped in place.")
    ap.add_argument("--system-in", default=None,
                    help="apply: font-stage SYSTEM file (fallback copies land here).")
    ap.add_argument("--assignments", default=None,
                    help="apply: build font slot assignments CSV.")
    args = ap.parse_args()
    lang = language_from_args(args)
    if args.command == "plan":
        if not (args.saturn_orig and args.translation_root):
            raise SystemExit("plan requires --saturn-orig and --translation-root")
        cmd_plan(args, lang)
    else:
        if not (args.tbl and args.system_in and args.assignments):
            raise SystemExit("apply requires --tbl, --system-in and --assignments")
        cmd_apply(args)


if __name__ == "__main__":
    main()
