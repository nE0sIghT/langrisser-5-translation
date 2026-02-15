#!/usr/bin/env python3
import argparse
import csv
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def load_confirmed_indices(path: Path):
    return sorted({int(x.strip()) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()})


def load_char_map_from_report(path: Path):
    out = {}
    with path.open(encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            ch = (row.get('char') or '').strip()
            if ch:
                out[int(row['index_dec'])] = ch
    return out


def build_jis0208_order():
    seq = []
    for ku in range(1, 95):
        for ten in range(1, 95):
            bs = b'\x1b$B' + bytes([0x20 + ku, 0x20 + ten]) + b'\x1b(B'
            try:
                ch = bs.decode('iso2022_jp')
            except Exception:
                continue
            if len(ch) == 1:
                seq.append(ch)
    return seq


def get_font(path: str, size: int):
    if path:
        return ImageFont.truetype(path, size=size)
    for cand in [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc',
    ]:
        if Path(cand).exists():
            return ImageFont.truetype(cand, size=size)
    return ImageFont.load_default()


def render_ttf_cell(ch: str, size: int, font):
    cell = Image.new('L', (size, size), 255)
    d = ImageDraw.Draw(cell)
    bbox = d.textbbox((0, 0), ch, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (size - tw) // 2 - bbox[0]
    y = (size - th) // 2 - bbox[1]
    d.text((x, y), ch, font=font, fill=0)
    return cell


def xbrz64(tile: Image.Image) -> Image.Image:
    with tempfile.TemporaryDirectory(prefix='lang5_jisfill_') as td:
        in_p = Path(td) / 'in.png'
        out_p = Path(td) / 'out.png'
        tile.save(in_p)
        subprocess.run(['xbrzscale', '5', str(in_p), str(out_p)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        up = Image.open(out_p).convert('L')
        canvas = Image.new('L', (64, 64), 255)
        canvas.paste(up, ((64 - up.width) // 2, (64 - up.height) // 2))
        return canvas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--confirmed-indices', default='work/font_export/group_confirmed_indices.txt')
    ap.add_argument('--groups-report', default='work/font_export/grouped/groups_report.csv')
    ap.add_argument('--sheet-inv', default='work/font_probe/l512x12qg8_inv_12x12.png')
    ap.add_argument('--out-dir', default='work/font_export/jis_gapfill_232plus')
    ap.add_argument('--min-index', type=int, default=232)
    ap.add_argument('--pair-size', type=int, default=128)
    ap.add_argument('--ttf-size', type=int, default=128)
    ap.add_argument('--ttf', default='')
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    pairs_dir = out_dir / 'pairs'
    pairs_dir.mkdir(parents=True, exist_ok=True)
    for p in pairs_dir.glob('*.png'):
        p.unlink()

    confirmed_all = load_confirmed_indices(Path(args.confirmed_indices))
    char_map = load_char_map_from_report(Path(args.groups_report))

    confirmed = [i for i in confirmed_all if i >= args.min_index and i in char_map]
    if not confirmed:
        raise SystemExit('No confirmed 232+ points with mapped chars.')

    min_i = min(confirmed)
    max_i = max(confirmed)

    jis = build_jis0208_order()
    rank = {ch: i for i, ch in enumerate(jis)}

    confirmed_set = set(confirmed)
    # left-anchor lookup
    left_by_idx = {}
    left = None
    for i in range(min_i, max_i + 1):
        if i in confirmed_set:
            left = i
        left_by_idx[i] = left

    # build filled map
    filled = {}
    source = {}
    for i in range(min_i, max_i + 1):
        if i in confirmed_set:
            filled[i] = char_map[i]
            source[i] = 'confirmed'
            continue
        li = left_by_idx[i]
        if li is None:
            source[i] = 'unfilled'
            continue
        lch = char_map.get(li, '')
        if lch not in rank:
            source[i] = 'unfilled'
            continue
        off = i - li
        ri = rank[lch] + off
        if 0 <= ri < len(jis):
            filled[i] = jis[ri]
            source[i] = 'jis_from_left'
        else:
            source[i] = 'unfilled'

    # output csv
    csv_path = out_dir / 'mapping.csv'
    with csv_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['index_dec', 'index_hex', 'char', 'source', 'left_anchor'])
        for i in range(min_i, max_i + 1):
            w.writerow([i, f'{i:04X}', filled.get(i, ''), source.get(i, 'unfilled'), left_by_idx.get(i)])

    img_inv = Image.open(args.sheet_inv).convert('L')
    cols = img_inv.width // 12
    font = get_font(args.ttf, args.ttf_size)

    pair_count = 0
    for i in range(min_i, max_i + 1):
        ch = filled.get(i, '')
        if not ch:
            continue
        row, col = divmod(i, cols)
        box = (col * 12, row * 12, (col + 1) * 12, (row + 1) * 12)
        g = img_inv.crop(box)
        gx64 = xbrz64(g)
        game_cell = gx64.resize((args.pair_size, args.pair_size), Image.NEAREST)
        ttf_cell = render_ttf_cell(ch, args.pair_size, font)
        pair = Image.new('L', (args.pair_size * 2 + 8, args.pair_size), 255)
        pair.paste(game_cell, (0, 0))
        pair.paste(ttf_cell, (args.pair_size + 8, 0))
        pair.save(pairs_dir / f'{i:04d}.png')
        pair_count += 1

    summary = out_dir / 'summary.txt'
    summary.write_text(
        f'min_index={min_i}\nmax_index={max_i}\n'
        f'confirmed_points={len(confirmed)}\n'
        f'filled_points={len(filled)}\n'
        f'pair_count={pair_count}\n',
        encoding='utf-8',
    )
    print(f'out_dir={out_dir}')
    print(f'min_index={min_i} max_index={max_i}')
    print(f'confirmed_points={len(confirmed)} pair_count={pair_count}')
    print(f'mapping_csv={csv_path}')


if __name__ == '__main__':
    main()
