#!/usr/bin/env python3
import argparse
import csv
import json
import re
import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def read_chunk_pointers(data: bytes) -> List[int]:
    size = len(data)
    points: List[int] = []
    off = 0
    while off + 4 <= size:
        ptr = struct.unpack_from("<I", data, off)[0]
        points.append(ptr)
        off += 4
        if ptr == size:
            break
    return points


def split_chunks(data: bytes) -> List[bytes]:
    pts = read_chunk_pointers(data)
    return [data[pts[i] : pts[i + 1]] for i in range(len(pts) - 1)]


def find_local_table(chunk: bytes, min_entries: int = 32) -> Optional[Tuple[int, List[int]]]:
    n = len(chunk)
    best: Optional[Tuple[int, List[int]]] = None
    for start in range(0, n - 4, 2):
        vals: List[int] = []
        prev = -1
        i = start
        limit = n - start
        while i + 2 <= n:
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


def decode_words(blob: bytes) -> List[int]:
    return [blob[i] | (blob[i + 1] << 8) for i in range(0, len(blob) - 1, 2)]


def extract_records(chunk: bytes) -> List[Dict]:
    tbl = find_local_table(chunk)
    if not tbl:
        return []
    table_off, vals = tbl
    if vals and vals[0] == 0:
        table_off += 2
        vals = vals[1:]
    recs = []
    for ridx in range(1, len(vals) - 1):
        a = table_off + vals[ridx]
        b = table_off + vals[ridx + 1]
        if b <= a or b > len(chunk):
            continue
        words = decode_words(chunk[a:b])
        if not words:
            continue
        recs.append(
            {
                "record_index": ridx,
                "offset": a,
                "size": b - a,
                "words": words,
            }
        )
    return recs


def is_textlike_word(w: int) -> bool:
    hi = (w >> 8) & 0xFF
    return hi in (0x00, 0x01, 0x02)


def token_string(words: List[int]) -> str:
    out = []
    for w in words:
        if w == 0xFFFF:
            out.append("{END}")
        elif w == 0xFFFE:
            out.append("{CTRL_FFFE}")
        elif w == 0xFFFC:
            out.append("{CTRL_FFFC}")
        elif (w & 0xFF00) == 0xFB00:
            out.append(f"{{CTRL_{w:04X}}}")
        elif (w >> 8) == 0xFF:
            out.append(f"{{FF:{w & 0xFF:02X}}}")
        else:
            out.append(f"[{w:04X}]")
    return "".join(out)


def scenario_tags_from_translation(path: Path) -> Dict[int, str]:
    txt = path.read_text(errors="ignore")
    pat = re.compile(r"^Scenario\s+(\d+)(\s+Clear)?\s*$", re.IGNORECASE)
    tags: Dict[int, List[str]] = {}
    for ln in txt.splitlines():
        m = pat.match(ln.strip())
        if not m:
            continue
        n = int(m.group(1))
        tags.setdefault(n, [])
        t = "clear" if m.group(2) else "main"
        if t not in tags[n]:
            tags[n].append(t)
    return {k: "+".join(v) for k, v in tags.items()}


def scenario_english_lines(path: Path) -> Dict[int, List[str]]:
    txt = path.read_text(errors="ignore")
    lines = txt.splitlines()
    head = re.compile(r"^Scenario\s+(\d+)(\s+Clear)?\s*$", re.IGNORECASE)
    out: Dict[int, List[str]] = {}
    cur: Optional[int] = None
    for raw in lines:
        s = raw.strip()
        m = head.match(s)
        if m:
            cur = int(m.group(1))
            out.setdefault(cur, [])
            continue
        if cur is None:
            continue
        # Drop empty lines and section separators.
        if not s or s.startswith("-----"):
            continue
        out[cur].append(s)
    return out


def chunk_to_scenario(chunk_index: int, tags: Dict[int, str]) -> Optional[str]:
    if 1 <= chunk_index <= 36:
        t = tags.get(chunk_index, "unknown")
        return f"Scenario {chunk_index} ({t})"
    if chunk_index in (40, 41, 42):
        return f"LateGame chunk {chunk_index}"
    return None


def main() -> None:
    p = argparse.ArgumentParser(description="Extract scenario-ordered tokenized JP script from SCEN.DAT.")
    p.add_argument("--scen", default="work/extracted/SCEN.DAT")
    p.add_argument("--translation", default="translation.txt")
    p.add_argument("--out", default="work/scen_analysis/story_ordered.json")
    args = p.parse_args()

    scen = Path(args.scen).read_bytes()
    chunks = split_chunks(scen)
    tags = scenario_tags_from_translation(Path(args.translation))

    out: Dict[str, Dict] = {}
    en_lines_by_scen = scenario_english_lines(Path(args.translation))
    for cidx, chunk in enumerate(chunks):
        scenario = chunk_to_scenario(cidx, tags)
        if not scenario:
            continue
        recs = extract_records(chunk)
        if not recs:
            continue

        # Small early records ending with END tend to be speaker/name entries.
        name_records = []
        for r in recs[:30]:
            w = r["words"]
            if len(w) <= 16 and 0xFFFF in w and w.count(0xFB00) == 0:
                name_records.append(
                    {
                        "record_index": r["record_index"],
                        "tokenized": token_string(w),
                    }
                )

        dialogue_records = []
        for r in recs:
            w = r["words"]
            textlike = sum(1 for x in w if is_textlike_word(x))
            if textlike < 4:
                continue
            # Include dialog-command records and text-heavy records.
            if 0xFB00 in w or (textlike / max(1, len(w))) >= 0.55:
                dialogue_records.append(
                    {
                        "record_index": r["record_index"],
                        "offset": r["offset"],
                        "size": r["size"],
                        "tokenized": token_string(w),
                        "text_token_count": textlike,
                    }
                )

        out[scenario] = {
            "chunk_index": cidx,
            "name_records": name_records,
            "dialogue_records": dialogue_records,
        }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))

    # Build a practical alignment preview: scenario-local order vs translation order.
    align_path = out_path.with_name("story_alignment_preview.csv")
    rows = []
    for scenario, payload in out.items():
        m = re.match(r"^Scenario\s+(\d+)\b", scenario)
        if not m:
            continue
        sn = int(m.group(1))
        en_lines = en_lines_by_scen.get(sn, [])
        jp_lines = payload["dialogue_records"]
        n = max(len(en_lines), len(jp_lines))
        for i in range(n):
            rows.append(
                {
                    "scenario": scenario,
                    "chunk_index": payload["chunk_index"],
                    "seq": i + 1,
                    "jp_record_index": jp_lines[i]["record_index"] if i < len(jp_lines) else "",
                    "jp_tokenized": jp_lines[i]["tokenized"] if i < len(jp_lines) else "",
                    "en_line": en_lines[i] if i < len(en_lines) else "",
                }
            )
    with align_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["scenario", "chunk_index", "seq", "jp_record_index", "jp_tokenized", "en_line"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
