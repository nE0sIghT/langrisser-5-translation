#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List


def build_cp932_table() -> List[str]:
    out: List[str] = []
    for b1 in list(range(0x81, 0x9F + 1)) + list(range(0xE0, 0xFC + 1)):
        for b2 in list(range(0x40, 0x7E + 1)) + list(range(0x80, 0xFC + 1)):
            try:
                out.append(bytes([b1, b2]).decode('cp932'))
            except Exception:
                continue
    return out


def load_manual_map(path: Path) -> Dict[int, str]:
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


def decode_token(tok: int, cp932_chars: List[str], mp: Dict[int, str], shift: int) -> str:
    if tok in mp:
        return mp[tok]
    if tok in (0x0005,):
        return '、'
    if tok in (0x0006,):
        return '。'
    if tok in (0x00CF,):
        return '・'
    if tok in (0x00D1,):
        return 'ー'
    if tok >= 0xFF00:
        return '{' + f'{tok:04X}' + '}'
    j = tok + shift
    if 0 <= j < len(cp932_chars):
        return cp932_chars[j]
    return '[' + f'{tok:04X}' + ']'


def parse_words(hex_line: str) -> List[int]:
    if not hex_line:
        return []
    out: List[int] = []
    for x in hex_line.split():
        try:
            out.append(int(x, 16))
        except ValueError:
            continue
    return out


def extract_text_segments(words: List[int], cp932_chars: List[str], mp: Dict[int, str], shift: int) -> List[str]:
    out: List[str] = []
    i = 0
    while i < len(words):
        if words[i] == 0x0003:
            j = i + 1
            seg: List[str] = []
            while j < len(words) and words[j] not in (0x0004, 0xFFFE, 0xFFFD, 0xFFFC, 0xFB00):
                seg.append(decode_token(words[j], cp932_chars, mp, shift))
                j += 1
            if seg:
                out.append(''.join(seg))
            i = j
        else:
            i += 1
    return out


def first_fb00_label(words: List[int]) -> str:
    for i in range(len(words) - 1):
        if words[i] == 0xFB00:
            return f'{words[i+1]:04X}'
    return ''


def main() -> None:
    p = argparse.ArgumentParser(description='Extract likely text segments from token records (0003..0004 windows).')
    p.add_argument('--records', default='work/scen_analysis/records.csv')
    p.add_argument('--token-map', default='scripts/lang5_token_map_manual.json')
    p.add_argument('--cp932-shift', type=int, default=166)
    p.add_argument('--out-csv', default='work/scen_analysis/text_segments.csv')
    p.add_argument('--out-txt', default='work/scen_analysis/text_segments.txt')
    args = p.parse_args()

    mp = load_manual_map(Path(args.token_map))
    cp932_chars = build_cp932_table()

    rows = list(csv.DictReader(Path(args.records).open('r', encoding='utf-8')))
    out_rows: List[dict] = []
    for r in rows:
        words = parse_words(r.get('words_hex', ''))
        segs = extract_text_segments(words, cp932_chars, mp, args.cp932_shift)
        if not segs:
            continue
        out_rows.append(
            {
                'chunk_index': r['chunk_index'],
                'record_index': r['record_index'],
                'offset': r['offset'],
                'word_count': r['word_count'],
                'fb00_label': first_fb00_label(words),
                'segments_joined': ' | '.join(segs),
                'words_hex': r['words_hex'],
            }
        )

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                'chunk_index',
                'record_index',
                'offset',
                'word_count',
                'fb00_label',
                'segments_joined',
                'words_hex',
            ],
        )
        w.writeheader()
        w.writerows(out_rows)

    out_txt = Path(args.out_txt)
    with out_txt.open('w', encoding='utf-8') as fh:
        cur = None
        for r in out_rows:
            c = int(r['chunk_index'])
            if c != cur:
                cur = c
                fh.write(f'\n=== chunk {c} ===\n')
            lab = r['fb00_label'] or '-'
            fh.write(
                f"rec={r['record_index']:>4} off=0x{int(r['offset']):04X} fb00={lab} : "
                f"{r['segments_joined']}\n"
            )

    print(f'wrote {out_csv} ({len(out_rows)} rows)')
    print(f'wrote {out_txt}')


if __name__ == '__main__':
    main()
