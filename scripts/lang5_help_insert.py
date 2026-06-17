#!/usr/bin/env python3
"""Insert translated SYSTEM.BIN help text from data/translation/system_help.json.

Each entry's English is encoded with the EN glyph table and written back at the
entry's fixed offset, terminated and padded with 0xFFFF inside the original
run's word budget, so SYSTEM.BIN keeps its size. Entries with an empty `en` are
left as the original Japanese. Over-budget or unencodable entries are reported
and skipped (the build should keep this list empty).
"""
import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lang5_scen import Codec, load_charmap_tbl

FFFF = 0xFFFF


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--system-in", default="work/build/SYSTEM.BIN.en")
    ap.add_argument("--system-out", default="work/build/SYSTEM.BIN.en")
    ap.add_argument("--help-json", action="append", default=None,
                    help="Translation JSON (repeatable).")
    ap.add_argument("--tbl", default="work/tables/lang5_en.tbl")
    ap.add_argument("--strict", action="store_true",
                    help="Exit non-zero if any entry is over budget or unencodable.")
    args = ap.parse_args()

    codec = Codec(load_charmap_tbl(Path(args.tbl)))
    data = bytearray(Path(args.system_in).read_bytes())
    json_paths = args.help_json or ["data/translation/system_help.json"]
    entries = []
    for jp in json_paths:
        entries.extend(json.loads(Path(jp).read_text(encoding="utf-8")))

    inserted = 0
    problems = []
    for e in entries:
        en = e.get("en", "").strip()
        if not en:
            continue
        off = int(e["offset"], 16)
        budget = int(e["words"])
        try:
            toks = codec.encode(en)
        except Exception as exc:  # unencodable character
            problems.append(f"{e['offset']}: unencodable ({exc}) :: {en!r}")
            continue
        if len(toks) > budget:
            problems.append(f"{e['offset']}: over budget {len(toks)}>{budget} :: {en!r}")
            continue
        words = toks + [FFFF] * (budget - len(toks))
        struct.pack_into("<%dH" % budget, data, off, *words)
        inserted += 1

    Path(args.system_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.system_out).write_bytes(data)
    print(f"inserted {inserted} help strings -> {args.system_out}")
    for p in problems:
        print("  PROBLEM", p)
    if problems and args.strict:
        sys.exit(1)


if __name__ == "__main__":
    main()
