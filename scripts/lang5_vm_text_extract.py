#!/usr/bin/env python3
import argparse
import csv
import struct
from pathlib import Path
from typing import Dict, List, Set, Tuple

from lang5_textcodec import decode_words, load_tbl, load_token_map_json


def ru16(b: bytes, off: int) -> int:
    return struct.unpack_from("<H", b, off)[0]


def ru32(b: bytes, off: int) -> int:
    return struct.unpack_from("<I", b, off)[0]


def words_from_bytes(blob: bytes) -> List[int]:
    return [ru16(blob, i) for i in range(0, len(blob) & ~1, 2)]


def read_chunk_pointers(data: bytes) -> List[int]:
    pts: List[int] = []
    for off in range(0, 0x800, 4):
        if off + 4 > len(data):
            break
        v = ru32(data, off)
        if v == 0:
            break
        pts.append(v)
        if len(pts) > 1 and v <= pts[-2]:
            break
        if v == len(data):
            break
    return pts


def parse_u16_list(block: bytes, off: int, max_items: int = 2048) -> Tuple[List[int], bool]:
    vals: List[int] = []
    p = off
    for _ in range(max_items):
        if p + 2 > len(block):
            return (vals, False)
        v = ru16(block, p)
        p += 2
        if v == 0xFFFF:
            return (vals, True)
        vals.append(v)
    return (vals, False)


def read_entry_words(block: bytes, off: int, max_words: int = 512) -> List[int]:
    out: List[int] = []
    p = off
    for _ in range(max_words):
        if p + 2 > len(block):
            break
        w = ru16(block, p)
        out.append(w)
        p += 2
        if w == 0xFFFF:
            break
    return out


def extract_ff00_ids(words: List[int]) -> List[int]:
    out: List[int] = []
    for i in range(len(words) - 1):
        if words[i] == 0xFF00:
            out.append(words[i + 1])
    return out


def parse_text_section(chunk: bytes, vm_off: int, vm_size: int) -> Tuple[int, int, List[int], int]:
    sec_off = vm_off + vm_size
    if sec_off + 4 > len(chunk):
        return (-1, 0, [], -1)
    sec_size = ru32(chunk, sec_off)
    if sec_size < 0x20 or sec_off + sec_size > len(chunk):
        return (-1, 0, [], -1)

    # Observed layout:
    #   [u32 section_size]
    #   [u16 offsets list, starts at sec_off+2 with leading 0x0000]
    vals: List[int] = []
    prev = -1
    for off in range(sec_off + 2, sec_off + sec_size, 2):
        v = ru16(chunk, off)
        if v < prev or v >= sec_size:
            break
        vals.append(v)
        prev = v

    if len(vals) < 2:
        return (sec_off, sec_size, [], -1)

    data_base = sec_off + 2 + len(vals) * 2
    if data_base >= sec_off + sec_size:
        return (sec_off, sec_size, [], -1)
    return (sec_off, sec_size, vals, data_base)


def scan_one(src: Path, tok2txt: Dict[int, str], out_dir: Path) -> None:
    data = src.read_bytes()
    pts = read_chunk_pointers(data)
    if len(pts) < 2:
        raise RuntimeError(f"no chunks in {src}")

    rows_text = []
    rows_links = []

    for cidx in range(len(pts) - 1):
        c_start = pts[cidx]
        c_end = pts[cidx + 1]
        chunk = data[c_start:c_end]
        if len(chunk) < 0x80:
            continue

        vm_off = ru32(chunk, 0)
        if not (0x40 <= vm_off <= len(chunk) - 0x40):
            continue
        if ru32(chunk, vm_off) != 0x44:
            continue
        vm_size = ru32(chunk, vm_off + 0x3C)
        if vm_size < 0x40 or vm_off + vm_size > len(chunk):
            continue
        block = chunk[vm_off:vm_off + vm_size]

        main_ptr = ru32(block, 0x2C)
        entry_offs, ok = parse_u16_list(block, main_ptr)
        if not ok:
            entry_offs = []
        entry_offs = [e for e in entry_offs if (e & 1) == 0 and 0x40 <= e < vm_size]

        ff00_by_entry: Dict[int, List[int]] = {}
        referenced_ids: Set[int] = set()
        for eidx, eoff in enumerate(entry_offs):
            ws = read_entry_words(block, eoff, 256)
            ids = extract_ff00_ids(ws)
            ff00_by_entry[eidx] = ids
            for i in ids:
                referenced_ids.add(i)

        sec_off, sec_size, offsets, data_base = parse_text_section(chunk, vm_off, vm_size)
        if sec_off < 0 or data_base < 0:
            continue

        for tid in range(len(offsets) - 1):
            a = data_base + offsets[tid]
            b = data_base + offsets[tid + 1]
            if not (data_base <= a <= b <= sec_off + sec_size):
                continue
            ws = words_from_bytes(chunk[a:b])
            if not ws:
                continue
            rows_text.append(
                {
                    "source_file": src.name,
                    "chunk_index": cidx,
                    "chunk_start": f"0x{c_start:06X}",
                    "vm_off": f"0x{vm_off:04X}",
                    "vm_size": f"0x{vm_size:04X}",
                    "text_section_off": f"0x{sec_off:04X}",
                    "text_section_size": f"0x{sec_size:04X}",
                    "text_data_base": f"0x{data_base:04X}",
                    "text_id": tid,
                    "text_rel_off": f"0x{offsets[tid]:04X}",
                    "word_count": len(ws),
                    "referenced_by_vm_ff00": int(tid in referenced_ids),
                    "words_hex": " ".join(f"{w:04X}" for w in ws[:160]),
                    "decoded_preview": decode_words(ws[:160], tok2txt),
                }
            )

        for eidx, ids in ff00_by_entry.items():
            for tid in ids:
                preview = ""
                if 0 <= tid < len(offsets) - 1:
                    a = data_base + offsets[tid]
                    b = data_base + offsets[tid + 1]
                    if data_base <= a <= b <= sec_off + sec_size:
                        ws = words_from_bytes(chunk[a:b])
                        preview = decode_words(ws[:64], tok2txt)
                rows_links.append(
                    {
                        "source_file": src.name,
                        "chunk_index": cidx,
                        "entry_index": eidx,
                        "ff00_text_id": tid,
                        "has_text_record": int(bool(preview)),
                        "decoded_preview": preview,
                    }
                )

    out_dir.mkdir(parents=True, exist_ok=True)
    out_text = out_dir / f"{src.stem.lower()}_vm_texts.csv"
    out_links = out_dir / f"{src.stem.lower()}_vm_ff00_links.csv"

    with out_text.open("w", newline="", encoding="utf-8") as fh:
        cols = list(rows_text[0].keys()) if rows_text else [
            "source_file",
            "chunk_index",
            "chunk_start",
            "vm_off",
            "vm_size",
            "text_section_off",
            "text_section_size",
            "text_data_base",
            "text_id",
            "text_rel_off",
            "word_count",
            "referenced_by_vm_ff00",
            "words_hex",
            "decoded_preview",
        ]
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows_text)

    with out_links.open("w", newline="", encoding="utf-8") as fh:
        cols = list(rows_links[0].keys()) if rows_links else [
            "source_file",
            "chunk_index",
            "entry_index",
            "ff00_text_id",
            "has_text_record",
            "decoded_preview",
        ]
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows_links)

    print(f"wrote {out_text}")
    print(f"wrote {out_links}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract text sections attached to VM blocks and link FF00 ids to records.")
    ap.add_argument("--scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--scen2", default="work/extracted/SCEN2.DAT")
    ap.add_argument("--tbl", default="work/tables/lang5_merged.tbl")
    ap.add_argument("--token-map", default="scripts/lang5_token_map_manual.json")
    ap.add_argument("--out-dir", default="work/scen_analysis")
    args = ap.parse_args()

    tbl_path = Path(args.tbl)
    if tbl_path.exists():
        tok2txt = load_tbl(tbl_path)
    else:
        tok2txt = load_token_map_json(Path(args.token_map))

    out_dir = Path(args.out_dir)
    scan_one(Path(args.scen), tok2txt, out_dir)
    scan_one(Path(args.scen2), tok2txt, out_dir)


if __name__ == "__main__":
    main()
