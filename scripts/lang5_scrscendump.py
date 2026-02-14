#!/usr/bin/env python3
import argparse
import struct
from pathlib import Path
from typing import Dict, List, Tuple

from lang5_textcodec import decode_words, load_tbl, load_token_map_json, save_tbl


def read_chunk_pointers(data: bytes) -> List[int]:
    pts: List[int] = []
    for off in range(0, len(data), 4):
        if off + 4 > len(data):
            break
        v = struct.unpack_from("<I", data, off)[0]
        pts.append(v)
        if v == len(data):
            break
    return pts


def split_chunks(data: bytes) -> List[Tuple[int, int]]:
    pts = read_chunk_pointers(data)
    return [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]


def detect_table(chunk: bytes, min_entries: int = 24) -> Tuple[int, List[int]] | None:
    best: Tuple[int, List[int]] | None = None
    n = len(chunk)
    for start in range(0, n - 6, 2):
        vals: List[int] = []
        prev = -1
        i = start
        limit = n - start
        while i + 1 < n:
            v = chunk[i] | (chunk[i + 1] << 8)
            if v <= prev or v >= limit:
                break
            vals.append(v)
            prev = v
            i += 2
        if len(vals) >= min_entries:
            if best is None or len(vals) > len(best[1]):
                best = (start, vals)
    return best


def words_from_bytes(blob: bytes) -> List[int]:
    return [struct.unpack_from("<H", blob, i)[0] for i in range(0, len(blob) & ~1, 2)]


def dump_one(src: Path, out_dir: Path, tok2txt: Dict[int, str]) -> None:
    data = src.read_bytes()
    chunks = split_chunks(data)
    root = out_dir / src.stem
    root.mkdir(parents=True, exist_ok=True)

    for cidx, (s, e) in enumerate(chunks):
        chunk = data[s:e]
        t = detect_table(chunk)
        if not t:
            continue
        tab_off, vals = t
        rec_start_idx = 1 if vals and vals[0] == 0 else 0
        if len(vals) < rec_start_idx + 2:
            continue

        lines: List[str] = []
        lines.append(f"# chunk={cidx} file={src.name} start=0x{s:06X} end=0x{e:06X}")
        lines.append(f"# table_off=0x{tab_off:04X} entries={len(vals)} rec_start_idx={rec_start_idx}")
        lines.append("# format: rec_index<TAB>text")

        for ridx in range(rec_start_idx, len(vals) - 1):
            a = tab_off + vals[ridx]
            b = tab_off + vals[ridx + 1]
            if not (0 <= a < b <= len(chunk)):
                continue
            words = words_from_bytes(chunk[a:b])
            text = decode_words(words, tok2txt)
            lines.append(f"{ridx}\t{text}")

        (root / f"chunk_{cidx:03d}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Dump Langrisser V SCEN/SCEN2 records to editable text files.")
    ap.add_argument("--scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--scen2", default="work/extracted/SCEN2.DAT")
    ap.add_argument("--tbl", default="work/tables/lang5.tbl")
    ap.add_argument("--token-map", default="scripts/lang5_token_map_manual.json")
    ap.add_argument("--out-dir", default="work/scriptdump")
    args = ap.parse_args()

    tbl_path = Path(args.tbl)
    if tbl_path.exists():
        tok2txt = load_tbl(tbl_path)
    else:
        tok2txt = load_token_map_json(Path(args.token_map))
        tbl_path.parent.mkdir(parents=True, exist_ok=True)
        save_tbl(tbl_path, tok2txt)

    out_dir = Path(args.out_dir)
    dump_one(Path(args.scen), out_dir, tok2txt)
    dump_one(Path(args.scen2), out_dir, tok2txt)
    print(f"wrote dump to {out_dir}")
    print(f"table: {tbl_path}")


if __name__ == "__main__":
    main()
