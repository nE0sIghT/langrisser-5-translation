#!/usr/bin/env python3
import argparse
import csv
import json
import struct
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def load_token_map(path: Path) -> Dict[int, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[int, str] = {}
    for k, v in raw.items():
        try:
            t = int(k, 16)
        except Exception:
            continue
        if isinstance(v, str) and v:
            out[t] = v[0]
    return out


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


def words_from_bytes(blob: bytes) -> List[int]:
    return [struct.unpack_from("<H", blob, i)[0] for i in range(0, len(blob) & ~1, 2)]


def find_best_local_table(chunk: bytes, min_entries: int = 24) -> Tuple[int, List[int]] | None:
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


def decode_words(words: Iterable[int], mp: Dict[int, str]) -> str:
    out: List[str] = []
    for w in words:
        if w in mp:
            out.append(mp[w])
        elif 0xFF00 <= w <= 0xFFFF:
            out.append("{" + f"{w:04X}" + "}")
        else:
            out.append("[" + f"{w:04X}" + "]")
    return "".join(out)


def text_ratio(words: List[int], mp: Dict[int, str]) -> float:
    if not words:
        return 0.0
    good = 0
    for w in words:
        if w in mp:
            good += 1
        elif w in (0x0005, 0x0006, 0x00CF, 0x00D1):
            good += 1
        elif w >= 0xFF00:
            good += 1
    return good / len(words)


def parse_scen_records(data: bytes) -> List[dict]:
    rows: List[dict] = []
    chunks = split_chunks(data)
    for cidx, (s, e) in enumerate(chunks):
        chunk = data[s:e]
        t = find_best_local_table(chunk, min_entries=24)
        if not t:
            continue
        tab_off, vals = t
        if vals and vals[0] == 0:
            tab_off += 2
            vals = vals[1:]
        for ridx in range(1, len(vals) - 1):
            a = tab_off + vals[ridx]
            b = tab_off + vals[ridx + 1]
            if not (0 <= a < b <= len(chunk)):
                continue
            rec = chunk[a:b]
            words = words_from_bytes(rec)
            if not words:
                continue
            rows.append(
                {
                    "chunk_index": cidx,
                    "record_index": ridx,
                    "chunk_rel_off": a,
                    "word_count": len(words),
                    "words": words,
                }
            )
    return rows


def extract_text_windows(words: List[int]) -> List[List[int]]:
    out: List[List[int]] = []
    i = 0
    while i < len(words):
        if words[i] == 0x0003:
            j = i + 1
            seg: List[int] = []
            while j < len(words) and words[j] not in (0x0004, 0xFFFC, 0xFFFD, 0xFFFE, 0xFB00):
                seg.append(words[j])
                j += 1
            if seg:
                out.append(seg)
            i = j + 1
            continue
        i += 1
    return out


def extract_ffff_runs(words: List[int], min_words: int, max_words: int) -> List[List[int]]:
    out: List[List[int]] = []
    start = 0
    for i, w in enumerate(words):
        if w != 0xFFFF:
            continue
        seg = words[start : i + 1]
        start = i + 1
        if min_words <= len(seg) <= max_words:
            out.append(seg)
    return out


def append_rows(
    out_rows: List[dict],
    src: str,
    section: str,
    anchor: str,
    kind: str,
    words: List[int],
    mp: Dict[int, str],
) -> None:
    out_rows.append(
        {
            "source_file": src,
            "section": section,
            "anchor": anchor,
            "kind": kind,
            "word_count": len(words),
            "text_ratio": f"{text_ratio(words, mp):.3f}",
            "decoded_partial": decode_words(words, mp),
            "words_hex": " ".join(f"{w:04X}" for w in words),
        }
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract all text-bearing token streams from Langrisser V data files.")
    ap.add_argument("--scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--scen2", default="work/extracted/SCEN2.DAT")
    ap.add_argument("--system", default="work/extracted/SYSTEM.BIN")
    ap.add_argument("--slps", default="work/extracted/SLPS_018.19")
    ap.add_argument("--token-map", default="scripts/lang5_token_map_manual.json")
    ap.add_argument("--out-csv", default="work/scen_analysis/all_texts.csv")
    ap.add_argument("--min-run-words", type=int, default=4)
    ap.add_argument("--max-run-words", type=int, default=96)
    ap.add_argument("--min-ratio", type=float, default=0.35)
    args = ap.parse_args()

    mp = load_token_map(Path(args.token_map))
    out_rows: List[dict] = []

    for src_path in [Path(args.scen), Path(args.scen2)]:
        data = src_path.read_bytes()
        for rec in parse_scen_records(data):
            section = f"chunk:{rec['chunk_index']}"
            anchor = f"rec:{rec['record_index']}@0x{rec['chunk_rel_off']:04X}"
            words = rec["words"]

            for seg in extract_text_windows(words):
                if text_ratio(seg, mp) >= args.min_ratio:
                    append_rows(out_rows, src_path.name, section, anchor, "scen_window_0003_0004", seg, mp)

            # Include short terminal records (names/labels/menu fragments).
            if words and words[-1] == 0xFFFF and args.min_run_words <= len(words) <= args.max_run_words:
                if text_ratio(words, mp) >= args.min_ratio:
                    append_rows(out_rows, src_path.name, section, anchor, "scen_record_ffff", words, mp)

    for src_path in [Path(args.system), Path(args.slps)]:
        data = src_path.read_bytes()
        words = words_from_bytes(data)
        runs = extract_ffff_runs(words, args.min_run_words, args.max_run_words)
        for i, seg in enumerate(runs, start=1):
            if text_ratio(seg, mp) < args.min_ratio:
                continue
            anchor = f"run:{i}"
            append_rows(out_rows, src_path.name, "global", anchor, "ffff_run", seg, mp)

    # Stable deterministic ordering.
    out_rows.sort(key=lambda r: (r["source_file"], r["section"], r["anchor"], r["kind"], r["words_hex"]))

    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "source_file",
                "section",
                "anchor",
                "kind",
                "word_count",
                "text_ratio",
                "decoded_partial",
                "words_hex",
            ],
        )
        w.writeheader()
        w.writerows(out_rows)

    print(f"wrote {out} ({len(out_rows)} rows)")


if __name__ == "__main__":
    main()
