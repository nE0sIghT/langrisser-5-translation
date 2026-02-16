#!/usr/bin/env python3
import argparse
import csv
import json
import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def read_chunk_pointers(data: bytes) -> List[int]:
    pts: List[int] = []
    off = 0
    while off + 4 <= len(data):
        v = struct.unpack_from('<I', data, off)[0]
        pts.append(v)
        off += 4
        if v == len(data):
            break
    return pts


def load_map(path: Path) -> Dict[int, str]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding='utf-8'))
    out: Dict[int, str] = {}
    for k, v in raw.items():
        try:
            t = int(k, 16)
        except Exception:
            continue
        if isinstance(v, str) and v:
            out[t] = v[0]
    return out


def decode_words(words: List[int], mp: Dict[int, str]) -> str:
    out: List[str] = []
    for w in words:
        if w in mp:
            out.append(mp[w])
        elif 0xFF00 <= w <= 0xFFFF:
            out.append('{' + f'{w:04X}' + '}')
        else:
            out.append('[' + f'{w:04X}' + ']')
    return ''.join(out)


def _scan_increasing_offsets(chunk: bytes, start_off: int, min_entries: int) -> Optional[List[int]]:
    vals: List[int] = []
    prev = -1
    for i in range(start_off, len(chunk) - 1, 2):
        v = struct.unpack_from('<H', chunk, i)[0]
        if v == 0xFFFF:
            break
        if v >= len(chunk):
            break
        if prev != -1 and v <= prev:
            break
        vals.append(v)
        prev = v
    if len(vals) < min_entries:
        return None
    if vals[0] != 0:
        vals = [0] + vals
    return vals


def find_table_candidates(chunk: bytes, min_entries: int = 12) -> List[Tuple[int, List[int]]]:
    cands: List[Tuple[int, List[int]]] = []
    # Runtime-hint candidate: base0 + sub_3c
    if len(chunk) >= 0x50:
        base0 = struct.unpack_from('<I', chunk, 0x00)[0]
        if 0 <= base0 + 0x3E <= len(chunk):
            sub_3c = struct.unpack_from('<I', chunk, base0 + 0x3C)[0]
            hint = base0 + sub_3c
            if 0 <= hint + 4 <= len(chunk):
                vals = _scan_increasing_offsets(chunk, hint, min_entries)
                if vals:
                    cands.append((hint, vals))

    # Global scan for table-like offset runs.
    for off in range(0, len(chunk) - min_entries * 2, 2):
        vals = _scan_increasing_offsets(chunk, off, min_entries)
        if not vals:
            continue
        # Avoid duplicates by exact first/last signature.
        sig = (off, vals[0], vals[-1], len(vals))
        if any((o, v[0], v[-1], len(v)) == sig for o, v in cands):
            continue
        cands.append((off, vals))
    return cands


def extract_records(chunk: bytes, offsets: List[int]) -> List[Tuple[int, int, bytes, List[int]]]:
    out: List[Tuple[int, int, bytes, List[int]]] = []
    for ridx, (a, b) in enumerate(zip(offsets, offsets[1:]), start=1):
        if b <= a or b > len(chunk):
            continue
        rec = chunk[a:b]
        if len(rec) < 2:
            continue
        words = [struct.unpack_from('<H', rec, i)[0] for i in range(0, len(rec) & ~1, 2)]
        out.append((ridx, a, rec, words))
    return out


def find_fb00_label(words: List[int]) -> Optional[int]:
    for i in range(len(words) - 1):
        if words[i] == 0xFB00:
            return words[i + 1]
    return None


def charlike_ratio(words: List[int]) -> float:
    if not words:
        return 0.0
    good = 0
    for w in words:
        if w in (0x0005, 0x0006, 0x00CF, 0x00D1):
            good += 1
        elif 0x007E <= w <= 0x06FF:
            good += 1
    return good / len(words)


def score_records(rows: List[dict]) -> float:
    if not rows:
        return -1.0
    fb = sum(1 for r in rows if r['fb00_label'])
    avg_char = sum(float(r['charlike_ratio']) for r in rows) / len(rows)
    return fb * 100.0 + avg_char * 20.0 + len(rows) * 0.02


def main() -> None:
    p = argparse.ArgumentParser(description='Extract SCEN records using runtime-structure offsets (base0+sub_3c).')
    p.add_argument('--scen', default='work/extracted/SCEN.DAT')
    p.add_argument('--token-map', default='scripts/lang5_token_map_manual.json')
    p.add_argument('--out-csv', default='work/scen_analysis/stream_records.csv')
    p.add_argument('--out-ch56', default='work/scen_analysis/chunk56_stream.txt')
    args = p.parse_args()

    scen = Path(args.scen).read_bytes()
    pts = read_chunk_pointers(scen)
    mp = load_map(Path(args.token_map))

    rows: List[dict] = []
    for cidx in range(len(pts) - 1):
        s, e = pts[cidx], pts[cidx + 1]
        chunk = scen[s:e]
        cands = find_table_candidates(chunk)
        if not cands:
            continue
        best_rows: List[dict] = []
        best_table = -1
        best_score = -1.0
        for table_off, offsets in cands:
            recs = extract_records(chunk, offsets)
            cur_rows: List[dict] = []
            for ridx, off, rec, words in recs:
                fb_label = find_fb00_label(words)
                cur_rows.append(
                    {
                        'chunk_index': cidx,
                        'record_index': ridx,
                        'offset': off,
                        'size': len(rec),
                        'word_count': len(words),
                        'table_off': table_off,
                        'fb00_label': '' if fb_label is None else f'{fb_label:04X}',
                        'charlike_ratio': f'{charlike_ratio(words):.3f}',
                        'decoded_manual': decode_words(words, mp),
                        'words_hex': ' '.join(f'{w:04X}' for w in words),
                    }
                )
            sc = score_records(cur_rows)
            if sc > best_score:
                best_score = sc
                best_rows = cur_rows
                best_table = table_off
        for r in best_rows:
            r['table_off'] = best_table
        rows.extend(best_rows)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                'chunk_index',
                'record_index',
                'offset',
                'size',
                'word_count',
                'table_off',
                'fb00_label',
                'charlike_ratio',
                'decoded_manual',
                'words_hex',
            ],
        )
        w.writeheader()
        w.writerows(rows)

    ch56 = [r for r in rows if int(r['chunk_index']) == 56]
    out_ch56 = Path(args.out_ch56)
    with out_ch56.open('w', encoding='utf-8') as fh:
        for r in ch56:
            fh.write(
                f"chunk={r['chunk_index']} rec={r['record_index']} off=0x{int(r['offset']):04X} "
                f"size={r['size']} fb00={r['fb00_label'] or '-'}\n"
            )
            fh.write(f"DEC: {r['decoded_manual']}\n")
            fh.write(f"TOK: {r['words_hex']}\n\n")

    print(f'wrote {out_csv} ({len(rows)} rows)')
    print(f'wrote {out_ch56} ({len(ch56)} rows for chunk 56)')


if __name__ == '__main__':
    main()
