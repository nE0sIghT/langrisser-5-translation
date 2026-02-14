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
    p.add_argument("--debug-dir", default="")
    p.add_argument("--lang", default="jpn")
    return p.parse_args()


def detect_dialogue_box(img: Image.Image) -> tuple[int, int, int, int, str]:
    w, h = img.size
    rgb = img.convert("RGB")
    px = rgb.load()

    # Search in lower part where textbox appears.
    x0, y0 = int(w * 0.05), int(h * 0.48)
    x1, y1 = int(w * 0.95), int(h * 0.98)

    xs = []
    ys = []
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b = px[x, y]
            # Gold frame heuristic (works for the tutorial dialogue frame).
            if r >= 120 and g >= 90 and b <= 80:
                xs.append(x)
                ys.append(y)

    if len(xs) > 500:
        bx0, bx1 = min(xs), max(xs)
        by0, by1 = min(ys), max(ys)
        bw, bh = bx1 - bx0 + 1, by1 - by0 + 1
        # Basic sanity to avoid accidental tiny detections.
        if bw > int(w * 0.35) and bh > int(h * 0.12):
            # Dialogue frame is expected in lower half and fairly wide.
            if by0 < int(h * 0.40) or by1 < int(h * 0.58):
                return 0, 0, w - 1, h - 1, "full_screen"
            # False-positive guard: menus often produce near-full-width boxes.
            if bw > int(w * 0.86):
                return 0, 0, w - 1, h - 1, "full_screen"
            # Dialogue frame should not hug the bottom edge.
            if by1 > int(h * 0.82):
                return 0, 0, w - 1, h - 1, "full_screen"
            ar = bw / max(1, bh)
            if ar < 1.8 or ar > 5.5:
                return 0, 0, w - 1, h - 1, "full_screen"
            pad = 6
            bx0 = max(0, bx0 - pad)
            by0 = max(0, by0 - pad)
            bx1 = min(w - 1, bx1 + pad)
            by1 = min(h - 1, by1 + pad)
            # Validate dark-blue textbox interior to reject false positives
            # from non-dialogue menus/class screens.
            inside = 0
            navy = 0
            for yy in range(by0 + 4, by1 - 3):
                for xx in range(bx0 + 4, bx1 - 3):
                    r, g, b = px[xx, yy]
                    inside += 1
                    if r < 80 and g < 90 and 40 < b < 170:
                        navy += 1
            navy_ratio = (navy / inside) if inside else 0.0
            if navy_ratio < 0.08:
                return 0, 0, w - 1, h - 1, "full_screen"
            return bx0, by0, bx1, by1, "gold_box"

    # Fallback ROI.
    return 0, 0, w - 1, h - 1, "full_screen"


def preprocess_dialogue_roi(img: Image.Image) -> tuple[Image.Image, tuple[int, int, int, int], str]:
    x0, y0, x1, y1, method = detect_dialogue_box(img)
    crop = img.crop((x0, y0, x1 + 1, y1 + 1))
    if method == "gold_box":
        # Slight inward trim to reduce decorative frame noise.
        cw, ch = crop.size
        trim_l = int(cw * 0.02)
        trim_r = int(cw * 0.02)
        trim_t = int(ch * 0.10)
        trim_b = int(ch * 0.14)
        crop = crop.crop((trim_l, trim_t, max(trim_l + 1, cw - trim_r), max(trim_t + 1, ch - trim_b)))

    g = ImageOps.grayscale(crop)
    g = ImageEnhance.Contrast(g).enhance(2.5)
    bw = g.point(lambda p: 255 if p > 150 else 0)
    bw = bw.resize((bw.size[0] * 2, bw.size[1] * 2), Image.Resampling.NEAREST)
    return bw, (x0, y0, x1, y1), method


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
    debug_dir = Path(args.debug_dir) if args.debug_dir else None
    if debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    files = sorted(input_dir.glob("*.png"), key=lambda p: p.stat().st_mtime)
    for i, f in enumerate(files, 1):
        img = Image.open(f).convert("RGB")
        proc, box, method = preprocess_dialogue_roi(img)
        proc_path = tmp_dir / f"{f.stem}_dialog_bw.png"
        proc.save(proc_path)
        raw = run_ocr(proc_path, args.lang)
        cleaned = clean_text(raw)
        x0, y0, x1, y1 = box
        rows.append(
            {
                "file": f.name,
                "mtime": int(f.stat().st_mtime),
                "crop_method": method,
                "crop_box": f"{x0},{y0},{x1},{y1}",
                "ocr_raw": raw.replace("\n", "\\n"),
                "ocr_cleaned": cleaned.replace("\n", "\\n"),
            }
        )
        if debug_dir:
            # Draw bbox on original and save side-by-side comparison.
            marked = img.copy()
            mp = marked.load()
            for x in range(x0, x1 + 1):
                if 0 <= y0 < marked.size[1]:
                    mp[x, y0] = (255, 0, 0)
                if 0 <= y1 < marked.size[1]:
                    mp[x, y1] = (255, 0, 0)
            for y in range(y0, y1 + 1):
                if 0 <= x0 < marked.size[0]:
                    mp[x0, y] = (255, 0, 0)
                if 0 <= x1 < marked.size[0]:
                    mp[x1, y] = (255, 0, 0)

            # Recreate unbinarized crop preview for visual QA.
            vis_crop = img.crop((x0, y0, x1 + 1, y1 + 1))
            pair_w = marked.size[0] + vis_crop.size[0]
            pair_h = max(marked.size[1], vis_crop.size[1])
            pair = Image.new("RGB", (pair_w, pair_h), (20, 20, 20))
            pair.paste(marked, (0, 0))
            pair.paste(vis_crop, (marked.size[0], 0))
            pair_name = f"{i:03d}_{method}_{f.name}"
            pair.save(debug_dir / pair_name)

    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["file", "mtime", "crop_method", "crop_box", "ocr_raw", "ocr_cleaned"],
        )
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
