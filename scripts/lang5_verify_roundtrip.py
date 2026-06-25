#!/usr/bin/env python3
"""Round-trip integrity test for the SCEN dump/insert toolchain.

Check 1 (codec): every record decoded from the source files re-encodes to
the exact original bytes.
Check 2 (pipeline): dumping to a temp dir and inserting without edits
produces byte-identical SCEN.DAT/SCEN2.DAT.

Exits non-zero on any mismatch.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from lang5_scen import (
    Codec,
    find_text_block,
    load_charmap_csv,
    read_chunk_spans,
    words_from_bytes,
    words_to_bytes,
)
from lang5_project import COMMON_FONT_MAP


def check_codec(src: Path, codec: Codec) -> int:
    data = src.read_bytes()
    bad = 0
    for cidx, (s, e) in enumerate(read_chunk_spans(data)):
        chunk = data[s:e]
        block = find_text_block(chunk)
        for ridx in range(1, block.record_count + 1):
            a, b = block.record_span(ridx)
            original = chunk[a:b]
            text = codec.decode(words_from_bytes(original))
            if words_to_bytes(codec.encode(text)) != original:
                print(f"codec mismatch: {src.name} chunk={cidx} record={ridx}")
                bad += 1
    return bad


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--scen2", default="work/extracted/SCEN2.DAT")
    ap.add_argument("--charmap", default=str(COMMON_FONT_MAP))
    args = ap.parse_args()

    codec = Codec(load_charmap_csv(Path(args.charmap)))
    failures = 0

    for src in (Path(args.scen), Path(args.scen2)):
        bad = check_codec(src, codec)
        print(f"codec round-trip {src.name}: {'OK' if not bad else f'{bad} mismatches'}")
        failures += bad

    scripts = Path(__file__).parent
    with tempfile.TemporaryDirectory(prefix="l5_roundtrip_") as tmp:
        dump_dir = Path(tmp) / "dump"
        build_dir = Path(tmp) / "build"
        run = lambda *cmd: subprocess.run([sys.executable, *cmd], check=True)
        run(scripts / "lang5_scendump.py", "--scen", args.scen, "--scen2", args.scen2,
            "--charmap", args.charmap, "--out-dir", str(dump_dir))
        run(scripts / "lang5_sceninsert.py", "--scen", args.scen, "--scen2", args.scen2,
            "--charmap", args.charmap, "--dump-dir", str(dump_dir),
            "--out-scen", str(build_dir / "SCEN.DAT"),
            "--out-scen2", str(build_dir / "SCEN2.DAT"))
        for src, out in ((Path(args.scen), build_dir / "SCEN.DAT"),
                         (Path(args.scen2), build_dir / "SCEN2.DAT")):
            same = src.read_bytes() == out.read_bytes()
            print(f"pipeline round-trip {src.name}: {'OK' if same else 'MISMATCH'}")
            if not same:
                failures += 1

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
