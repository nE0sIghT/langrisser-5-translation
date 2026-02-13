#!/usr/bin/env python3
import argparse
import shutil
from pathlib import Path

from iso_mode2 import inject_file, read_user_bytes, walk_iso
from ppf3 import write_ppf3


TITLE_JP = "ラングリッサー５".encode("shift_jis")
TITLE_EN = b"LANGRISSER V".ljust(len(TITLE_JP), b"\x00")


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
            raise RuntimeError("JP title string not found in executable.")
        tmp = bin_path.parent / "SLPS_018.19.patched"
        tmp.write_bytes(data)
        inject_file(fh, "/SLPS_018.19", str(tmp))
        tmp.unlink()
        return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a reproducible PPF patch for Langrisser V (PS1)."
    )
    parser.add_argument(
        "--source-bin",
        default="iso/SLPS-01818-9-B.bin",
        help="Original source BIN",
    )
    parser.add_argument(
        "--work-bin",
        default="work/build/SLPS-01818-9-B.en.bin",
        help="Path for modified BIN copy",
    )
    parser.add_argument(
        "--output-ppf",
        default="patches/langrisser_v_en.ppf",
        help="Output patch path",
    )
    args = parser.parse_args()

    src = Path(args.source_bin)
    work = Path(args.work_bin)
    out = Path(args.output_ppf)
    if not src.exists():
        raise FileNotFoundError(src)

    work.parent.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, work)

    replacements = patch_executable_title(work)
    records = write_ppf3(
        src.read_bytes(),
        work.read_bytes(),
        out,
        "Langrisser V EN alpha",
    )
    print(f"title replacements: {replacements}")
    print(f"ppf records: {records}")
    print(f"output: {out}")


if __name__ == "__main__":
    main()
