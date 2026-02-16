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


def load_char_map(groups_report_csv: Path) -> Dict[int, str]:
    out: Dict[int, str] = {}
    with groups_report_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
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


def dump_one(
    src: Path,
    out_dir: Path,
    token_to_char: Dict[int, str],
) -> List[Dict[str, str]]:
    data = src.read_bytes()
    chunks = split_chunks(data)
    root = out_dir / src.stem
    root.mkdir(parents=True, exist_ok=True)
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
        lines.append(f"# chunk={cidx} file={src.name} start=0x{s:06X} end=0x{e:06X}")
        lines.append(f"# table_off=0x{tab_off:04X} entries={len(vals)} rec_start_idx={rec_start_idx}")
        lines.append("# format: rec_index<TAB>text")

        for ridx in range(rec_start_idx, len(vals) - 1):
            a = tab_off + vals[ridx]
            b = tab_off + vals[ridx + 1]
            if not (0 <= a < b <= len(chunk)):
                continue
            words = words_from_bytes(chunk[a:b])
            text, unknown = decode_words(words, token_to_char)
            lines.append(f"{ridx}\t{text}")
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

        (root / f"chunk_{cidx:03d}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Dump Langrisser V SCEN/SCEN2 using groups_report.csv token->char map.")
    ap.add_argument("--scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--scen2", default="work/extracted/SCEN2.DAT")
    ap.add_argument("--groups-report", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--out-dir", default="work/scriptdump_groups")
    args = ap.parse_args()

    token_to_char = load_char_map(Path(args.groups_report))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    rows.extend(dump_one(Path(args.scen), out_dir, token_to_char))
    rows.extend(dump_one(Path(args.scen2), out_dir, token_to_char))

    csv_path = out_dir / "all_records.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        fields = ["source_file", "chunk_index", "record_index", "word_count", "unknown_token_count", "text"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    unknown_total = sum(int(r["unknown_token_count"]) for r in rows)
    words_total = sum(int(r["word_count"]) for r in rows)
    summary = out_dir / "summary.txt"
    summary.write_text(
        "\n".join(
            [
                f"records={len(rows)}",
                f"words_total={words_total}",
                f"unknown_tokens_total={unknown_total}",
                f"groups_report={Path(args.groups_report)}",
                f"csv={csv_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"wrote {len(rows)} records")
    print(f"csv: {csv_path}")
    print(f"summary: {summary}")


if __name__ == "__main__":
    main()
