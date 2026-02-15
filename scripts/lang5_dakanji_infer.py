#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path

import numpy as np
from PIL import Image
import tensorflow as tf


def load_labels(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    lines = [s.strip() for s in raw.splitlines() if s.strip()]
    # DaKanji release sometimes stores labels as one long string
    # of characters instead of one label per line.
    if len(lines) == 1 and len(lines[0]) > 1000:
        return list(lines[0])
    return [s[0] if s else "" for s in lines]


def load_groups(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def tile_from_sheet(sheet: Image.Image, idx: int) -> Image.Image:
    cols = sheet.width // 12
    r, c = divmod(idx, cols)
    return sheet.crop((c * 12, r * 12, (c + 1) * 12, (r + 1) * 12))


def prep_input(tile: Image.Image, h: int, w: int, dtype: np.dtype) -> np.ndarray:
    # model expects grayscale image; game atlas is white glyph on black
    img = tile.resize((w, h), Image.BILINEAR).convert("L")
    x = np.array(img, dtype=np.float32) / 255.0
    # keep white glyph as high activation; add channel/batch dims
    x = x.reshape(1, h, w, 1)
    if dtype == np.uint8:
        x = (x * 255.0).astype(np.uint8)
    else:
        x = x.astype(np.float32)
    return x


def main() -> None:
    ap = argparse.ArgumentParser(description="Infer Japanese glyph candidates with DaKanji tflite model.")
    ap.add_argument("--model", default="external/dakanji_release/v1.2/tflite/model.tflite")
    ap.add_argument("--labels", default="external/dakanji_release/v1.2/labels.txt")
    ap.add_argument("--groups-report", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--sheet-inv", default="work/font_probe/l512x12qg8_inv_12x12.png")
    ap.add_argument("--out-csv", default="work/font_export/grouped/unconfirmed_dakanji_candidates.csv")
    ap.add_argument("--topk", type=int, default=10)
    ap.add_argument("--exclude-confirmed", action="store_true", default=True)
    args = ap.parse_args()

    labels = load_labels(Path(args.labels))
    rows = load_groups(Path(args.groups_report))

    confirmed_chars = {
        (r.get("char") or "")[:1]
        for r in rows
        if r.get("group") == "confirmed" and (r.get("char") or "").strip()
    }

    # map label index -> char
    label_chars = [lb[:1] if lb else "" for lb in labels]

    sheet = Image.open(args.sheet_inv).convert("L")

    intr = tf.lite.Interpreter(model_path=args.model)
    # DaKanji tflite is dynamic in spatial dims; default can be 1x1.
    # Use a practical inference size.
    intr.resize_tensor_input(0, [1, 64, 64, 1], strict=False)
    intr.allocate_tensors()
    in_info = intr.get_input_details()[0]
    out_info = intr.get_output_details()[0]
    _, h, w, _ = in_info["shape"]
    in_dtype = in_info["dtype"]

    rec_rows = []
    for r in rows:
        if r.get("group") != "unconfirmed":
            continue
        idx = int(r["index_dec"])
        tile = tile_from_sheet(sheet, idx)
        x = prep_input(tile, int(h), int(w), in_dtype)
        intr.set_tensor(in_info["index"], x)
        intr.invoke()
        y = intr.get_tensor(out_info["index"]).reshape(-1).astype(np.float32)
        order = np.argsort(-y)

        picks = []
        for li in order:
            ch = label_chars[int(li)]
            if not ch:
                continue
            if args.exclude_confirmed and ch in confirmed_chars:
                continue
            picks.append((ch, float(y[int(li)])))
            if len(picks) >= args.topk:
                break

        guess_char = picks[0][0] if picks else ""
        guess_score = picks[0][1] if picks else 0.0
        rec_rows.append(
            {
                "index_dec": str(idx),
                "index_hex": f"{idx:04X}",
                "guess_char": guess_char,
                "guess_score": f"{guess_score:.6f}",
                "top_candidates": " | ".join(f"{c}:{s:.6f}" for c, s in picks),
            }
        )

    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        fields = ["index_dec", "index_hex", "guess_char", "guess_score", "top_candidates"]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rec_rows)

    print(f"model={args.model}")
    print(f"input_shape={in_info['shape']} dtype={in_dtype}")
    print(f"labels={len(labels)}")
    print(f"rows_out={len(rec_rows)}")
    print(f"out_csv={out}")


if __name__ == "__main__":
    main()
