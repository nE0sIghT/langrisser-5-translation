#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from lang5_textcodec import save_tbl


def load_lang3_tbl(path: Path) -> dict[int, str]:
    out: dict[int, str] = {}
    for raw_ln in path.read_bytes().splitlines():
        ln = raw_ln.strip()
        if not ln or ln.startswith(b';') or b'=' not in ln:
            continue
        k, v = ln.split(b'=', 1)
        try:
            tok = int(k.decode('ascii'), 16)
        except Exception:
            continue
        try:
            ch = v.decode('cp932')
        except Exception:
            continue
        if ch:
            out[tok] = ch[0]
    return out


def load_manual(path: Path) -> dict[int, str]:
    raw = json.loads(path.read_text(encoding='utf-8'))
    out: dict[int, str] = {}
    for k, v in raw.items():
        try:
            tok = int(k, 16)
        except Exception:
            continue
        if isinstance(v, str) and v:
            out[tok] = v[0]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description='Build Langrisser V table from lang3.tbl with manual overrides.')
    ap.add_argument('--lang3-tbl', default='external/lang3/scripts/jp/lang3.tbl')
    ap.add_argument('--manual', default='scripts/lang5_token_map_manual.json')
    ap.add_argument('--out', default='work/tables/lang5_merged.tbl')
    args = ap.parse_args()

    lang3 = load_lang3_tbl(Path(args.lang3_tbl))
    manual = load_manual(Path(args.manual))

    merged = dict(lang3)
    merged.update(manual)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    save_tbl(out, merged)

    overlap = sum(1 for t in manual if t in lang3)
    diffs = sum(1 for t, ch in manual.items() if t in lang3 and lang3[t] != ch)
    print(f'lang3={len(lang3)} manual={len(manual)} overlap={overlap} manual_diffs={diffs}')
    print(f'wrote {out} ({len(merged)} entries)')


if __name__ == '__main__':
    main()
