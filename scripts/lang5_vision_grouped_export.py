#!/usr/bin/env python3
import argparse
import csv
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def available_fonts(user_font: str) -> list[str]:
    out: list[str] = []
    if user_font:
        out.append(user_font)
    for cand in [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if Path(cand).exists():
            out.append(cand)
    return out


def load_groups_report(path: Path) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            clean = {
                "index_dec": (row.get("index_dec") or "").strip(),
                "index_hex": (row.get("index_hex") or "").strip(),
                "group": (row.get("group") or "").strip(),
                "char": (row.get("char") or ""),
                "source": (row.get("source") or "").strip(),
            }
            if clean["index_dec"] and clean["group"]:
                out.append(clean)
    return out


def save_groups_report(path: Path, rows: list[dict[str, str]]) -> None:
    fields = ["index_dec", "index_hex", "group", "char", "source"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=fields)
        wr.writeheader()
        wr.writerows(rows)


def char_mask_12(ch: str, font: ImageFont.FreeTypeFont) -> np.ndarray:
    img = Image.new("L", (12, 12), 255)
    d = ImageDraw.Draw(img)
    bbox = d.textbbox((0, 0), ch, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (12 - tw) // 2 - bbox[0]
    y = (12 - th) // 2 - bbox[1]
    d.text((x, y), ch, font=font, fill=0)
    arr = np.array(img, dtype=np.uint8)
    return arr < 128


def shift_mask(mask: np.ndarray, dx: int, dy: int) -> np.ndarray:
    out = np.zeros_like(mask, dtype=bool)
    x0 = max(0, dx)
    y0 = max(0, dy)
    x1 = min(mask.shape[1], mask.shape[1] + dx)
    y1 = min(mask.shape[0], mask.shape[0] + dy)
    sx0 = max(0, -dx)
    sy0 = max(0, -dy)
    sx1 = sx0 + (x1 - x0)
    sy1 = sy0 + (y1 - y0)
    if x1 > x0 and y1 > y0:
        out[y0:y1, x0:x1] = mask[sy0:sy1, sx0:sx1]
    return out


def iou_best(a: np.ndarray, b: np.ndarray) -> float:
    best = 0.0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            bs = shift_mask(b, dx, dy)
            inter = np.logical_and(a, bs).sum()
            union = np.logical_or(a, bs).sum()
            if union == 0:
                continue
            s = float(inter) / float(union)
            if s > best:
                best = s
    return best


def build_jis0208_chars() -> list[str]:
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


def build_candidate_chars(rows: list[dict[str, str]]) -> list[str]:
    s: set[str] = set()
    for row in rows:
        ch = (row.get("char") or "").strip()
        if ch:
            s.add(ch[0])
    for cp in range(0x20, 0x7F):
        s.add(chr(cp))
    for cp in range(0x3040, 0x30FF + 1):
        s.add(chr(cp))
    for cp in range(0xFF66, 0xFF9F + 1):
        s.add(chr(cp))
    for ch in build_jis0208_chars():
        s.add(ch)
    s.discard("\x00")
    return sorted(s)


def choose_best_font(font_paths: list[str], rows: list[dict[str, str],], game_masks: dict[int, np.ndarray]) -> str:
    # Use confirmed rows with mapped chars to score style fit.
    samples: list[tuple[int, str]] = []
    for row in rows:
        if row.get("group") != "confirmed":
            continue
        ch = (row.get("char") or "").strip()
        if not ch:
            continue
        idx = int(row["index_dec"])
        samples.append((idx, ch[0]))
        if len(samples) >= 220:
            break
    if not samples:
        return font_paths[0]

    best_font = font_paths[0]
    best_score = -1.0
    for fp in font_paths:
        font = ImageFont.truetype(fp, size=12)
        total = 0.0
        count = 0
        for idx, ch in samples:
            gm = game_masks[idx]
            cm = char_mask_12(ch, font)
            total += iou_best(gm, cm)
            count += 1
        score = total / max(1, count)
        if score > best_score:
            best_score = score
            best_font = fp
    return best_font


def xbrz_enlarge(tile: Image.Image, scale: int = 5, size: int = 128) -> Image.Image:
    with tempfile.TemporaryDirectory(prefix="lang5_xbrz_") as td:
        in_p = Path(td) / "in.png"
        out_p = Path(td) / "out.png"
        tile.save(in_p)
        try:
            subprocess.run(
                ["xbrzscale", str(scale), str(in_p), str(out_p)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            up = Image.open(out_p).convert("L")
        except Exception:
            up = tile.resize((12 * scale, 12 * scale), Image.NEAREST)
        canvas = Image.new("L", (size, size), 255)
        canvas.paste(up, ((size - up.width) // 2, (size - up.height) // 2))
        return canvas


def render_ttf_cell(ch: str, size: int, font: ImageFont.FreeTypeFont) -> Image.Image:
    img = Image.new("L", (size, size), 255)
    if not ch:
        return img
    d = ImageDraw.Draw(img)
    bbox = d.textbbox((0, 0), ch, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (size - tw) // 2 - bbox[0]
    y = (size - th) // 2 - bbox[1]
    d.text((x, y), ch, font=font, fill=0)
    return img


def main() -> None:
    ap = argparse.ArgumentParser(description="Vision-based Lang5 glyph recognition and grouped pair export.")
    ap.add_argument("--groups-report", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--sheet-inv", default="work/font_probe/l512x12qg8_inv_12x12.png")
    ap.add_argument("--out-dir", default="work/font_export/grouped")
    ap.add_argument("--pair-size", type=int, default=128)
    ap.add_argument("--topk", type=int, default=5)
    ap.add_argument("--font", default="")
    ap.add_argument("--min-iou", type=float, default=0.30)
    args = ap.parse_args()

    rows = load_groups_report(Path(args.groups_report))
    out_dir = Path(args.out_dir)
    d_conf = out_dir / "pairs_confirmed"
    d_un = out_dir / "pairs_unconfirmed"
    d_sym = out_dir / "pairs_symbol"
    for d in (d_conf, d_un, d_sym):
        d.mkdir(parents=True, exist_ok=True)
        for p in d.glob("*.png"):
            p.unlink()

    img = Image.open(args.sheet_inv).convert("L")
    cols = img.width // 12
    game_masks: dict[int, np.ndarray] = {}
    for row in rows:
        idx = int(row["index_dec"])
        r, c = divmod(idx, cols)
        tile = img.crop((c * 12, r * 12, (c + 1) * 12, (r + 1) * 12))
        arr = np.array(tile, dtype=np.uint8)
        game_masks[idx] = arr > 127  # white glyph on black background

    fonts = available_fonts(args.font)
    if not fonts:
        raise SystemExit("No usable fonts found.")
    best_font_path = choose_best_font(fonts, rows, game_masks)
    font12 = ImageFont.truetype(best_font_path, size=12)
    font_pair = ImageFont.truetype(best_font_path, size=args.pair_size)

    candidates = build_candidate_chars(rows)
    cand_masks = []
    cand_chars = []
    cand_count = []
    for ch in candidates:
        m = char_mask_12(ch, font12)
        if m.sum() == 0:
            continue
        cand_chars.append(ch)
        cand_masks.append(m)
        cand_count.append(int(m.sum()))
    cand_masks_np = np.stack(cand_masks, axis=0)
    cand_count_np = np.array(cand_count, dtype=np.int16)

    # prebuild shifted candidate masks
    shifts = [(-1, -1), (0, -1), (1, -1), (-1, 0), (0, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
    shifted = []
    for dx, dy in shifts:
        mats = np.zeros_like(cand_masks_np, dtype=bool)
        for i in range(cand_masks_np.shape[0]):
            mats[i] = shift_mask(cand_masks_np[i], dx, dy)
        shifted.append(mats.reshape(mats.shape[0], -1))

    # recognition for unconfirmed
    rec_rows: list[dict[str, str]] = []
    for row in rows:
        if row.get("group") != "unconfirmed":
            continue
        idx = int(row["index_dec"])
        gm = game_masks[idx].reshape(-1)
        gcount = int(gm.sum())

        # prefilter by pixel count difference
        keep = np.where(np.abs(cand_count_np - gcount) <= 28)[0]
        if keep.size == 0:
            keep = np.arange(cand_masks_np.shape[0], dtype=np.int32)

        best_scores = np.zeros(keep.shape[0], dtype=np.float32)
        for mats in shifted:
            sub = mats[keep]
            inter = np.logical_and(sub, gm).sum(axis=1)
            union = np.logical_or(sub, gm).sum(axis=1)
            iou = np.divide(inter, np.maximum(union, 1), dtype=np.float32)
            best_scores = np.maximum(best_scores, iou)

        order = np.argsort(-best_scores)
        top = order[: args.topk]
        top_items = []
        for t in top:
            ci = keep[t]
            top_items.append((cand_chars[int(ci)], float(best_scores[int(t)])))

        guess_char = top_items[0][0] if top_items else ""
        guess_score = top_items[0][1] if top_items else 0.0

        row["char"] = guess_char
        row["source"] = "vision" if guess_score >= args.min_iou else "vision_low"
        rec_rows.append(
            {
                "index_dec": str(idx),
                "index_hex": f"{idx:04X}",
                "guess_char": guess_char,
                "guess_iou": f"{guess_score:.5f}",
                "top_candidates": " | ".join(f"{c}:{s:.4f}" for c, s in top_items),
            }
        )

    # write updated report + candidate details
    out_report = out_dir / "groups_report.csv"
    save_groups_report(out_report, rows)
    rec_csv = out_dir / "unconfirmed_vision_candidates.csv"
    with rec_csv.open("w", newline="", encoding="utf-8") as fh:
        fields = ["index_dec", "index_hex", "guess_char", "guess_iou", "top_candidates"]
        wr = csv.DictWriter(fh, fieldnames=fields)
        wr.writeheader()
        wr.writerows(rec_rows)

    # pairs for all three groups (xbrz game glyph + ttf glyph when mapped)
    for row in rows:
        idx = int(row["index_dec"])
        grp = row["group"]
        ch = (row.get("char") or "")[:1]
        r, c = divmod(idx, cols)
        tile = img.crop((c * 12, r * 12, (c + 1) * 12, (r + 1) * 12))
        game_cell = xbrz_enlarge(tile, scale=5, size=args.pair_size)
        ttf_cell = render_ttf_cell(ch, args.pair_size, font_pair)
        pair = Image.new("L", (args.pair_size * 2 + 8, args.pair_size), 255)
        pair.paste(game_cell, (0, 0))
        pair.paste(ttf_cell, (args.pair_size + 8, 0))
        out_name = f"{idx:04d}.png"
        if grp == "confirmed":
            pair.save(d_conf / out_name)
        elif grp == "unconfirmed":
            pair.save(d_un / out_name)
        elif grp == "symbol":
            pair.save(d_sym / out_name)

    print(f"font={best_font_path}")
    print(f"updated_report={out_report}")
    print(f"unconfirmed_candidates={rec_csv}")
    print(f"pairs_confirmed={len(list(d_conf.glob('*.png')))}")
    print(f"pairs_unconfirmed={len(list(d_un.glob('*.png')))}")
    print(f"pairs_symbol={len(list(d_sym.glob('*.png')))}")


if __name__ == "__main__":
    main()
