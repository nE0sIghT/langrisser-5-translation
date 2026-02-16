#!/usr/bin/env python3
import argparse
import csv
import os
import shutil
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import paddlex as pdx


def load_rows(path: Path) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    with path.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out.append(
                {
                    "index_dec": (r.get("index_dec") or "").strip(),
                    "index_hex": (r.get("index_hex") or "").strip(),
                    "group": (r.get("group") or "").strip(),
                    "char": (r.get("char") or ""),
                    "source": (r.get("source") or "").strip(),
                }
            )
    return out


def save_rows(path: Path, rows: list[dict[str, str]]) -> None:
    fields = ["index_dec", "index_hex", "group", "char", "source"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


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


def tile_from_sheet(sheet: Image.Image, idx: int) -> Image.Image:
    cols = sheet.width // 12
    rr, cc = divmod(idx, cols)
    return sheet.crop((cc * 12, rr * 12, (cc + 1) * 12, (rr + 1) * 12))


def xbrz_up(tile12: Image.Image, size: int) -> Image.Image:
    with tempfile.TemporaryDirectory(prefix="lang5_xbrz_") as td:
        inp = Path(td) / "in.png"
        out = Path(td) / "out.png"
        tile12.save(inp)
        try:
            subprocess.run(
                ["xbrzscale", "6", str(inp), str(out)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            up = Image.open(out).convert("L")
        except Exception:
            up = tile12.resize((72, 72), Image.NEAREST)
        return up.resize((size, size), Image.NEAREST)


def raw_up(tile12: Image.Image, size: int) -> Image.Image:
    return tile12.resize((size, size), Image.NEAREST)


def predict_char(model, img: Image.Image):
    tmp = Path(tempfile.gettempdir()) / f"lang5_dual_{os.getpid()}_{id(img)}.png"
    img.convert("RGB").save(tmp)
    pred = list(model.predict(str(tmp)))
    if not pred:
        return "", 0.0, ""
    text = pred[0].get("rec_text") or ""
    score = float(pred[0].get("rec_score") or 0.0)
    return (text[:1] if text else ""), score, text


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


def render_pairs(rows: list[dict[str, str]], sheet: Image.Image, out_dir: Path, pair_size: int, font) -> None:
    mapping = {
        "confirmed": out_dir / "pairs_confirmed",
        "unconfirmed": out_dir / "pairs_unconfirmed",
        "symbol": out_dir / "pairs_symbol",
    }
    for d in mapping.values():
        d.mkdir(parents=True, exist_ok=True)
        for p in d.glob("*.png"):
            p.unlink()

    for r in rows:
        grp = r.get("group", "")
        if grp not in mapping:
            continue
        idx = int(r["index_dec"])
        ch = (r.get("char") or "")[:1]
        tile = tile_from_sheet(sheet, idx)
        raw = raw_up(tile, pair_size)
        xbz = xbrz_up(tile, pair_size)
        ttf = render_ttf(ch, pair_size, font)

        if grp == "unconfirmed":
            # 3 columns per user request: raw, xbrz, ttf
            pair = Image.new("L", (pair_size * 3 + 16, pair_size), 255)
            pair.paste(raw, (0, 0))
            pair.paste(xbz, (pair_size + 8, 0))
            pair.paste(ttf, (pair_size * 2 + 16, 0))
        else:
            # Keep 2-column layout for other groups: xbrz + ttf
            pair = Image.new("L", (pair_size * 2 + 8, pair_size), 255)
            pair.paste(xbz, (0, 0))
            pair.paste(ttf, (pair_size + 8, 0))
        pair.save(mapping[grp] / f"{idx:04d}.png")


def run_mode(
    mode: str,
    base_rows: list[dict[str, str]],
    sheet: Image.Image,
    model,
    out_dir: Path,
    pair_size: int,
    ocr_size: int,
    font,
) -> None:
    rows = deepcopy(base_rows)
    cand_rows: list[dict[str, str]] = []

    for r in rows:
        if r["group"] != "unconfirmed":
            continue
        idx = int(r["index_dec"])
        tile = tile_from_sheet(sheet, idx)
        inp = xbrz_up(tile, ocr_size) if mode == "xbrz" else raw_up(tile, ocr_size)
        ch, score, raw_text = predict_char(model, inp)
        if ch:
            r["char"] = ch
            r["source"] = f"paddle_{mode}:{score:.3f}"
        else:
            r["char"] = ""
            r["source"] = f"paddle_{mode}:none"
        cand_rows.append(
            {
                "index_dec": str(idx),
                "index_hex": f"{idx:04X}",
                "guess_char": ch,
                "guess_score": f"{score:.6f}",
                "raw_text": raw_text,
            }
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    save_rows(out_dir / "groups_report.csv", rows)
    with (out_dir / "unconfirmed_paddle_candidates.csv").open("w", newline="", encoding="utf-8") as fh:
        fields = ["index_dec", "index_hex", "guess_char", "guess_score", "raw_text"]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(cand_rows)

    render_pairs(rows, sheet, out_dir, pair_size, font)

    cnt = {"confirmed": 0, "unconfirmed": 0, "symbol": 0}
    for r in rows:
        g = r.get("group", "")
        if g in cnt:
            cnt[g] += 1
    filled = sum(1 for r in rows if r.get("group") == "unconfirmed" and (r.get("char") or "").strip())
    print(f"[{mode}] out_dir={out_dir}")
    print(f"[{mode}] confirmed={cnt['confirmed']} unconfirmed={cnt['unconfirmed']} symbol={cnt['symbol']}")
    print(f"[{mode}] unconfirmed_filled={filled}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Run Paddle twice (raw/xbrz) and build grouped pair outputs.")
    ap.add_argument("--groups-report-in", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--sheet-inv", default="work/font_probe/l512x12qg8_inv_12x12.png")
    ap.add_argument("--out-root", default="work/font_export")
    ap.add_argument("--pair-size", type=int, default=128)
    ap.add_argument("--ocr-size", type=int, default=96)
    ap.add_argument("--model", default="PP-OCRv5_server_rec")
    ap.add_argument("--font", default="")
    ap.add_argument("--mode", choices=["raw", "xbrz", "both"], default="both")
    args = ap.parse_args()

    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    base_rows = load_rows(Path(args.groups_report_in))
    sheet = Image.open(args.sheet_inv).convert("L")
    font = pick_font(args.font, args.pair_size)
    model = pdx.create_model(args.model)

    out_root = Path(args.out_root)
    out_raw = out_root / "grouped_raw"
    out_xbrz = out_root / "grouped_xbrz"

    if args.mode in ("raw", "both"):
        if out_raw.exists():
            shutil.rmtree(out_raw)
        run_mode("raw", base_rows, sheet, model, out_raw, args.pair_size, args.ocr_size, font)

    if args.mode in ("xbrz", "both"):
        if out_xbrz.exists():
            shutil.rmtree(out_xbrz)
        run_mode("xbrz", base_rows, sheet, model, out_xbrz, args.pair_size, args.ocr_size, font)


if __name__ == "__main__":
    main()
