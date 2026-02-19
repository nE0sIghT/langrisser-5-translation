#!/usr/bin/env python3
import argparse
import shutil
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build PPF from edited SCEN/SCEN2 script dumps.")
    ap.add_argument("--orig-bin", default="iso/SLPS-01818-9-B.bin")
    ap.add_argument("--scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--scen2", default="work/extracted/SCEN2.DAT")
    ap.add_argument("--dump-dir", default="work/scriptdump_en")
    ap.add_argument("--tbl", default="work/tables/lang5_en_insert.tbl")
    ap.add_argument("--work-bin", default="work/build/SLPS-01818-9-B.script.en.bin")
    ap.add_argument("--out-ppf", default="patches/langrisser_v_en_script_only.ppf")
    ap.add_argument("--max-size-mode", choices=["off", "original"], default="original")
    args = ap.parse_args()

    work_bin = Path(args.work_bin)
    work_bin.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.orig_bin, work_bin)

    out_scen = Path("work/build/SCEN.script.DAT")
    out_scen2 = Path("work/build/SCEN2.script.DAT")

    run(
        [
            "python3",
            "scripts/lang5_scrsceninsert.py",
            "--scen",
            args.scen,
            "--scen2",
            args.scen2,
            "--dump-dir",
            args.dump_dir,
            "--tbl",
            args.tbl,
            "--out-scen",
            str(out_scen),
            "--out-scen2",
            str(out_scen2),
            "--max-size-mode",
            args.max_size_mode,
        ]
    )

    run(["python3", "scripts/iso_mode2.py", str(work_bin), "inject", "/L5/SCEN.DAT", str(out_scen)])
    run(["python3", "scripts/iso_mode2.py", str(work_bin), "inject", "/L5/SCEN2.DAT", str(out_scen2)])

    Path(args.out_ppf).parent.mkdir(parents=True, exist_ok=True)
    run(["python3", "scripts/ppf3.py", args.orig_bin, str(work_bin), args.out_ppf])
    print(f"wrote {args.out_ppf}")


if __name__ == "__main__":
    main()
