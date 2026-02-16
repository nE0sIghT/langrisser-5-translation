#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def load_rows(path: Path) -> list[dict[str, str]]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append(
                {
                    "index_dec": (r.get("index_dec") or "").strip(),
                    "index_hex": (r.get("index_hex") or "").strip(),
                    "group": (r.get("group") or "").strip(),
                    "char": (r.get("char") or "").strip(),
                    "source": (r.get("source") or "").strip(),
                }
            )
    return rows


def save_rows(path: Path, rows: list[dict[str, str]]) -> None:
    fields = ["index_dec", "index_hex", "group", "char", "source"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def build_jis0208_order() -> list[str]:
    seq: list[str] = []
    for ku in range(1, 95):
        for ten in range(1, 95):
            bs = b"\x1b$B" + bytes([0x20 + ku, 0x20 + ten]) + b"\x1b(B"
            try:
                ch = bs.decode("iso2022_jp")
            except Exception:
                continue
            if len(ch) == 1:
                seq.append(ch)
    return seq


def pick_font(path: str) -> str:
    if path and Path(path).exists():
        return path
    for cand in [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    ]:
        if Path(cand).exists():
            return cand
    raise SystemExit("No CJK font found.")


def tile_mask_12(img: Image.Image, idx: int) -> np.ndarray:
    cols = img.width // 12
    r, c = divmod(idx, cols)
    t = img.crop((c * 12, r * 12, (c + 1) * 12, (r + 1) * 12))
    a = np.array(t, dtype=np.uint8)
    return a > 127


def char_mask_12(ch: str, font: ImageFont.FreeTypeFont) -> np.ndarray:
    img = Image.new("L", (12, 12), 255)
    d = ImageDraw.Draw(img)
    bb = d.textbbox((0, 0), ch, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x = (12 - tw) // 2 - bb[0]
    y = (12 - th) // 2 - bb[1]
    d.text((x, y), ch, font=font, fill=0)
    return np.array(img, dtype=np.uint8) < 128


def shift_mask(m: np.ndarray, dx: int, dy: int) -> np.ndarray:
    o = np.zeros_like(m, dtype=bool)
    x0, y0 = max(0, dx), max(0, dy)
    x1, y1 = min(12, 12 + dx), min(12, 12 + dy)
    sx0, sy0 = max(0, -dx), max(0, -dy)
    sx1, sy1 = sx0 + (x1 - x0), sy0 + (y1 - y0)
    if x1 > x0 and y1 > y0:
        o[y0:y1, x0:x1] = m[sy0:sy1, sx0:sx1]
    return o


def iou(a: np.ndarray, b: np.ndarray) -> float:
    inter = np.logical_and(a, b).sum()
    uni = np.logical_or(a, b).sum()
    if uni == 0:
        return 0.0
    return float(inter) / float(uni)


def best_iou(a: np.ndarray, b: np.ndarray) -> float:
    best = 0.0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            best = max(best, iou(a, shift_mask(b, dx, dy)))
    return best


def contiguous_runs(xs: list[int]) -> list[list[int]]:
    if not xs:
        return []
    xs = sorted(xs)
    runs = [[xs[0]]]
    for x in xs[1:]:
        if x == runs[-1][-1] + 1:
            runs[-1].append(x)
        else:
            runs.append([x])
    return runs


def main() -> None:
    ap = argparse.ArgumentParser(description="Constrained unconfirmed recognition with JIS-order anchors.")
    ap.add_argument("--groups-report", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--sheet-inv", default="work/font_probe/l512x12qg8_inv_12x12.png")
    ap.add_argument("--out-report", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--out-csv", default="work/font_export/grouped/unconfirmed_constrained_candidates.csv")
    ap.add_argument("--font", default="")
    ap.add_argument("--topk", type=int, default=10)
    ap.add_argument("--min-score", type=float, default=0.40)
    args = ap.parse_args()

    rows = load_rows(Path(args.groups_report))
    img = Image.open(args.sheet_inv).convert("L")
    font = ImageFont.truetype(pick_font(args.font), size=12)

    jis = build_jis0208_order()
    rank = {ch: i for i, ch in enumerate(jis)}

    confirmed = {}
    for r in rows:
        if r["group"] != "confirmed":
            continue
        ch = (r["char"] or "")[:1]
        if ch and ch in rank:
            confirmed[int(r["index_dec"])] = ch

    # Candidate charset: JIS only, but remove already confirmed chars.
    confirmed_chars = set(confirmed.values())
    cand_chars = [c for c in jis if c not in confirmed_chars]
    cand_masks = [char_mask_12(c, font) for c in cand_chars]

    un_indices = [int(r["index_dec"]) for r in rows if r["group"] == "unconfirmed"]
    runs = contiguous_runs(un_indices)

    rec_records = []
    row_by_idx = {int(r["index_dec"]): r for r in rows}

    for run in runs:
        left = run[0] - 1
        right = run[-1] + 1
        left_ch = confirmed.get(left, "")
        right_ch = confirmed.get(right, "")
        use_interp = bool(left_ch and right_ch and rank[right_ch] > rank[left_ch])
        lrank = rank[left_ch] if left_ch else -1
        rrank = rank[right_ch] if right_ch else -1
        n = len(run)

        for j, idx in enumerate(run, start=1):
            gm = tile_mask_12(img, idx)
            scores = np.array([best_iou(gm, cm) for cm in cand_masks], dtype=np.float32)
            top_idx = np.argsort(-scores)[: args.topk]
            top = [(cand_chars[k], float(scores[k])) for k in top_idx]

            choice = top[0][0]
            score = top[0][1]
            source = "vision_constrained"
            if use_interp:
                target = lrank + (rrank - lrank) * (j / (n + 1))
                reranked = sorted(top, key=lambda t: (abs(rank.get(t[0], 10**9) - target), -t[1]))
                choice, score = reranked[0]
                source = "vision_jis_interp"

            if score < args.min_score:
                source = "vision_low"

            rb = row_by_idx[idx]
            rb["char"] = choice
            rb["source"] = source

            rec_records.append(
                {
                    "index_dec": str(idx),
                    "index_hex": f"{idx:04X}",
                    "guess_char": choice,
                    "guess_score": f"{score:.5f}",
                    "source": source,
                    "top_candidates": " | ".join(f"{c}:{s:.4f}" for c, s in top),
                    "left_anchor": left_ch,
                    "right_anchor": right_ch,
                }
            )

    save_rows(Path(args.out-report), rows)
    with Path(args.out_csv).open("w", newline="", encoding="utf-8") as fh:
        fields = [
            "index_dec",
            "index_hex",
            "guess_char",
            "guess_score",
            "source",
            "top_candidates",
            "left_anchor",
            "right_anchor",
        ]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rec_records)

    print(f"updated_report={args.out_report}")
    print(f"candidates={args.out_csv}")
    print(f"updated_unconfirmed={len(rec_records)}")


if __name__ == "__main__":
    main()
