#!/usr/bin/env python3
import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

REC_RE = re.compile(r"^(?P<rec>\d+)\t(?P<txt>.*)$")


def load_alignment_map(path: Path) -> Dict[Tuple[int, int], Dict]:
    out: Dict[Tuple[int, int], Dict] = {}
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        for row in csv.DictReader(fh):
            c = (row.get("chunk_index") or "").strip()
            r = (row.get("jp_record_index") or "").strip()
            if not c or not r:
                continue
            try:
                key = (int(c), int(r))
            except ValueError:
                continue
            out[key] = {
                "scenario": (row.get("scenario") or "").strip(),
                "seq": int((row.get("seq") or "0").strip() or 0),
                "en_line": (row.get("en_line") or "").strip(),
                "jp_tokenized": (row.get("jp_tokenized") or "").strip(),
                "jp_partially_decoded": (row.get("jp_partially_decoded") or "").strip(),
            }
    return out


def parse_chunk_file(path: Path) -> List[Tuple[int, str]]:
    rows: List[Tuple[int, str]] = []
    for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not ln or ln.startswith("#"):
            continue
        m = REC_RE.match(ln)
        if not m:
            continue
        rows.append((int(m.group("rec")), m.group("txt")))
    return rows


def build_records(src_root: Path, align: Dict[Tuple[int, int], Dict]) -> Dict:
    records: List[Dict] = []
    by_key: Dict[str, Dict] = {}
    stats = {
        "total_records": 0,
        "with_en_line": 0,
        "without_en_line": 0,
        "sources": defaultdict(int),
        "chunks": defaultdict(int),
    }

    for source_dir in ("SCEN", "SCEN2"):
        base = src_root / source_dir
        if not base.exists():
            continue
        for chunk_file in sorted(base.glob("chunk_*.txt")):
            try:
                chunk_idx = int(chunk_file.stem.split("_")[1])
            except Exception:
                continue
            for rec_idx, jp_text in parse_chunk_file(chunk_file):
                a = align.get((chunk_idx, rec_idx), {})
                key = f"{source_dir}:{chunk_idx:03d}:{rec_idx:04d}"
                obj = {
                    "key": key,
                    "source_file": f"{source_dir}.DAT",
                    "chunk_index": chunk_idx,
                    "record_index": rec_idx,
                    "jp_text": jp_text,
                    "scenario": a.get("scenario", ""),
                    "seq": a.get("seq", 0),
                    "en_line": a.get("en_line", ""),
                    "jp_tokenized_alignment": a.get("jp_tokenized", ""),
                    "jp_partially_decoded_alignment": a.get("jp_partially_decoded", ""),
                }
                records.append(obj)
                by_key[key] = obj
                stats["total_records"] += 1
                stats["sources"][source_dir] += 1
                stats["chunks"][f"{source_dir}:{chunk_idx:03d}"] += 1
                if obj["en_line"]:
                    stats["with_en_line"] += 1
                else:
                    stats["without_en_line"] += 1

    return {
        "meta": {
            "total_records": stats["total_records"],
            "with_en_line": stats["with_en_line"],
            "without_en_line": stats["without_en_line"],
            "sources": dict(stats["sources"]),
            "chunk_count": len(stats["chunks"]),
            "note": "All records from scriptdump_groups are included; no logical filtering.",
        },
        "by_key": dict(sorted(by_key.items(), key=lambda x: x[0])),
        "records": records,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build full JP/EN record mapping JSON from all chunk dumps.")
    ap.add_argument("--scriptdump-root", default="work/scriptdump_groups")
    ap.add_argument("--alignment", default="work/scen_analysis/story_alignment_partial_decode.csv")
    ap.add_argument("--out", default="data/translation/jp_en_full_records.json")
    args = ap.parse_args()

    align = load_alignment_map(Path(args.alignment))
    obj = build_records(Path(args.scriptdump_root), align)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    print(json.dumps(obj["meta"], ensure_ascii=False))


if __name__ == "__main__":
    main()
