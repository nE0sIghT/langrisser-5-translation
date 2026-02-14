#!/usr/bin/env python3
import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

HEX4 = re.compile(r"^[0-9A-Fa-f]{4}$")


def parse_words(s: str) -> List[int]:
    return [int(x, 16) for x in (s or "").split() if HEX4.match(x)]


def best_overlap(a: List[int], b: List[int]) -> int:
    best = 0
    for i in range(len(a)):
        for j in range(len(b)):
            n = 0
            while i + n < len(a) and j + n < len(b) and a[i + n] == b[j + n]:
                n += 1
            if n > best:
                best = n
    return best


def main() -> None:
    ap = argparse.ArgumentParser(description="Match runtime token windows to SCEN records.")
    ap.add_argument("--windows", default="work/scen_analysis/runtime_state_segments_windows.csv")
    ap.add_argument("--records", default="work/scen_analysis/records.csv")
    ap.add_argument("--out-csv", default="work/scen_analysis/runtime_record_matches.csv")
    ap.add_argument("--min-window-words", type=int, default=7)
    ap.add_argument("--min-overlap", type=int, default=7)
    ap.add_argument("--top-k", type=int, default=3)
    args = ap.parse_args()

    recs: List[Tuple[int, int, List[int]]] = []
    with Path(args.records).open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            w = parse_words(r.get("words_hex", ""))
            if w:
                recs.append((int(r["chunk_index"]), int(r["record_index"]), w))

    tri = defaultdict(list)
    for cidx, ridx, w in recs:
        for i in range(len(w) - 2):
            tri[(w[i], w[i + 1], w[i + 2])].append((cidx, ridx, w))

    out_rows: List[dict] = []
    with Path(args.windows).open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            ww = parse_words(r.get("words_hex", ""))
            if len(ww) < args.min_window_words:
                continue
            trigrams = [
                (ww[i], ww[i + 1], ww[i + 2])
                for i in range(len(ww) - 2)
                if sum(1 for x in ww[i : i + 3] if x >= 0xFF00) <= 1
            ]
            if not trigrams:
                continue
            key = min(trigrams, key=lambda t: len(tri.get(t, [])))
            matches = []
            for cidx, ridx, rw in tri.get(key, []):
                ov = best_overlap(ww, rw)
                if ov >= args.min_overlap:
                    matches.append((ov, cidx, ridx))
            if not matches:
                continue
            matches = sorted(set(matches), reverse=True)[: args.top_k]
            for rank, (ov, cidx, ridx) in enumerate(matches, start=1):
                out_rows.append(
                    {
                        "state_file": r.get("state_file", ""),
                        "stop_index": r.get("stop_index", ""),
                        "segment_index": r.get("segment_index", ""),
                        "contains_current_ptr": r.get("contains_current_ptr", ""),
                        "window_words": len(ww),
                        "overlap_words": ov,
                        "chunk_index": cidx,
                        "record_index": ridx,
                        "match_rank": rank,
                        "decoded_manual": r.get("decoded_manual", ""),
                        "window_words_hex": r.get("words_hex", ""),
                    }
                )

    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "state_file",
                "stop_index",
                "segment_index",
                "contains_current_ptr",
                "window_words",
                "overlap_words",
                "chunk_index",
                "record_index",
                "match_rank",
                "decoded_manual",
                "window_words_hex",
            ],
        )
        w.writeheader()
        w.writerows(out_rows)
    print(f"wrote {out} ({len(out_rows)} rows)")


if __name__ == "__main__":
    main()
