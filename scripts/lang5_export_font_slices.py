#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path
import shutil
from typing import Dict, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont
import pytesseract
from pytesseract import Output


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


def upscale_tile(tile: Image.Image, target: int) -> Image.Image:
    return tile.resize((target, target), Image.NEAREST)


def has_ink(tile: Image.Image) -> bool:
    # Tiles are black glyph on white background after feidian export.
    return tile.getbbox() is not None and tile.getextrema()[0] < 255


def ocr_single(tile: Image.Image, lang: str, psm: int) -> Tuple[str, float]:
    cfg = f"--oem 1 --psm {psm}"
    data = pytesseract.image_to_data(tile, lang=lang, config=cfg, output_type=Output.DICT)
    best_txt = ""
    best_conf = -1.0
    for txt, conf_s in zip(data.get("text", []), data.get("conf", [])):
        txt = (txt or "").strip()
        if not txt:
            continue
        try:
            conf = float(conf_s)
        except Exception:
            conf = -1.0
        if conf > best_conf:
            best_conf = conf
            best_txt = txt
    if best_txt:
        best_txt = best_txt[0]
    return best_txt, best_conf


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
    ap.add_argument("--ttf-size", type=int, default=64)
    ap.add_argument("--pair-size", type=int, default=64)
    ap.add_argument("--ocr-lang", default="jpn+eng")
    ap.add_argument("--ocr-psm", type=int, default=10)
    ap.add_argument("--no-ocr", action="store_true")
    ap.add_argument("--out-dir", default="work/font_export")
    ap.add_argument("--clean-pairs", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_norm = out_dir / "glyphs_normal"
    out_inv = out_dir / "glyphs_inverted"
    out_pairs = out_dir / "pairs_game_vs_ttf"
    out_norm.mkdir(parents=True, exist_ok=True)
    out_inv.mkdir(parents=True, exist_ok=True)
    out_pairs.mkdir(parents=True, exist_ok=True)
    if args.clean_pairs:
        for p in sorted(out_pairs.glob("*")):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                shutil.rmtree(p)

    sheet = Image.open(args.sheet).convert("L")
    sheet_inv = Image.open(args.sheet_inv).convert("L")
    token_map = load_token_map(Path(args.token_map))

    font = get_font(Path(args.ttf) if args.ttf else None, size=args.ttf_size)

    mapping_csv = out_dir / "glyph_index_to_utf8.csv"
    ocr_csv = out_dir / "glyph_index_to_utf8_ocr_full.csv"
    pair_files = []

    with mapping_csv.open("w", newline="", encoding="utf-8") as f, ocr_csv.open(
        "w", newline="", encoding="utf-8"
    ) as f_ocr:
        w = csv.writer(f)
        w_ocr = csv.writer(f_ocr)
        w.writerow(["index_dec", "index_hex", "row", "col", "utf8_char", "known"])
        w_ocr.writerow(
            [
                "index_dec",
                "index_hex",
                "row",
                "col",
                "utf8_char",
                "source",
                "ocr_conf",
                "ocr_normal",
                "ocr_inv",
            ]
        )
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

                ocr_norm_char, ocr_norm_conf = "", -1.0
                ocr_inv_char, ocr_inv_conf = "", -1.0
                up_norm = upscale_tile(g_norm, args.pair_size)
                up_inv = upscale_tile(g_inv, args.pair_size)

                if args.no_ocr:
                    src = "token_map" if ch else "none"
                    conf = -1.0
                else:
                    if has_ink(g_norm):
                        ocr_norm_char, ocr_norm_conf = ocr_single(up_norm, args.ocr_lang, args.ocr_psm)
                        ocr_inv_char, ocr_inv_conf = ocr_single(up_inv, args.ocr_lang, args.ocr_psm)

                    if not ch:
                        if ocr_inv_conf > ocr_norm_conf and ocr_inv_char:
                            ch = ocr_inv_char
                            src = "ocr_inv"
                            conf = ocr_inv_conf
                        elif ocr_norm_char:
                            ch = ocr_norm_char
                            src = "ocr_norm"
                            conf = ocr_norm_conf
                        else:
                            ch = ""
                            src = "none"
                            conf = -1.0
                    else:
                        src = "manual"
                        conf = -1.0

                w_ocr.writerow(
                    [idx, f"{idx:04X}", row, col, ch, src, f"{conf:.2f}", ocr_norm_char, ocr_inv_char]
                )

                if ch:
                    ttf_cell = render_ttf_cell(ch, args.pair_size, font)
                    pair = Image.new("L", (args.pair_size * 2 + 8, args.pair_size), 255)
                    # For easier visual comparison keep game glyph black-on-white.
                    pair.paste(up_inv, (0, 0))
                    pair.paste(ttf_cell, (args.pair_size + 8, 0))
                    # File names are font indices so lexical FS sorting == index order.
                    p = out_pairs / f"{idx:04d}.png"
                    pair.save(p)
                    pair_files.append(p)

    build_contact_sheet(pair_files, out_dir / "pairs_contact_sheet.png")

    print(f"sheet={args.sheet}")
    print(f"tiles={args.cols * args.rows}")
    print(f"out_dir={out_dir}")
    print(f"mapping_csv={mapping_csv}")
    print(f"ocr_csv={ocr_csv}")
    print(f"pairs={len(pair_files)}")


if __name__ == "__main__":
    main()
