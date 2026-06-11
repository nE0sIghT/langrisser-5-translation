#!/usr/bin/env python3
"""Build the Langrisser V EN PPF patch.

Pipeline: EN font into SYSTEM.BIN -> insert EN dump into SCEN/SCEN2 ->
inject all three into a copy of the BIN -> PPF3 diff against the original.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from ppf3 import write_ppf3


def run(*cmd: str) -> None:
    subprocess.run([sys.executable, *cmd], check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--orig-bin", default="iso/SLPS-01818-9-B.bin")
    ap.add_argument("--en-dump", default="data/translation/en")
    ap.add_argument("--scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--scen2", default="work/extracted/SCEN2.DAT")
    ap.add_argument("--system", default="work/extracted/SYSTEM.BIN")
    ap.add_argument("--work-bin", default="work/build/langrisser_v_en.bin")
    ap.add_argument("--out-ppf", default="patches/langrisser_v_en.ppf")
    args = ap.parse_args()

    scripts = Path(__file__).parent

    run(scripts / "lang5_build_en_font.py", "--system-bin", args.system,
        "--out-system-bin", "work/build/SYSTEM.BIN.font",
        "--out-tbl", "work/tables/lang5_en.tbl")

    run(scripts / "lang5_patch_system_menu.py",
        "--system-in", "work/build/SYSTEM.BIN.font",
        "--system-out", "work/build/SYSTEM.BIN.en",
        "--menu-map", "data/translation/system_menu_map.json",
        "--menu-map", "data/translation/names_map.json",
        "--tbl", "work/tables/lang5_en.tbl")

    run(scripts / "lang5_sceninsert.py", "--scen", args.scen, "--scen2", args.scen2,
        "--dump-dir", args.en_dump, "--charmap", "work/tables/lang5_en.tbl",
        "--out-scen", "work/build/SCEN.en.DAT", "--out-scen2", "work/build/SCEN2.en.DAT")

    work_bin = Path(args.work_bin)
    work_bin.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.orig_bin, work_bin)

    for iso_path, local in (
        ("/L5/SCEN.DAT", "work/build/SCEN.en.DAT"),
        ("/L5/SCEN2.DAT", "work/build/SCEN2.en.DAT"),
        ("/L5/SYSTEM.BIN", "work/build/SYSTEM.BIN.en"),
    ):
        # No --allow-grow: relocation is unsafe on this disc (the free tail
        # region overlaps the CD audio tracks). Sizes must stay unchanged.
        run(scripts / "iso_mode2.py", str(work_bin), "inject", iso_path, local)

    out_ppf = Path(args.out_ppf)
    out_ppf.parent.mkdir(parents=True, exist_ok=True)
    records = write_ppf3(
        Path(args.orig_bin).read_bytes(),
        work_bin.read_bytes(),
        out_ppf,
        "Langrisser V EN (quiz PoC)",
    )
    print(f"ppf_records={records} out={out_ppf}")


if __name__ == "__main__":
    main()
