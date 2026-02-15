#!/usr/bin/env python3
import argparse
import csv
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def get_font(font_path: str, size: int):
    if font_path:
        return ImageFont.truetype(font_path, size=size)
    for cand in [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc',
    ]:
        if Path(cand).exists():
            return ImageFont.truetype(cand, size=size)
    return ImageFont.load_default()


def render_ttf_cell(ch: str, size: int, font):
    img = Image.new('L', (size, size), 255)
    d = ImageDraw.Draw(img)
    bbox = d.textbbox((0, 0), ch, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (size - tw) // 2 - bbox[0]
    y = (size - th) // 2 - bbox[1]
    d.text((x, y), ch, font=font, fill=0)
    return img


def xbrz64(tile: Image.Image) -> Image.Image:
    with tempfile.TemporaryDirectory(prefix='lang5_pair_') as td:
        in_p = Path(td) / 'in.png'
        out_p = Path(td) / 'out.png'
        tile.save(in_p)
        subprocess.run(['xbrzscale', '5', str(in_p), str(out_p)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        up = Image.open(out_p).convert('L')  # 60x60
        canvas = Image.new('L', (64, 64), 255)
        canvas.paste(up, ((64 - up.width) // 2, (64 - up.height) // 2))
        return canvas


def read_indices(path: Path):
    return {int(x.strip()) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sheet-inv', default='work/font_probe/l512x12qg8_inv_12x12.png')
    ap.add_argument('--token-map', default='work/font_export/token_map_guess_full_noocr_round10_seed.json')
    ap.add_argument('--ocr-csv', default='work/font_export/group_unconfirmed_xbrz64_ocr.csv')
    ap.add_argument('--confirmed', default='work/font_export/group_confirmed_indices.txt')
    ap.add_argument('--symbols', default='work/font_export/group_symbol_indices.txt')
    ap.add_argument('--out', default='work/font_export/grouped')
    ap.add_argument('--pair-size', type=int, default=128)
    ap.add_argument('--ttf-size', type=int, default=128)
    ap.add_argument('--ttf', default='')
    ap.add_argument('--fallback-char', default='?')
    args = ap.parse_args()

    out = Path(args.out)
    d_conf = out / 'pairs_confirmed'
    d_un = out / 'pairs_unconfirmed'
    d_sym = out / 'symbols_only'
    for d in [d_conf, d_un, d_sym]:
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    token_map = json.loads(Path(args.token_map).read_text(encoding='utf-8'))
    confirmed = read_indices(Path(args.confirmed))
    symbols = read_indices(Path(args.symbols))

    ocr_map = {}
    with Path(args.ocr_csv).open(encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            ch = (row.get('ocr_char') or '').strip()
            if ch:
                ocr_map[int(row['index_dec'])] = ch[0]

    img_inv = Image.open(args.sheet_inv).convert('L')
    cols = img_inv.width // 12
    total = (img_inv.width // 12) * (img_inv.height // 12)
    font = get_font(args.ttf, args.ttf_size)

    report = out / 'groups_report.csv'
    with report.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['index_dec', 'index_hex', 'group', 'char', 'source'])

        for idx in range(total):
            row, col = divmod(idx, cols)
            box = (col * 12, row * 12, (col + 1) * 12, (row + 1) * 12)
            g_inv = img_inv.crop(box)
            g_x64 = xbrz64(g_inv)

            if idx in symbols:
                g_x64.save(d_sym / f'{idx:04d}.png')
                w.writerow([idx, f'{idx:04X}', 'symbol', '', 'none'])
                continue

            key = f'{idx:04X}'
            if idx in confirmed and token_map.get(key):
                ch = token_map[key]
                group = 'confirmed'
                source = 'token_map'
            else:
                # Unconfirmed: OCR result takes precedence; then map fallback; then '?'.
                ch = ocr_map.get(idx) or token_map.get(key) or args.fallback_char
                group = 'unconfirmed'
                source = 'ocr' if idx in ocr_map else ('token_map' if token_map.get(key) else 'fallback')

            ttf_cell = render_ttf_cell(ch, args.pair_size, font)
            game_cell = g_x64.resize((args.pair_size, args.pair_size), Image.NEAREST)
            pair = Image.new('L', (args.pair_size * 2 + 8, args.pair_size), 255)
            pair.paste(game_cell, (0, 0))
            pair.paste(ttf_cell, (args.pair_size + 8, 0))
            out_p = (d_conf if group == 'confirmed' else d_un) / f'{idx:04d}.png'
            pair.save(out_p)
            w.writerow([idx, f'{idx:04X}', group, ch, source])

    print('out', out)
    print('confirmed_pairs', len(list(d_conf.glob('*.png'))))
    print('unconfirmed_pairs', len(list(d_un.glob('*.png'))))
    print('symbols', len(list(d_sym.glob('*.png'))))
    print('report', report)


if __name__ == '__main__':
    main()
