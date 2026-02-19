#!/usr/bin/env python3
import argparse
import shutil
import subprocess
from pathlib import Path

from iso_mode2 import inject_file, read_user_bytes, walk_iso
from ppf3 import write_ppf3


TITLE_JP = "ラングリッサー５".encode("shift_jis")
TITLE_EN = b"LANGRISSER V".ljust(len(TITLE_JP), b"\x00")


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def patch_executable_title(bin_path: Path) -> int:
    with open(bin_path, "rb+") as fh:
        entries = walk_iso(fh)
        exe = next((e for e in entries if e.path == "/SLPS_018.19"), None)
        if exe is None:
            raise RuntimeError("Could not find /SLPS_018.19 in image.")
        data = bytearray(read_user_bytes(fh, exe.extent_lba, exe.size))
        count = 0
        cursor = 0
        while True:
            pos = data.find(TITLE_JP, cursor)
            if pos < 0:
                break
            data[pos : pos + len(TITLE_JP)] = TITLE_EN
            cursor = pos + len(TITLE_JP)
            count += 1
        if count == 0:
            return 0
        tmp = bin_path.parent / "SLPS_018.19.patched"
        tmp.write_bytes(data)
        inject_file(fh, "/SLPS_018.19", str(tmp))
        tmp.unlink()
        return count


def main() -> None:
    ap = argparse.ArgumentParser(description="Build canonical full Langrisser V EN PPF (script+font+menu).")
    ap.add_argument("--orig-bin", default="iso/SLPS-01818-9-B.bin")
    ap.add_argument("--scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--scen2", default="work/extracted/SCEN2.DAT")
    ap.add_argument("--system", default="work/extracted/SYSTEM.BIN")
    ap.add_argument("--groups-report", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--jp-tbl", default="data/tables/lang5_jp.tbl")
    ap.add_argument("--full-records", default="data/translation/jp_en_full_records.json")
    ap.add_argument("--manual-overrides", default="data/translation/manual_record_overrides.json")
    ap.add_argument("--menu-map", default="data/translation/system_menu_map.json")
    ap.add_argument("--src-dump", default="work/scriptdump_groups")
    ap.add_argument("--out-dump", default="work/scriptdump_en")
    ap.add_argument("--out-tbl", default="work/tables/lang5_en_insert.tbl")
    ap.add_argument("--work-bin", default="work/build/SLPS-01818-9-B.en.full.bin")
    ap.add_argument("--out-ppf", default="patches/langrisser_v_en.ppf")
    args = ap.parse_args()

    work_bin = Path(args.work_bin)
    work_bin.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.orig_bin, work_bin)

    run(
        [
            "python3",
            "scripts/lang5_build_en_dump_full.py",
            "--src-dump",
            args.src_dump,
            "--tbl",
            args.jp_tbl,
            "--full-records",
            args.full_records,
            "--manual-overrides",
            args.manual_overrides,
            "--out-dump",
            args.out_dump,
            "--out-tbl",
            args.out_tbl,
        ]
    )

    run(
        [
            "python3",
            "scripts/lang5_scrsceninsert.py",
            "--scen",
            args.scen,
            "--scen2",
            args.scen2,
            "--dump-dir",
            args.out_dump,
            "--tbl",
            args.out_tbl,
            "--out-scen",
            "work/build/SCEN.script.DAT",
            "--out-scen2",
            "work/build/SCEN2.script.DAT",
            "--max-size-mode",
            "original",
        ]
    )

    run(["python3", "scripts/iso_mode2.py", str(work_bin), "inject", "/L5/SCEN.DAT", "work/build/SCEN.script.DAT"])
    run(["python3", "scripts/iso_mode2.py", str(work_bin), "inject", "/L5/SCEN2.DAT", "work/build/SCEN2.script.DAT"])

    run(
        [
            "python3",
            "scripts/lang5_patch_system_menu.py",
            "--system-in",
            args.system,
            "--system-out",
            "work/build/SYSTEM.BIN.en",
            "--groups-report",
            args.groups_report,
            "--tbl",
            args.out_tbl,
            "--menu-map",
            args.menu_map,
            "--report-csv",
            "work/scen_analysis/system_menu_occurrences.csv",
        ]
    )
    run(["python3", "scripts/iso_mode2.py", str(work_bin), "inject", "/L5/SYSTEM.BIN", "work/build/SYSTEM.BIN.en"])

    title_repl = patch_executable_title(work_bin)

    out_ppf = Path(args.out_ppf)
    out_ppf.parent.mkdir(parents=True, exist_ok=True)
    records = write_ppf3(
        Path(args.orig_bin).read_bytes(),
        work_bin.read_bytes(),
        out_ppf,
        "Langrisser V EN script+font",
    )
    print(f"title replacements: {title_repl}")
    print(f"ppf records: {records}")
    print(f"output: {out_ppf}")


if __name__ == "__main__":
    main()
