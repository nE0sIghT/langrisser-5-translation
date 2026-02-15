#!/usr/bin/env python3
import argparse
import csv
import struct
from pathlib import Path
from typing import Dict, List, Tuple


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


def load_map_from_groups_report(path: Path, allowed_groups: set[str]) -> Dict[int, str]:
    out: Dict[int, str] = {}
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            grp = (row.get("group") or "").strip()
            if grp not in allowed_groups:
                continue
            try:
                idx = int(row["index_dec"])
            except Exception:
                continue
            ch = (row.get("char") or "").strip()
            if ch:
                out[idx] = ch
    return out


def decode_words(words: List[int], token_to_char: Dict[int, str]) -> Tuple[str, int]:
    out: List[str] = []
    unknown = 0
    for w in words:
        ch = token_to_char.get(w, "")
        if ch:
            out.append(ch)
        else:
            out.append(f"<${w:04X}>")
            unknown += 1
    return "".join(out), unknown


def export_one(
    src: Path,
    prefix: str,
    out_scripts_dir: Path,
    token_to_char: Dict[int, str],
    text_encoding: str,
) -> List[Dict[str, str]]:
    data = src.read_bytes()
    chunks = split_chunks(data)
    rows: List[Dict[str, str]] = []

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
        lines.append(f"Langrisser V dumper [{s:#x} to {e:#x}]")
        lines.append("")

        rec_count = 0
        for ridx in range(rec_start_idx, len(vals) - 1):
            a = tab_off + vals[ridx]
            b = tab_off + vals[ridx + 1]
            if not (0 <= a < b <= len(chunk)):
                continue
            words = words_from_bytes(chunk[a:b])
            text, unknown = decode_words(words, token_to_char)
            lines.append(text)
            rec_count += 1
            rows.append(
                {
                    "source_file": src.name,
                    "chunk_index": str(cidx),
                    "record_index": str(ridx),
                    "word_count": str(len(words)),
                    "unknown_token_count": str(unknown),
                    "text": text,
                }
            )

        out_name = f"{prefix}{cidx}.sjs"
        out_path = out_scripts_dir / out_name
        out_path.write_bytes(("\n".join(lines) + "\n").encode(text_encoding, errors="replace"))
        if rec_count == 0:
            out_path.unlink(missing_ok=True)

    return rows


def write_tbl(out_tbl: Path, token_to_char: Dict[int, str], text_encoding: str) -> None:
    lines = []
    for tok in sorted(token_to_char):
        lines.append(f"{tok:04X}={token_to_char[tok]}")
    out_tbl.write_text("\n".join(lines) + "\n", encoding=text_encoding, errors="replace")


def main() -> None:
    ap = argparse.ArgumentParser(description="Export Langrisser V scripts in lang3-like .sjs/.tbl format.")
    ap.add_argument("--scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--scen2", default="work/extracted/SCEN2.DAT")
    ap.add_argument("--groups-report", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--groups", default="confirmed,symbol", help="Comma-separated groups from groups_report to use (default: confirmed,symbol)")
    ap.add_argument("--out-root", default="work/lang5_lang3_format")
    ap.add_argument("--text-encoding", default="utf-8", help="Encoding for .sjs and .tbl output files (default: utf-8)")
    args = ap.parse_args()

    allowed_groups = {g.strip() for g in args.groups.split(",") if g.strip()}
    token_to_char = load_map_from_groups_report(Path(args.groups_report), allowed_groups)

    out_root = Path(args.out_root)
    out_scripts_dir = out_root / "scripts" / "jp"
    out_scripts_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, str]] = []
    rows.extend(export_one(Path(args.scen), "scen", out_scripts_dir, token_to_char, args.text_encoding))
    rows.extend(export_one(Path(args.scen2), "scen2_", out_scripts_dir, token_to_char, args.text_encoding))

    write_tbl(out_scripts_dir / "lang5.tbl", token_to_char, args.text_encoding)

    csv_path = out_root / "all_records.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        fields = ["source_file", "chunk_index", "record_index", "word_count", "unknown_token_count", "text"]
        wr = csv.DictWriter(fh, fieldnames=fields)
        wr.writeheader()
        wr.writerows(rows)

    unknown_total = sum(int(r["unknown_token_count"]) for r in rows)
    words_total = sum(int(r["word_count"]) for r in rows)
    summary = out_root / "summary.txt"
    summary.write_text(
        "\n".join(
            [
                f"groups={','.join(sorted(allowed_groups))}",
                f"text_encoding={args.text_encoding}",
                f"map_entries={len(token_to_char)}",
                f"records={len(rows)}",
                f"words_total={words_total}",
                f"unknown_tokens_total={unknown_total}",
                f"groups_report={Path(args.groups_report)}",
                f"scripts_dir={out_scripts_dir}",
                f"csv={csv_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"scripts_dir={out_scripts_dir}")
    print(f"map_entries={len(token_to_char)} groups={','.join(sorted(allowed_groups))}")
    print(f"records={len(rows)} unknown_tokens_total={unknown_total}")
    print(f"summary={summary}")


if __name__ == "__main__":
    main()
