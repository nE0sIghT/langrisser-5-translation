#!/usr/bin/env python3
"""Build translated Saturn data files from a universal `data/lang` pack.

Platform is a build-time choice: the same pack that produces the PS1 PPF drives
this Saturn flow. It reuses the shared stages unchanged:

1. regenerate the common PS1 SYSTEM source and resolved target strings;
2. complete font assignments into a build copy and emit a Saturn `.tbl`;
3. reflow, validate and rewrap a generated translation copy with that table;
4. pack Saturn `SYSTEM.DAT` through platform mappings;
5. insert translated scenario text into Saturn `SCEN.DAT` through platform
   mappings (fixed-size where it fits, growing + re-laying-out blocks where it
   does not).

Outputs the translated `SYSTEM.DAT` and `SCEN.DAT` under `work/build/saturn/`.
With `--remaster-disc`, it also writes a translated mixed-mode BIN/CUE under
the same directory.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from lang5_platform import add_platform_args, platform_from_args
from lang5_project import COMMON_FONT_MAP, add_language_args, language_from_args


def run(*cmd: object) -> None:
    result = subprocess.run([sys.executable, *(str(c) for c in cmd)])
    if result.returncode:
        raise SystemExit(result.returncode)


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
    add_platform_args(ap, "saturn")
    ap.add_argument("--saturn-dir", default="work/build/saturn",
                    help="directory holding the extracted Saturn SYSTEM.DAT/SCEN.DAT")
    ap.add_argument("--assignments", default=None,
                    help="font slot assignments CSV (default: the pack's tracked file)")
    ap.add_argument("--translation-root", default=None,
                    help="Override the language pack's translated-text root.")
    ap.add_argument("--ps1-scen", default="work/extracted/SCEN.DAT",
                    help="PS1 SCEN.DAT used as the common script source.")
    ap.add_argument("--ps1-scen2", default="work/extracted/SCEN2.DAT",
                    help="PS1 SCEN2.DAT used for common validation/font-slot safety.")
    ap.add_argument("--ps1-system", default="work/extracted/SYSTEM.BIN",
                    help="PS1 SYSTEM.BIN used as the common SYSTEM source.")
    ap.add_argument("--cue", default="iso/saturn/LANGRISSER_5.cue",
                    help="source Saturn CUE for --remaster-disc")
    ap.add_argument("--remaster-disc", action="store_true",
                    help="build a translated BIN/CUE in addition to extracted files")
    ap.add_argument("--out-bin", default=None,
                    help="translated Saturn BIN path for --remaster-disc")
    ap.add_argument("--out-cue", default=None,
                    help="translated Saturn CUE path for --remaster-disc")
    ap.add_argument("--allow-unmapped", action="store_true",
                    help="Diagnostic mode: preserve unmapped Saturn SCEN/SYSTEM data.")
    args = ap.parse_args()

    lang = language_from_args(args)
    platform = platform_from_args(args)
    if platform.code != "saturn":
        raise SystemExit(f"this builder only supports the saturn platform, got {platform.code}")
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
    for path in (Path(args.ps1_scen), Path(args.ps1_scen2), Path(args.ps1_system)):
        if not path.exists():
            raise SystemExit(
                f"missing common PS1 source {path}; extract PS1 base files first"
            )

    translation_root = (Path(args.translation_root)
                        if args.translation_root else lang.dump_root)
    build_translation_root = Path(f"work/build/translation.{lang.suffix}.saturn")
    if build_translation_root.exists():
        shutil.rmtree(build_translation_root)
    shutil.copytree(translation_root, build_translation_root)

    assignments = Path(args.assignments) if args.assignments else lang.font_assignments
    system_font = saturn / f"SYSTEM.DAT.{lang.suffix}.font"
    tbl = saturn / f"lang5_{lang.suffix}.saturn.tbl"

    system_source = Path(f"work/build/system_source.{lang.suffix}.json")
    run(scripts / "lang5_system_dump.py",
        "--system-bin", args.ps1_system,
        "--out", system_source)
    resolved_system_strings = Path(f"work/build/system_strings.{lang.suffix}.json")
    resolve_args = [
        scripts / "lang5_resolve_system_strings.py",
        "--lang", args.lang,
        "--lang-root", args.lang_root,
        "--system-source", system_source,
        "--out", resolved_system_strings,
    ]
    if lang.system_complete:
        resolve_args.append("--require-complete")
    run(*resolve_args)

    # Characters encoded through native PS1-map tokens can hit Saturn slots
    # that hold a different glyph (reordered kanji region). Plan the remap to
    # the Saturn slots that already hold the right glyphs, so the assigner
    # never sacrifices those slots; the .tbl is remapped after the font build.
    glyph_plan = Path(f"work/build/saturn/native_glyphs.{lang.suffix}.plan.json")
    run(scripts / "saturn_fix_native_glyphs.py",
        "--lang", args.lang, "--lang-root", args.lang_root,
        "plan",
        "--plan", glyph_plan,
        "--saturn-orig", system_in,
        "--ps1-system", args.ps1_system,
        "--translation-root", build_translation_root,
        "--strings", resolved_system_strings,
        "--strings", lang.root / "platforms" / platform.code / "system_strings.json")

    build_assignments = Path(f"work/build/font_slot_assignments.{lang.suffix}.saturn.csv")
    run(scripts / "lang5_assign_font_slots.py",
        "--lang", args.lang,
        "--lang-root", args.lang_root,
        "--groups-report", COMMON_FONT_MAP,
        "--assignments", assignments,
        "--out-assignments", build_assignments,
        "--translation-root", build_translation_root,
        "--menu-map", resolved_system_strings,
        "--system-source", system_source,
        "--scen", args.ps1_scen,
        "--scen2", args.ps1_scen2,
        "--max-slot", str(platform.max_font_slot),
        "--exclude-slots", glyph_plan)

    font_cmd = [
        scripts / "lang5_build_font.py",
        "--lang", args.lang, "--lang-root", args.lang_root,
        "--groups-report", COMMON_FONT_MAP,
        "--assignments", build_assignments,
        "--system-bin", system_in,
        "--out-system-bin", system_font,
        "--out-tbl", tbl,
        "--font-size", str(lang.font_size),
        "--max-slot", str(platform.max_font_slot),
    ]
    if lang.font:
        font_cmd.extend(["--font", lang.font])
    if lang.caps_font:
        font_cmd.extend(["--caps-font", lang.caps_font,
                         "--caps-font-size", str(lang.caps_font_size)])
    run(*font_cmd)
    # Remap the .tbl onto the planned Saturn slots before anything encodes
    # with it; PS1 bitmaps are copied only for glyphs Saturn lacks entirely.
    run(scripts / "saturn_fix_native_glyphs.py",
        "--lang", args.lang, "--lang-root", args.lang_root,
        "apply",
        "--plan", glyph_plan,
        "--ps1-system", args.ps1_system,
        "--tbl", tbl,
        "--system-in", system_font,
        "--assignments", build_assignments)

    reflowed_system_strings = Path(f"work/build/system_strings.{lang.suffix}.saturn.reflowed.json")
    run(scripts / "lang5_reflow_system_cards.py",
        "--strings", resolved_system_strings,
        "--out", reflowed_system_strings,
        "--tbl", tbl,
        "--system-source", system_source)
    run(scripts / "lang5_validate_system_ui.py",
        "--lang", args.lang,
        "--lang-root", args.lang_root,
        "--tbl", tbl,
        "--strings", reflowed_system_strings,
        "--system-source", system_source)
    run(scripts / "lang5_rewrap.py",
        "--lang", args.lang,
        "--lang-root", args.lang_root,
        "--translation-root", build_translation_root,
        "--tbl", tbl,
        "--scen", args.ps1_scen)
    run(scripts / "lang5_validate_translation.py",
        "--lang", args.lang,
        "--lang-root", args.lang_root,
        "--translation-root", build_translation_root,
        "--tbl", tbl,
        "--scen", args.ps1_scen,
        "--scen2", args.ps1_scen2)

    system_out = saturn / f"SYSTEM.{lang.suffix}.DAT"
    system_cmd: list[object] = [
        scripts / "lang5_saturn_system_pack.py",
        "--lang", args.lang,
        "--lang-root", args.lang_root,
        "--platform", args.platform,
        "--platform-root", args.platform_root,
        "--system-in", system_font,
        "--system-out", system_out,
        "--ps1-system", args.ps1_system,
        "--strings", reflowed_system_strings,
        "--platform-strings", lang.root / "platforms" / platform.code / "system_strings.json",
        "--tbl", tbl,
    ]
    if args.allow_unmapped:
        system_cmd.append("--allow-unmapped")
    run(*system_cmd)
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
    # The runtime addresses SYSTEM text through the pointer directory at
    # +0x8000; validate the final file against the write contract so no
    # stage can clobber it again (see docs/SATURN_DISC_FORMAT.md).
    run(scripts / "saturn_system_validate.py",
        "--orig", system_in,
        "--system", system_out,
        "--tbl", tbl)

    scen_out = saturn / f"SCEN.{lang.suffix}.DAT"
    scen_cmd: list[object] = [
        scripts / "lang5_saturn_apply.py",
        "--lang", args.lang, "--lang-root", args.lang_root,
        "--platform", args.platform,
        "--platform-root", args.platform_root,
        "--scen", scen_in,
        "--out-scen", scen_out,
        "--tbl", tbl,
        "--ps1-scen", args.ps1_scen,
    ]
    if args.allow_unmapped:
        scen_cmd.append("--allow-unmapped")
    run(*scen_cmd)

    # SCENARIO CLEAR banner (CLEAR.DAT), if extracted and the pack sets the text.
    clear_in = saturn / "CLEAR.DAT"
    if lang.scenario_clear and clear_in.exists():
        run(scripts / "saturn_scenario_clear.py",
            "--lang", args.lang, "--lang-root", args.lang_root,
            "--clear", clear_in,
            "--out-clear", saturn / f"CLEAR.{lang.suffix}.DAT")

    # Translator credits on both title screens (TITLE1/TITLE2), if extracted.
    for title_name in ("TITLE1", "TITLE2"):
        title_in = saturn / f"{title_name}.DAT"
        if title_in.exists():
            run(scripts / "saturn_title_credits.py",
                "--lang", args.lang, "--lang-root", args.lang_root,
                "--title", title_in,
                "--out-title", saturn / f"{title_name}.{lang.suffix}.DAT",
                "--out-preview", saturn / f"{title_name.lower()}_credits_{lang.suffix}_preview.png")

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
        for title_name in ("TITLE1", "TITLE2"):
            title_out = saturn / f"{title_name}.{lang.suffix}.DAT"
            if title_out.exists():
                remaster_cmd.extend(["--replace", f"/{title_name}.DAT={title_out}"])
        open_out = saturn / f"OPEN.{lang.suffix}.DAT"
        if open_out.exists():
            remaster_cmd.extend(["--replace", f"/OPEN.DAT={open_out}"])
        run(*remaster_cmd)

    print(f"saturn build: system -> {system_out}, scen -> {scen_out}")


if __name__ == "__main__":
    main()
