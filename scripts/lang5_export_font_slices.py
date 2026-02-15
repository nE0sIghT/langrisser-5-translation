#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Optional

from PIL import Image, ImageDraw, ImageFont


def load_token_map(path: Path) -> Dict[int, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[int, str] = {}
    for k, v in raw.items():
        try:
            idx = int(k, 16)
        except Exception:
            continue
        if isinstance(v, str) and v:
            out[idx] = v
    return out


def safe_char_tag(ch: str) -> str:
    cp = ord(ch)
    return f"U+{cp:04X}"


def get_font(font_path: Optional[Path], size: int) -> ImageFont.ImageFont:
    if font_path is not None:
        return ImageFont.truetype(str(font_path), size=size)
    candidates = [
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"),
    ]
    for cand in candidates:
        if cand.exists():
            return ImageFont.truetype(str(cand), size=size)
    return ImageFont.load_default()


def render_ttf_cell(ch: str, size: int, font: ImageFont.ImageFont) -> Image.Image:
    cell = Image.new("L", (size, size), 255)
    d = ImageDraw.Draw(cell)
    try:
        bbox = d.textbbox((0, 0), ch, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = (size - tw) // 2 - bbox[0]
        y = (size - th) // 2 - bbox[1]
    except Exception:
        x, y = 1, 1
    d.text((x, y), ch, font=font, fill=0)
    return cell


def build_contact_sheet(pair_files, out_path: Path, cols: int = 12, pad: int = 4) -> None:
    if not pair_files:
        return
    sample = Image.open(pair_files[0])
    pw, ph = sample.size
    sample.close()
    rows = (len(pair_files) + cols - 1) // cols
    cw = cols * pw + (cols + 1) * pad
    ch = rows * ph + (rows + 1) * pad
    canvas = Image.new("L", (cw, ch), 255)
    for i, p in enumerate(pair_files):
        r = i // cols
        c = i % cols
        x = pad + c * (pw + pad)
        y = pad + r * (ph + pad)
        img = Image.open(p).convert("L")
        canvas.paste(img, (x, y))
        img.close()
    canvas.save(out_path)


def main() -> None:
    ap = argparse.ArgumentParser(description="Export Langrisser V 12x12 font slices and TTF comparison pairs.")
    ap.add_argument("--sheet", default="work/font_probe/l512x12qg8_12x12.png")
    ap.add_argument("--sheet-inv", default="work/font_probe/l512x12qg8_inv_12x12.png")
    ap.add_argument("--token-map", default="scripts/lang5_token_map_manual.json")
    ap.add_argument("--tile-w", type=int, default=12)
    ap.add_argument("--tile-h", type=int, default=12)
    ap.add_argument("--cols", type=int, default=32)
    ap.add_argument("--rows", type=int, default=57)
    ap.add_argument("--ttf", default="")
    ap.add_argument("--ttf-size", type=int, default=12)
    ap.add_argument("--out-dir", default="work/font_export")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_norm = out_dir / "glyphs_normal"
    out_inv = out_dir / "glyphs_inverted"
    out_pairs = out_dir / "pairs_game_vs_ttf"
    out_norm.mkdir(parents=True, exist_ok=True)
    out_inv.mkdir(parents=True, exist_ok=True)
    out_pairs.mkdir(parents=True, exist_ok=True)

    sheet = Image.open(args.sheet).convert("L")
    sheet_inv = Image.open(args.sheet_inv).convert("L")
    token_map = load_token_map(Path(args.token_map))

    font = get_font(Path(args.ttf) if args.ttf else None, size=args.ttf_size)

    mapping_csv = out_dir / "glyph_index_to_utf8.csv"
    pair_files = []

    with mapping_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["index_dec", "index_hex", "row", "col", "utf8_char", "known"])
        for row in range(args.rows):
            for col in range(args.cols):
                idx = row * args.cols + col
                x0 = col * args.tile_w
                y0 = row * args.tile_h
                box = (x0, y0, x0 + args.tile_w, y0 + args.tile_h)

                g_norm = sheet.crop(box)
                g_inv = sheet_inv.crop(box)
                g_norm.save(out_norm / f"{idx:04d}_{idx:04X}.png")
                g_inv.save(out_inv / f"{idx:04d}_{idx:04X}.png")

                ch = token_map.get(idx, "")
                known = 1 if ch else 0
                w.writerow([idx, f"{idx:04X}", row, col, ch, known])

                if ch:
                    ttf_cell = render_ttf_cell(ch, args.tile_w, font)
                    pair = Image.new("L", (args.tile_w * 2 + 1, args.tile_h), 255)
                    pair.paste(g_norm, (0, 0))
                    pair.paste(ttf_cell, (args.tile_w + 1, 0))
                    tag = safe_char_tag(ch)
                    p = out_pairs / f"{idx:04d}_{idx:04X}_{tag}.png"
                    pair.save(p)
                    pair_files.append(p)

    build_contact_sheet(pair_files, out_dir / "pairs_contact_sheet.png")

    print(f"sheet={args.sheet}")
    print(f"tiles={args.cols * args.rows}")
    print(f"out_dir={out_dir}")
    print(f"mapping_csv={mapping_csv}")
    print(f"pairs={len(pair_files)}")


if __name__ == "__main__":
    main()
