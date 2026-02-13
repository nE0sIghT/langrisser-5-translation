#!/usr/bin/env python3
import argparse
import csv
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


MAGIC_SPLIT = bytes.fromhex(
    "01 00 00 01 80 00 00 00 78 80 70 80 30 30 01 02 "
    "78 78 00 13 28 13 38 38 02 00 A0 A0 00 10 18 10"
)


@dataclass
class ChunkInfo:
    index: int
    start: int
    end: int
    size: int
    magic_offset: Optional[int]
    local_table_offset: Optional[int]
    local_table_count: int
    record_count: int
    fb00_count: int
    differs_in_scen2: bool
    scenario_hint: str


@dataclass
class RecordInfo:
    chunk_index: int
    record_index: int
    offset: int
    size: int
    word_count: int
    has_ffff_end: bool
    fb00_count: int
    fffe_count: int
    fffc_count: int
    charlike_ratio: float
    first_words_hex: str
    last_words_hex: str
    words_hex: str


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


def split_chunks(data: bytes) -> List[Tuple[int, int]]:
    points = read_chunk_pointers(data)
    return [(points[i], points[i + 1]) for i in range(len(points) - 1)]


def words_from_bytes(blob: bytes) -> List[int]:
    return [blob[i] | (blob[i + 1] << 8) for i in range(0, len(blob) - 1, 2)]


def find_best_local_table(chunk: bytes, min_entries: int = 32) -> Optional[Tuple[int, List[int]]]:
    n = len(chunk)
    best: Optional[Tuple[int, List[int]]] = None
    for start in range(0, n - 4, 2):
        values: List[int] = []
        prev = -1
        i = start
        limit = n - start
        while i + 2 <= n:
            v = chunk[i] | (chunk[i + 1] << 8)
            if v <= prev or v >= limit:
                break
            values.append(v)
            prev = v
            i += 2
        if len(values) >= min_entries:
            if best is None or len(values) > len(best[1]):
                best = (start, values)
    return best


def scenario_headings_from_translation(path: Path) -> Dict[int, str]:
    text = path.read_text(errors="ignore")
    scenario_re = re.compile(r"^Scenario\s+(\d+)(\s+Clear)?\s*$", re.IGNORECASE)
    by_number: Dict[int, List[str]] = {}
    for raw in text.splitlines():
        m = scenario_re.match(raw.strip())
        if not m:
            continue
        n = int(m.group(1))
        tag = "clear" if m.group(2) else "main"
        by_number.setdefault(n, [])
        if tag not in by_number[n]:
            by_number[n].append(tag)
    out: Dict[int, str] = {}
    for n in sorted(by_number):
        out[n] = "+".join(by_number[n])
    return out


def scenario_hint_for_chunk(chunk_index: int, known: Dict[int, str]) -> str:
    # Empirical mapping:
    # chunks 1..36 in SCEN/SCEN2 are the main route-dependent scenario blocks.
    if 1 <= chunk_index <= 36:
        scen = chunk_index
        suffix = known.get(scen, "unknown")
        return f"Scenario {scen} ({suffix})"
    if chunk_index in (40, 41, 42):
        return "Late-game/ending block"
    return ""


def build_record_infos(chunk_index: int, chunk: bytes) -> Tuple[Optional[int], int, List[RecordInfo]]:
    table = find_best_local_table(chunk)
    if table is None:
        return None, 0, []
    table_off, values = table
    # Many chunks start the table with a leading 0 sentinel.
    if values and values[0] == 0:
        table_off += 2
        values = values[1:]
    recs: List[RecordInfo] = []
    for i in range(1, len(values) - 1):
        a = table_off + values[i]
        b = table_off + values[i + 1]
        if b <= a or b > len(chunk):
            continue
        rec = chunk[a:b]
        w = words_from_bytes(rec)
        if not w:
            continue
        bank_charlike = sum(1 for x in w if (x >> 8) in (0x00, 0x01, 0x02, 0xFF))
        charlike_ratio = bank_charlike / len(w)
        info = RecordInfo(
            chunk_index=chunk_index,
            record_index=i,
            offset=a,
            size=len(rec),
            word_count=len(w),
            has_ffff_end=(w[-1] == 0xFFFF),
            fb00_count=w.count(0xFB00),
            fffe_count=w.count(0xFFFE),
            fffc_count=w.count(0xFFFC),
            charlike_ratio=round(charlike_ratio, 4),
            first_words_hex=" ".join(f"{x:04X}" for x in w[:12]),
            last_words_hex=" ".join(f"{x:04X}" for x in w[-6:]),
            words_hex=" ".join(f"{x:04X}" for x in w),
        )
        recs.append(info)
    return table_off, len(values), recs


def write_csv(path: Path, rows: List[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze Langrisser V SCEN/SCEN2 structure and extract record-level token streams."
    )
    parser.add_argument("--scen", default="work/extracted/SCEN.DAT")
    parser.add_argument("--scen2", default="work/extracted/SCEN2.DAT")
    parser.add_argument("--translation", default="translation.txt")
    parser.add_argument("--out-dir", default="work/scen_analysis")
    parser.add_argument("--max-record-words", type=int, default=256)
    args = parser.parse_args()

    scen_path = Path(args.scen)
    scen2_path = Path(args.scen2)
    trans_path = Path(args.translation)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    scen = scen_path.read_bytes()
    scen2 = scen2_path.read_bytes()
    scen_chunks = split_chunks(scen)
    scen2_chunks = split_chunks(scen2)
    if len(scen_chunks) != len(scen2_chunks):
        raise RuntimeError("SCEN and SCEN2 chunk counts do not match.")

    headings = scenario_headings_from_translation(trans_path)
    chunk_infos: List[ChunkInfo] = []
    records_full: List[RecordInfo] = []

    for idx, ((s, e), (s2, e2)) in enumerate(zip(scen_chunks, scen2_chunks)):
        chunk = scen[s:e]
        words = words_from_bytes(chunk)
        magic_off = chunk.find(MAGIC_SPLIT)
        table_off, table_count, records = build_record_infos(idx, chunk)
        differs = scen[s:e] != scen2[s2:e2]
        hint = scenario_hint_for_chunk(idx, headings)
        info = ChunkInfo(
            index=idx,
            start=s,
            end=e,
            size=e - s,
            magic_offset=(magic_off if magic_off >= 0 else None),
            local_table_offset=table_off,
            local_table_count=table_count,
            record_count=len(records),
            fb00_count=words.count(0xFB00),
            differs_in_scen2=differs,
            scenario_hint=hint,
        )
        chunk_infos.append(info)
        records_full.extend(records)

    # Chunk summary CSV.
    chunk_rows = [
        {
            "chunk_index": c.index,
            "start": c.start,
            "end": c.end,
            "size": c.size,
            "magic_offset": "" if c.magic_offset is None else c.magic_offset,
            "local_table_offset": "" if c.local_table_offset is None else c.local_table_offset,
            "local_table_count": c.local_table_count,
            "record_count": c.record_count,
            "fb00_count": c.fb00_count,
            "differs_in_scen2": int(c.differs_in_scen2),
            "scenario_hint": c.scenario_hint,
        }
        for c in chunk_infos
    ]
    write_csv(out_dir / "chunks.csv", chunk_rows)

    # Full record dump (token stream in hex words).
    record_rows = []
    for r in records_full:
        trimmed_words = r.words_hex.split(" ")
        if args.max_record_words > 0 and len(trimmed_words) > args.max_record_words:
            words_hex = " ".join(trimmed_words[: args.max_record_words]) + " ...TRUNCATED..."
        else:
            words_hex = r.words_hex
        record_rows.append(
            {
                "chunk_index": r.chunk_index,
                "record_index": r.record_index,
                "offset": r.offset,
                "size": r.size,
                "word_count": r.word_count,
                "has_ffff_end": int(r.has_ffff_end),
                "fb00_count": r.fb00_count,
                "fffe_count": r.fffe_count,
                "fffc_count": r.fffc_count,
                "charlike_ratio": r.charlike_ratio,
                "first_words_hex": r.first_words_hex,
                "last_words_hex": r.last_words_hex,
                "words_hex": words_hex,
            }
        )
    write_csv(out_dir / "records.csv", record_rows)

    # Short terminal records are usually name/label tokens (speaker dictionary block).
    name_rows = []
    for r in records_full:
        if not r.has_ffff_end:
            continue
        if r.size > 48:
            continue
        if r.fb00_count or r.fffe_count or r.fffc_count:
            continue
        name_rows.append(
            {
                "chunk_index": r.chunk_index,
                "record_index": r.record_index,
                "offset": r.offset,
                "size": r.size,
                "word_count": r.word_count,
                "words_hex": r.words_hex,
            }
        )
    write_csv(out_dir / "names.csv", name_rows)

    # Storyline-oriented view: Scenario number -> chunk index.
    # This is a practical linkage layer for script work, even before full charset mapping.
    story_rows = []
    for c in chunk_infos:
        if not c.scenario_hint.startswith("Scenario "):
            continue
        story_rows.append(
            {
                "scenario": c.scenario_hint,
                "chunk_index": c.index,
                "scen_variant": "SCEN",
                "differs_vs_scen2": int(c.differs_in_scen2),
                "record_count": c.record_count,
                "fb00_count": c.fb00_count,
                "magic_offset": "" if c.magic_offset is None else c.magic_offset,
            }
        )
        story_rows.append(
            {
                "scenario": c.scenario_hint,
                "chunk_index": c.index,
                "scen_variant": "SCEN2" if c.differs_in_scen2 else "SCEN (identical)",
                "differs_vs_scen2": int(c.differs_in_scen2),
                "record_count": c.record_count,
                "fb00_count": c.fb00_count,
                "magic_offset": "" if c.magic_offset is None else c.magic_offset,
            }
        )
    write_csv(out_dir / "story_map.csv", story_rows)

    summary = {
        "scen_file": str(scen_path),
        "scen2_file": str(scen2_path),
        "chunk_count": len(chunk_infos),
        "chunks_differing_between_scen_and_scen2": [c.index for c in chunk_infos if c.differs_in_scen2],
        "magic_split_present_in_chunks": [c.index for c in chunk_infos if c.magic_offset is not None],
        "scenario_hints_found": sorted({c.scenario_hint for c in chunk_infos if c.scenario_hint}),
        "output_files": [
            str(out_dir / "chunks.csv"),
            str(out_dir / "records.csv"),
            str(out_dir / "names.csv"),
            str(out_dir / "story_map.csv"),
        ],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"analysis written to {out_dir}")


if __name__ == "__main__":
    main()
