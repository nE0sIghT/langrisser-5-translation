#!/usr/bin/env python3
"""Build translated Saturn data files from a universal `data/lang` pack.

Platform is a build-time choice: the same pack that produces the PS1 PPF drives
this Saturn flow. It reuses the shared stages unchanged:

1. `lang5_build_font` draws the target alphabet into the Saturn `SYSTEM.DAT`
   glyph plane (same 12x12x18 format and slots as PS1) and emits the `.tbl`.
2. `lang5_saturn_apply` inserts the translated scenario text into `SCEN.DAT`
   (fixed-size where it fits, growing + re-laying-out blocks where it does not).

Outputs the translated `SYSTEM.DAT` and `SCEN.DAT` under `work/build/saturn/`.
Disc re-mastering (injecting the grown files back into the mixed-mode BIN/CUE)
is the remaining output step; see docs/SATURN_DISC_FORMAT.md.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from lang5_project import COMMON_FONT_MAP, add_language_args, language_from_args


def run(*cmd: object) -> None:
    subprocess.run([sys.executable, *(str(c) for c in cmd)], check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_language_args(ap)
    ap.add_argument("--saturn-dir", default="work/build/saturn",
                    help="directory holding the extracted Saturn SYSTEM.DAT/SCEN.DAT")
    ap.add_argument("--assignments", default=None,
                    help="font slot assignments CSV (default: the pack's tracked file)")
    args = ap.parse_args()

    lang = language_from_args(args)
    scripts = Path(__file__).resolve().parent
    saturn = Path(args.saturn_dir)
    system_in = saturn / "SYSTEM.DAT"
    scen_in = saturn / "SCEN.DAT"
    for path in (system_in, scen_in):
        if not path.exists():
            raise SystemExit(
                f"missing {path}; extract it first: "
                f"python3 scripts/saturn_disc.py extract {path.name} {path}"
            )

    assignments = Path(args.assignments) if args.assignments else lang.font_assignments
    system_font = saturn / f"SYSTEM.DAT.{lang.suffix}.font"
    tbl = saturn / f"lang5_{lang.suffix}.saturn.tbl"

    font_cmd = [
        scripts / "lang5_build_font.py",
        "--lang", args.lang, "--lang-root", args.lang_root,
        "--groups-report", COMMON_FONT_MAP,
        "--assignments", assignments,
        "--system-bin", system_in,
        "--out-system-bin", system_font,
        "--out-tbl", tbl,
        "--font-size", str(lang.font_size),
    ]
    if lang.font:
        font_cmd.extend(["--font", lang.font])
    if lang.caps_font:
        font_cmd.extend(["--caps-font", lang.caps_font,
                         "--caps-font-size", str(lang.caps_font_size)])
    run(*font_cmd)

    run(scripts / "lang5_saturn_apply.py",
        "--lang", args.lang, "--lang-root", args.lang_root,
        "--scen", scen_in,
        "--out-scen", saturn / f"SCEN.{lang.suffix}.DAT",
        "--tbl", tbl)

    print(f"saturn build: font -> {system_font}, scen -> {saturn / f'SCEN.{lang.suffix}.DAT'}")


if __name__ == "__main__":
    main()
