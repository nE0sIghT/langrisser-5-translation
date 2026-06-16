#!/usr/bin/env python3
"""Dump SYSTEM.BIN help text (the triangle-button command help) to JSON.

Help strings are FFFF-terminated runs of 16-bit glyph codes at fixed offsets.
This emits one entry per run (offset, word budget, decoded JP, empty `en`) for
the editable translation file `data/translation/system_help.json`. The matching
inserter (`lang5_help_insert.py`) writes the English back at the same offsets,
within the same byte budget, so SYSTEM.BIN keeps its size.
"""
import argparse
import json
import struct
from pathlib import Path

FFFF = 0xFFFF


def load_codemap(tbl_path: str) -> dict[int, str]:
    codemap: dict[int, str] = {}
    for line in Path(tbl_path).read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if len(key) == 4:
            try:
                codemap[int(key, 16)] = value
            except ValueError:
                pass
    return codemap


def decode_run(words: list[int], codemap: dict[int, str]) -> str:
    out: list[str] = []
    for w in words:
        if w in (0x000A, 0xFFFC):
            out.append("\\n")
        elif w >= 0xFB00:
            out.append(f"{{{w:04X}}}")
        elif w == 0:
            out.append("")
        else:
            out.append(codemap.get(w, f"{{?{w:04X}}}"))
    return "".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--system-bin", default="work/extracted/SYSTEM.BIN")
    ap.add_argument("--tbl", default="data/tables/lang5_jp.tbl")
    ap.add_argument("--start", type=lambda x: int(x, 0), default=0x15BF6)
    ap.add_argument("--end", type=lambda x: int(x, 0), default=0x17990)
    ap.add_argument("--min-words", type=int, default=4)
    ap.add_argument("--out", default="data/translation/system_help.json")
    args = ap.parse_args()

    data = Path(args.system_bin).read_bytes()
    codemap = load_codemap(args.tbl)
    words = struct.unpack_from("<%dH" % (len(data) // 2), data, 0)

    entries = []
    i = args.start // 2
    end = args.end // 2
    cur = i
    while i < end:
        if words[i] == FFFF:
            if i - cur >= args.min_words:
                run = list(words[cur:i])
                entries.append({
                    "offset": f"0x{cur * 2:05X}",
                    "words": len(run),
                    "jp": decode_run(run, codemap),
                    "en": "",
                })
            cur = i + 1
        i += 1

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"dumped {len(entries)} help runs -> {args.out}")


if __name__ == "__main__":
    main()
