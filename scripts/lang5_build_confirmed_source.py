#!/usr/bin/env python3
import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


def load_tbl(path: Path) -> Dict[int, str]:
    mp: Dict[int, str] = {}
    if not path.exists():
        return mp
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = raw.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        try:
            mp[int(k, 16)] = v.strip()
        except Exception:
            continue
    return mp


def decode_words(words_hex: str, tbl: Dict[int, str]) -> str:
    out: List[str] = []
    for tok_s in words_hex.split():
        try:
            t = int(tok_s, 16)
        except Exception:
            continue
        out.append(tbl.get(t, f"<${t:04X}>"))
    return "".join(out)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build confirmed tokenized source dump from VM FF00 links (static data only)."
    )
    p.add_argument("--vm-texts", default="work/scen_analysis/scen_vm_texts.csv")
    p.add_argument("--vm-links", default="work/scen_analysis/scen_vm_ff00_links.csv")
    p.add_argument("--tbl", default="work/tables/lang5_merged.tbl")
    p.add_argument("--out-csv", default="work/scen_analysis/confirmed_source_tokenized.csv")
    p.add_argument("--out-txt", default="work/scen_analysis/confirmed_source_tokenized.txt")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    tbl = load_tbl(Path(args.tbl))

    texts_by_key: Dict[Tuple[int, int], dict] = {}
    with Path(args.vm_texts).open(encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            if row.get("source_file") != "SCEN.DAT":
                continue
            key = (int(row["chunk_index"]), int(row["text_id"]))
            texts_by_key[key] = row

    # Keep first occurrence of each (chunk, text_id) in VM call order.
    ordered_keys: List[Tuple[int, int, int, int]] = []
    seen = set()
    with Path(args.vm_links).open(encoding="utf-8", errors="ignore") as f:
        for row in csv.DictReader(f):
            if row.get("source_file") != "SCEN.DAT":
                continue
            chunk = int(row["chunk_index"])
            entry = int(row["entry_index"])
            tid = int(row["ff00_text_id"])
            k = (chunk, tid)
            if k in seen:
                continue
            seen.add(k)
            ordered_keys.append((chunk, entry, tid, len(ordered_keys)))

    # Group by chunk for readability.
    by_chunk: Dict[int, List[Tuple[int, int, int, int]]] = defaultdict(list)
    for rec in ordered_keys:
        by_chunk[rec[0]].append(rec)

    out_csv = Path(args.out_csv)
    out_txt = Path(args.out_txt)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    with out_csv.open("w", encoding="utf-8", newline="") as f_csv, out_txt.open(
        "w", encoding="utf-8"
    ) as f_txt:
        w = csv.writer(f_csv)
        w.writerow(
            [
                "seq",
                "chunk_index",
                "entry_index",
                "text_id",
                "words_hex",
                "decoded_preview",
            ]
        )
        for chunk in sorted(by_chunk):
            f_txt.write(f"## chunk {chunk}\n")
            for chunk_i, entry_i, text_id, seq in by_chunk[chunk]:
                trow = texts_by_key.get((chunk_i, text_id))
                if not trow:
                    continue
                words_hex = trow["words_hex"]
                dec = decode_words(words_hex, tbl)
                w.writerow([seq, chunk_i, entry_i, text_id, words_hex, dec])
                f_txt.write(
                    f"[{seq:05d}] chunk={chunk_i:03d} entry={entry_i:04d} text_id={text_id:04X} :: {dec}\n"
                )
            f_txt.write("\n")

    print(f"wrote {out_csv}")
    print(f"wrote {out_txt}")


if __name__ == "__main__":
    main()
