#!/usr/bin/env python3
import argparse
import struct
from pathlib import Path
from typing import Dict, List, Tuple

from lang5_textcodec import encode_text, load_tbl


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


def parse_dump_file(path: Path) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = raw.rstrip("\n")
        if not s or s.startswith("#"):
            continue
        if "\t" not in s:
            continue
        a, b = s.split("\t", 1)
        try:
            ridx = int(a.strip())
        except Exception:
            continue
        out[ridx] = b
    return out


def pack_u16_words(words: List[int]) -> bytes:
    out = bytearray()
    for w in words:
        out += struct.pack("<H", w & 0xFFFF)
    return bytes(out)


def rebuild_container(chunks: List[bytes], base_header: bytes, align_chunks: int = 0x800) -> bytes:
    hdr = bytearray(base_header)
    if len(hdr) < 0x800:
        hdr.extend(b"\x00" * (0x800 - len(hdr)))
    cur = 0x800
    ptrs: List[int] = []
    blobs: List[bytes] = []
    for ch in chunks:
        if align_chunks > 0 and cur % align_chunks != 0:
            pad = align_chunks - (cur % align_chunks)
            blobs.append(b"\x00" * pad)
            cur += pad
        ptrs.append(cur)
        blobs.append(ch)
        cur += len(ch)
    if align_chunks > 0 and cur % align_chunks != 0:
        pad = align_chunks - (cur % align_chunks)
        blobs.append(b"\x00" * pad)
        cur += pad
    ptrs.append(cur)
    for i, p in enumerate(ptrs):
        struct.pack_into("<I", hdr, i * 4, p)
    return bytes(hdr[:0x800]) + b"".join(blobs)


def insert_one(
    src: Path,
    dump_root: Path,
    out_path: Path,
    tok2txt: Dict[int, str],
    align_chunks: int,
    max_size: int,
) -> None:
    data = src.read_bytes()
    chunks_idx = split_chunks(data)
    chunks = [data[s:e] for s, e in chunks_idx]
    changed = 0

    base = dump_root / src.stem
    for cidx, chunk in enumerate(chunks):
        txt_path = base / f"chunk_{cidx:03d}.txt"
        if not txt_path.exists():
            continue
        edits = parse_dump_file(txt_path)
        if not edits:
            continue
        t = detect_table(chunk)
        if not t:
            continue
        tab_off, vals = t
        rec_start_idx = 1 if vals and vals[0] == 0 else 0
        if len(vals) < rec_start_idx + 2:
            continue

        new_records: List[bytes] = []
        for ridx in range(rec_start_idx, len(vals) - 1):
            a = tab_off + vals[ridx]
            b = tab_off + vals[ridx + 1]
            if not (0 <= a < b <= len(chunk)):
                new_records.append(chunk[a:b] if 0 <= a < len(chunk) and 0 <= b <= len(chunk) else b"")
                continue
            if ridx in edits:
                words = encode_text(edits[ridx], tok2txt)
                rec_bytes = pack_u16_words(words)
                new_records.append(rec_bytes)
                if rec_bytes != chunk[a:b]:
                    changed += 1
            else:
                new_records.append(chunk[a:b])

        # rebuild offsets for rec_start_idx..end
        new_vals = list(vals)
        cur = vals[rec_start_idx]
        for i, rec_bytes in enumerate(new_records, start=rec_start_idx):
            new_vals[i] = cur
            cur += len(rec_bytes)
        new_vals[len(vals) - 1] = cur

        table_bytes = bytearray()
        for v in new_vals:
            table_bytes += struct.pack("<H", v & 0xFFFF)
        old_table_bytes = chunk[tab_off : tab_off + 2 * len(vals)]
        if len(old_table_bytes) != len(table_bytes):
            raise RuntimeError(f"chunk {cidx}: table size mismatch")

        data_start_old = tab_off + vals[rec_start_idx]
        data_end_old = tab_off + vals[-1]
        if not (0 <= data_start_old <= data_end_old <= len(chunk)):
            raise RuntimeError(f"chunk {cidx}: invalid data range")

        prefix = chunk[:tab_off]
        middle = chunk[tab_off + 2 * len(vals) : data_start_old]
        suffix = chunk[data_end_old:]
        new_chunk = prefix + bytes(table_bytes) + middle + b"".join(new_records) + suffix
        chunks[cidx] = new_chunk

    rebuilt = rebuild_container(chunks, data[:0x800], align_chunks=align_chunks)
    if max_size > 0 and len(rebuilt) > max_size:
        raise RuntimeError(
            f"{src.name}: rebuilt size {len(rebuilt)} exceeds max_size {max_size}. "
            "Reduce edits or token lengths."
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(rebuilt)
    print(f"wrote {out_path} changed_records={changed}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Insert edited text dump back into SCEN/SCEN2 and rebuild containers.")
    ap.add_argument("--scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--scen2", default="work/extracted/SCEN2.DAT")
    ap.add_argument("--dump-dir", default="work/scriptdump")
    ap.add_argument("--tbl", default="work/tables/lang5.tbl")
    ap.add_argument("--out-scen", default="work/build/SCEN.DAT")
    ap.add_argument("--out-scen2", default="work/build/SCEN2.DAT")
    ap.add_argument("--align-chunks", type=int, default=0x800, help="Chunk alignment for rebuilt container.")
    ap.add_argument(
        "--max-size-mode",
        choices=["off", "original"],
        default="original",
        help="Size guard for rebuilt file.",
    )
    args = ap.parse_args()

    tok2txt = load_tbl(Path(args.tbl))
    if not tok2txt:
        raise SystemExit(f"empty or missing table: {args.tbl}")

    dump_root = Path(args.dump_dir)
    scen_src = Path(args.scen)
    scen2_src = Path(args.scen2)
    scen_max = scen_src.stat().st_size if args.max_size_mode == "original" else 0
    scen2_max = scen2_src.stat().st_size if args.max_size_mode == "original" else 0

    insert_one(scen_src, dump_root, Path(args.out_scen), tok2txt, args.align_chunks, scen_max)
    insert_one(scen2_src, dump_root, Path(args.out_scen2), tok2txt, args.align_chunks, scen2_max)


if __name__ == "__main__":
    main()
