#!/usr/bin/env python3
"""Build translated Saturn data files from a universal `data/lang` pack.

Platform is a build-time choice: the same pack that produces the PS1 PPF drives
this Saturn flow. It reuses the shared stages unchanged:

1. `lang5_build_font` draws the target alphabet into the Saturn `SYSTEM.DAT`
   glyph plane (same 12x12x18 format and slots as PS1) and emits the `.tbl`.
2. `saturn_name_entry` patches the name-entry display/input tables in
   `SYSTEM.DAT` using the same target alphabet grid as the PS1 build.
3. `lang5_saturn_apply` inserts the translated scenario text into `SCEN.DAT`
   (fixed-size where it fits, growing + re-laying-out blocks where it does not).

Outputs the translated `SYSTEM.DAT` and `SCEN.DAT` under `work/build/saturn/`.
With `--remaster-disc`, it also writes a translated mixed-mode BIN/CUE under
the same directory.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from lang5_project import COMMON_FONT_MAP, add_language_args, language_from_args


def run(*cmd: object) -> None:
    subprocess.run([sys.executable, *(str(c) for c in cmd)], check=True)


def has_target_text(path: Path) -> bool:
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and stripped != "---":
            return True
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_language_args(ap)
    ap.add_argument("--saturn-dir", default="work/build/saturn",
                    help="directory holding the extracted Saturn SYSTEM.DAT/SCEN.DAT")
    ap.add_argument("--assignments", default=None,
                    help="font slot assignments CSV (default: the pack's tracked file)")
    ap.add_argument("--cue", default="iso/saturn/LANGRISSER_5.cue",
                    help="source Saturn CUE for --remaster-disc")
    ap.add_argument("--remaster-disc", action="store_true",
                    help="build a translated BIN/CUE in addition to extracted files")
    ap.add_argument("--out-bin", default=None,
                    help="translated Saturn BIN path for --remaster-disc")
    ap.add_argument("--out-cue", default=None,
                    help="translated Saturn CUE path for --remaster-disc")
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

    system_out = saturn / f"SYSTEM.{lang.suffix}.DAT"
    run(scripts / "lang5_saturn_system_pack.py",
        "--system-in", system_font,
        "--system-out", system_out,
        "--strings", f"work/build/system_strings.{lang.suffix}.json",
        "--tbl", tbl)
    run(scripts / "saturn_name_entry.py",
        "--lang", args.lang, "--lang-root", args.lang_root,
        "--system-in", system_out,
        "--system-out", system_out,
        "--tbl", tbl)
    if lang.now_loading:
        run(scripts / "saturn_now_loading.py",
            "--lang", args.lang, "--lang-root", args.lang_root,
            "--system", system_out,
            "--out-system", system_out,
            "--out-preview", saturn / f"now_loading_{lang.suffix}_preview.png")

    scen_out = saturn / f"SCEN.{lang.suffix}.DAT"
    run(scripts / "lang5_saturn_apply.py",
        "--lang", args.lang, "--lang-root", args.lang_root,
        "--scen", scen_in,
        "--out-scen", scen_out,
        "--tbl", tbl)

    # SCENARIO CLEAR banner (CLEAR.DAT), if extracted and the pack sets the text.
    clear_in = saturn / "CLEAR.DAT"
    if lang.scenario_clear and clear_in.exists():
        run(scripts / "saturn_scenario_clear.py",
            "--lang", args.lang, "--lang-root", args.lang_root,
            "--clear", clear_in,
            "--out-clear", saturn / f"CLEAR.{lang.suffix}.DAT")

    # Translator credits on the title screen (TITLE1.DAT container), if extracted.
    title_in = saturn / "TITLE1.DAT"
    if title_in.exists():
        run(scripts / "saturn_title_credits.py",
            "--lang", args.lang, "--lang-root", args.lang_root,
            "--title", title_in,
            "--out-title", saturn / f"TITLE1.{lang.suffix}.DAT")

    # Prologue poem in the attract loop (OPEN.DAT sub-asset 2), if extracted.
    open_in = saturn / "OPEN.DAT"
    if open_in.exists() and has_target_text(lang.poem):
        run(scripts / "saturn_poem_translate.py",
            "--lang", args.lang, "--lang-root", args.lang_root,
            "--open", open_in,
            "--out-open", saturn / f"OPEN.{lang.suffix}.DAT",
            "--out-preview", saturn / f"open_poem_{lang.suffix}_preview.png")

    if args.remaster_disc:
        out_bin = Path(args.out_bin) if args.out_bin else saturn / f"langrisser_v_{lang.suffix}_saturn.bin"
        out_cue = Path(args.out_cue) if args.out_cue else saturn / f"langrisser_v_{lang.suffix}_saturn.cue"
        remaster_cmd: list[object] = [
            scripts / "saturn_disc.py",
            "--cue", args.cue,
            "remaster",
            "--out-bin", out_bin,
            "--out-cue", out_cue,
            "--replace", f"/SCEN.DAT={scen_out}",
            "--replace", f"/SYSTEM.DAT={system_out}",
        ]
        clear_out = saturn / f"CLEAR.{lang.suffix}.DAT"
        if clear_out.exists():
            remaster_cmd.extend(["--replace", f"/CLEAR.DAT={clear_out}"])
        title_out = saturn / f"TITLE1.{lang.suffix}.DAT"
        if title_out.exists():
            remaster_cmd.extend(["--replace", f"/TITLE1.DAT={title_out}"])
        open_out = saturn / f"OPEN.{lang.suffix}.DAT"
        if open_out.exists():
            remaster_cmd.extend(["--replace", f"/OPEN.DAT={open_out}"])
        run(*remaster_cmd)

    print(f"saturn build: system -> {system_out}, scen -> {scen_out}")


if __name__ == "__main__":
    main()
