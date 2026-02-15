#!/usr/bin/env python3
import argparse
import asyncio
import csv
import os
import tempfile
from pathlib import Path

from PIL import Image
import pytesseract
from pytesseract import Output


async def xbrz64(tile: Image.Image) -> Image.Image:
    def _run() -> Image.Image:
        with tempfile.TemporaryDirectory(prefix="lang5_uocr_") as td:
            in_p = Path(td) / "in.png"
            out_p = Path(td) / "out.png"
            tile.save(in_p)
            # 12x12 * 5 = 60x60, then centered into 64x64
            import subprocess

            subprocess.run(
                ["xbrzscale", "5", str(in_p), str(out_p)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            up = Image.open(out_p).convert("L")
            canvas = Image.new("L", (64, 64), 255)
            canvas.paste(up, ((64 - up.width) // 2, (64 - up.height) // 2))
            return canvas

    return await asyncio.to_thread(_run)


def ocr_one(img: Image.Image, lang: str, psm: int):
    d = pytesseract.image_to_data(
        img, lang=lang, config=f"--oem 1 --psm {psm}", output_type=Output.DICT
    )
    best_txt = ""
    best_conf = -1.0
    for txt, conf_s in zip(d.get("text", []), d.get("conf", [])):
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


async def process_index(idx: int, sheet: Image.Image, sheet_inv: Image.Image, cols: int, sem: asyncio.Semaphore, lang: str, psm: int):
    async with sem:
        row, col = divmod(idx, cols)
        box = (col * 12, row * 12, (col + 1) * 12, (row + 1) * 12)
        inv = sheet_inv.crop(box)
        norm = sheet.crop(box)

        inv64 = await xbrz64(inv)
        norm64 = await xbrz64(norm)

        ch_i, cf_i = await asyncio.to_thread(ocr_one, inv64, lang, psm)
        ch_n, cf_n = await asyncio.to_thread(ocr_one, norm64, lang, psm)

        if cf_i >= cf_n:
            ch, cf = ch_i, cf_i
        else:
            ch, cf = ch_n, cf_n

        return {
            "index_dec": idx,
            "index_hex": f"{idx:04X}",
            "ocr_char": ch,
            "ocr_conf": f"{cf:.2f}",
            "ocr_char_norm": ch_n,
            "ocr_conf_norm": f"{cf_n:.2f}",
            "ocr_char_inv": ch_i,
            "ocr_conf_inv": f"{cf_i:.2f}",
        }


async def main_async(args):
    sheet = Image.open(args.sheet).convert("L")
    sheet_inv = Image.open(args.sheet_inv).convert("L")

    if args.indices_file:
        idxs = []
        for line in Path(args.indices_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            idxs.append(int(line))
        idxs = sorted(set(idxs))
    else:
        idxs = [int(p.stem) for p in sorted(Path(args.unconfirmed_dir).glob("*.png"))]
    workers = args.workers or os.cpu_count() or 4
    sem = asyncio.Semaphore(workers)

    tasks = [
        asyncio.create_task(process_index(i, sheet, sheet_inv, args.cols, sem, args.lang, args.psm))
        for i in idxs
    ]

    rows = []
    done = 0
    total = len(tasks)
    for fut in asyncio.as_completed(tasks):
        rows.append(await fut)
        done += 1
        if done % 100 == 0 or done == total:
            print(f"progress {done}/{total}")

    rows.sort(key=lambda r: r["index_dec"])
    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "index_dec",
                "index_hex",
                "ocr_char",
                "ocr_conf",
                "ocr_char_norm",
                "ocr_conf_norm",
                "ocr_char_inv",
                "ocr_conf_inv",
            ],
        )
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out} rows={len(rows)} workers={workers}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", default="work/font_probe/l512x12qg8_12x12.png")
    ap.add_argument("--sheet-inv", default="work/font_probe/l512x12qg8_inv_12x12.png")
    ap.add_argument("--unconfirmed-dir", default="work/font_export/pairs_unconfirmed")
    ap.add_argument("--indices-file", default="")
    ap.add_argument("--out-csv", default="work/font_export/unconfirmed_xbrz64_ocr.csv")
    ap.add_argument("--cols", type=int, default=32)
    ap.add_argument("--lang", default="jpn+eng")
    ap.add_argument("--psm", type=int, default=10)
    ap.add_argument("--workers", type=int, default=0)
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
