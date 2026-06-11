#!/usr/bin/env python3
"""Insert edited script dump back into SCEN.DAT/SCEN2.DAT.

Records are re-encoded and repacked inside the original text block of each
chunk: records may trade space with each other, but the block base, size,
record count and everything outside the block stay byte-identical. The
space after the last record is padded with zero words.
"""
import argparse
import re
from pathlib import Path

from lang5_scen import (
    Codec,
    find_text_block,
    load_charmap_csv,
    load_charmap_tbl,
    read_chunk_spans,
    words_to_bytes,
)

CHUNK_FILE_RE = re.compile(r"chunk_(\d+)\.txt$")


def parse_dump_file(path: Path) -> dict[int, str]:
    out: dict[int, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw or raw.startswith("#") or "\t" not in raw:
            continue
        idx, text = raw.split("\t", 1)
        if idx.strip().isdigit():
            out[int(idx.strip())] = text
    return out


def insert_file(src: Path, dump_root: Path, out_path: Path, codec: Codec) -> int:
    data = bytearray(src.read_bytes())
    changed = 0

    for cidx, (s, e) in enumerate(read_chunk_spans(bytes(data))):
        dump_path = dump_root / src.stem / f"chunk_{cidx:03d}.txt"
        if not dump_path.exists():
            continue
        edits = parse_dump_file(dump_path)
        if not edits:
            continue

        chunk = bytes(data[s:e])
        block = find_text_block(chunk)
        table_end = block.base + 2 + 2 * len(block.offsets)

        # Collect record payloads: edited ones re-encoded, others verbatim.
        payloads: list[bytes] = []
        for ridx in range(1, block.record_count + 1):
            a, b = block.record_span(ridx)
            if ridx in edits:
                payloads.append(words_to_bytes(codec.encode(edits[ridx])))
            else:
                payloads.append(chunk[a:b])

        body = b"".join(payloads)
        budget = block.size - (table_end - block.base)
        if len(body) > budget:
            raise SystemExit(
                f"{src.name} chunk {cidx}: text needs {len(body)} bytes, "
                f"block budget is {budget}. Shorten the text."
            )

        # Rebuild offsets and assemble the block at its original size.
        new_offsets = list(block.offsets)
        cur = table_end - block.base
        for i, payload in enumerate(payloads, start=1):
            new_offsets[i] = cur
            cur += len(payload)

        blob = bytearray(chunk[block.base : block.base + block.size])
        # blob[0:2] is block_size, offsets[i] lives at blob[2+2*i].
        for i, off in enumerate(new_offsets):
            if i == 0:
                continue
            blob[2 + 2 * i : 4 + 2 * i] = off.to_bytes(2, "little")
        pos = table_end - block.base
        blob[pos : pos + len(body)] = body
        blob[pos + len(body) : block.size] = b"\x00" * (block.size - pos - len(body))

        abs_base = s + block.base
        if bytes(blob) != bytes(data[abs_base : abs_base + block.size]):
            changed += 1
            data[abs_base : abs_base + block.size] = blob

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(data))
    print(f"{src.name}: chunks_changed={changed} -> {out_path}")
    return changed


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--scen2", default="work/extracted/SCEN2.DAT")
    ap.add_argument("--dump-dir", default="work/scriptdump")
    ap.add_argument("--charmap", default="data/font_mapping/groups_report.csv",
                    help="groups_report.csv or a HHHH=c .tbl file")
    ap.add_argument("--out-scen", default="work/build/SCEN.DAT")
    ap.add_argument("--out-scen2", default="work/build/SCEN2.DAT")
    args = ap.parse_args()

    charmap_path = Path(args.charmap)
    if charmap_path.suffix == ".tbl":
        codec = Codec(load_charmap_tbl(charmap_path))
    else:
        codec = Codec(load_charmap_csv(charmap_path))

    dump_root = Path(args.dump_dir)
    insert_file(Path(args.scen), dump_root, Path(args.out_scen), codec)
    insert_file(Path(args.scen2), dump_root, Path(args.out_scen2), codec)


if __name__ == "__main__":
    main()
