#!/usr/bin/env python3
import argparse
import csv
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="OCR ingame screenshots for Langrisser V dialogue anchoring.")
    p.add_argument("--input-dir", default="work/ingame")
    p.add_argument("--out-csv", default="work/scen_analysis/ingame_ocr.csv")
    p.add_argument("--out-txt", default="")
    p.add_argument("--lang", default="jpn")
    return p.parse_args()


def preprocess_dialogue_roi(img: Image.Image) -> Image.Image:
    w, h = img.size
    # Heuristic ROI that works for desktop screenshots containing centered PS1 frame.
    crop = img.crop((int(w * 0.18), int(h * 0.52), int(w * 0.82), int(h * 0.88)))
    g = ImageOps.grayscale(crop)
    g = ImageEnhance.Contrast(g).enhance(2.5)
    bw = g.point(lambda p: 255 if p > 150 else 0)
    bw = bw.resize((bw.size[0] * 2, bw.size[1] * 2), Image.Resampling.NEAREST)
    return bw


def run_ocr(image_path: Path, lang: str) -> str:
    out = subprocess.run(
        ["tesseract", str(image_path), "stdout", "-l", lang, "--psm", "6"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    return (out.stdout or "").strip()


def clean_text(txt: str) -> str:
    # Keep mostly Japanese + punctuation and normalize whitespace.
    lines = []
    for raw in txt.splitlines():
        s = raw.strip()
        if not s:
            continue
        s = re.sub(r"[^\u3000-\u30FF\u4E00-\u9FFF0-9A-Za-z、。・ー！？「」（）\s]", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        if s:
            lines.append(s)
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir)
    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path("work/ocr2")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    files = sorted(input_dir.glob("*.png"), key=lambda p: p.stat().st_mtime)
    for f in files:
        img = Image.open(f).convert("RGB")
        proc = preprocess_dialogue_roi(img)
        proc_path = tmp_dir / f"{f.stem}_dialog_bw.png"
        proc.save(proc_path)
        raw = run_ocr(proc_path, args.lang)
        cleaned = clean_text(raw)
        rows.append(
            {
                "file": f.name,
                "mtime": int(f.stat().st_mtime),
                "ocr_raw": raw.replace("\n", "\\n"),
                "ocr_cleaned": cleaned.replace("\n", "\\n"),
            }
        )

    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "mtime", "ocr_raw", "ocr_cleaned"])
        w.writeheader()
        w.writerows(rows)

    if args.out_txt:
        out_txt = Path(args.out_txt)
        out_txt.parent.mkdir(parents=True, exist_ok=True)
        with out_txt.open("w", encoding="utf-8") as fh:
            for i, r in enumerate(rows, 1):
                fh.write(f"[{i:03d}] {r['file']}\n")
                cleaned = r["ocr_cleaned"].replace("\\n", "\n")
                fh.write(cleaned + "\n\n")

    print(f"wrote {out_csv} ({len(rows)} rows)")
    if args.out_txt:
        print(f"wrote {args.out_txt}")


if __name__ == "__main__":
    main()
