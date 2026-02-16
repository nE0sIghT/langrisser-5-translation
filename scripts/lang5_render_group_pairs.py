#!/usr/bin/env python3
import argparse
import csv
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def pick_font(path: str, size: int):
    if path and Path(path).exists():
        return ImageFont.truetype(path, size=size)
    for cand in [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    ]:
        if Path(cand).exists():
            return ImageFont.truetype(cand, size=size)
    return ImageFont.load_default()


def render_ttf(ch: str, size: int, font) -> Image.Image:
    img = Image.new("L", (size, size), 255)
    if not ch:
        return img
    d = ImageDraw.Draw(img)
    bb = d.textbbox((0, 0), ch, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x = (size - tw) // 2 - bb[0]
    y = (size - th) // 2 - bb[1]
    d.text((x, y), ch, font=font, fill=0)
    return img


def xbrz64(tile12: Image.Image, size: int = 64) -> Image.Image:
    with tempfile.TemporaryDirectory(prefix="lang5_pair_") as td:
        inp = Path(td) / "in.png"
        out = Path(td) / "out.png"
        tile12.save(inp)
        try:
            subprocess.run(["xbrzscale", "6", str(inp), str(out)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            up = Image.open(out).convert("L")
        except Exception:
            up = tile12.resize((72, 72), Image.NEAREST)
        return up.resize((size, size), Image.NEAREST)


def main() -> None:
    ap = argparse.ArgumentParser(description="Render pair images for confirmed/unconfirmed/symbol groups.")
    ap.add_argument("--groups-report", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--sheet-inv", default="work/font_probe/l512x12qg8_inv_12x12.png")
    ap.add_argument("--out-dir", default="work/font_export/grouped")
    ap.add_argument("--pair-size", type=int, default=64)
    ap.add_argument("--font", default="")
    ap.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 1))
    ap.add_argument("--ocr-xbrz-report", default="work/font_export/grouped_xbrz/groups_report.csv")
    ap.add_argument("--ocr-raw-report", default="work/font_export/grouped_raw/groups_report.csv")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.groups_report, encoding="utf-8")))
    ocr_xbrz = {}
    ocr_raw = {}
    if Path(args.ocr_xbrz_report).exists():
        ocr_xbrz = {int(r["index_dec"]): (r.get("char") or "")[:1] for r in csv.DictReader(open(args.ocr_xbrz_report, encoding="utf-8"))}
    if Path(args.ocr_raw_report).exists():
        ocr_raw = {int(r["index_dec"]): (r.get("char") or "")[:1] for r in csv.DictReader(open(args.ocr_raw_report, encoding="utf-8"))}

    img = Image.open(args.sheet_inv).convert("L")
    cols = img.width // 12
    font = pick_font(args.font, args.pair_size)

    out = Path(args.out_dir)
    mapping = {
        "confirmed": out / "pairs_confirmed",
        "unconfirmed": out / "pairs_unconfirmed",
        "symbol": out / "pairs_symbol",
    }
    for d in mapping.values():
        d.mkdir(parents=True, exist_ok=True)
        for p in d.glob("*.png"):
            p.unlink()

    def render_one(idx: int, grp: str, ch: str, tile: Image.Image) -> str:
        # Symbols are rendered as a single game glyph (no TTF pair).
        if grp == "symbol":
            single = xbrz64(tile, args.pair_size)
            single.save(mapping[grp] / f"{idx:04d}.png")
            return grp

        top_left = xbrz64(tile, args.pair_size)
        bottom_left = tile.resize((args.pair_size, args.pair_size), Image.NEAREST)
        if grp == "unconfirmed":
            # Unconfirmed right column uses OCR variants:
            # top-right from xBRZ OCR pass, bottom-right from raw OCR pass.
            top_right = render_ttf(ocr_xbrz.get(idx, ""), args.pair_size, font)
            bottom_right = render_ttf(ocr_raw.get(idx, ""), args.pair_size, font)
        else:
            top_right = render_ttf(ch, args.pair_size, font)
            bottom_right = render_ttf(ch, args.pair_size, font)

        # Square 2x2 layout:
        # [xbrz game | ttf]
        # [raw game  | ttf]
        pair = Image.new("L", (args.pair_size * 2 + 8, args.pair_size * 2 + 8), 255)
        pair.paste(top_left, (0, 0))
        pair.paste(top_right, (args.pair_size + 8, 0))
        pair.paste(bottom_left, (0, args.pair_size + 8))
        pair.paste(bottom_right, (args.pair_size + 8, args.pair_size + 8))
        pair.save(mapping[grp] / f"{idx:04d}.png")
        return grp

    futures = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        for r in rows:
            grp = r.get("group", "")
            if grp not in mapping:
                continue
            idx = int(r["index_dec"])
            ch = (r.get("char") or "")[:1]
            rr, cc = divmod(idx, cols)
            tile = img.crop((cc * 12, rr * 12, (cc + 1) * 12, (rr + 1) * 12)).copy()
            futures.append(ex.submit(render_one, idx, grp, ch, tile))

        for f in as_completed(futures):
            _ = f.result()

    print("done")
    for grp, d in mapping.items():
        print(grp, len(list(d.glob("*.png"))), d)


if __name__ == "__main__":
    main()
