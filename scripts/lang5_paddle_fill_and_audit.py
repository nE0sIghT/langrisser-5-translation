#!/usr/bin/env python3
import argparse
import csv
import os
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
import paddlex as pdx


def load_rows(path: Path):
    rows = []
    with path.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append(
                {
                    "index_dec": (r.get("index_dec") or "").strip(),
                    "index_hex": (r.get("index_hex") or "").strip(),
                    "group": (r.get("group") or "").strip(),
                    "char": (r.get("char") or ""),
                    "source": (r.get("source") or "").strip(),
                }
            )
    return rows


def save_rows(path: Path, rows):
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


def predict_char(model, tile12: Image.Image, size: int = 96, invert: bool = False):
    t = tile12
    if invert:
        t = ImageOps.invert(t)
    t = t.resize((size, size), Image.NEAREST).convert("L").convert("RGB")
    tmp = Path(tempfile.gettempdir()) / f"lang5_paddle_{os.getpid()}_{id(t)}.png"
    t.save(tmp)
    pred = list(model.predict(str(tmp)))
    if not pred:
        return "", 0.0, ""
    text = pred[0].get("rec_text") or ""
    score = float(pred[0].get("rec_score") or 0.0)
    return (text[:1] if text else ""), score, text


def xbrz64(tile12: Image.Image, size: int = 64) -> Image.Image:
    with tempfile.TemporaryDirectory(prefix="lang5_xbrz_") as td:
        inp = Path(td) / "in.png"
        out = Path(td) / "out.png"
        tile12.save(inp)
        try:
            subprocess.run(["xbrzscale", "6", str(inp), str(out)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            up = Image.open(out).convert("L")
        except Exception:
            up = tile12.resize((72, 72), Image.NEAREST)
        return up.resize((size, size), Image.NEAREST)


def render_ttf(ch: str, size: int, font):
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


def main():
    ap = argparse.ArgumentParser(description="Fill unconfirmed with Paddle OCR and audit confirmed mismatches.")
    ap.add_argument("--groups-report-in", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--groups-report-out", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--sheet-inv", default="work/font_probe/l512x12qg8_inv_12x12.png")
    ap.add_argument("--pair-size", type=int, default=64)
    ap.add_argument("--font", default="")
    ap.add_argument("--audit-dir", default="work/font_export/grouped/paddle_not_confirmed")
    ap.add_argument("--audit-csv", default="work/font_export/grouped/paddle_not_confirmed.csv")
    ap.add_argument("--model", default="PP-OCRv5_server_rec")
    args = ap.parse_args()

    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    rows = load_rows(Path(args.groups_report_in))
    sheet = Image.open(args.sheet_inv).convert("L")
    font = pick_font(args.font, args.pair_size)
    model = pdx.create_model(args.model)

    # 1) Fill unconfirmed: take everything recognized on pass1.
    un_rows = [r for r in rows if r["group"] == "unconfirmed"]
    remaining = []
    for r in un_rows:
        idx = int(r["index_dec"])
        ch, sc, raw = predict_char(model, tile_from_sheet(sheet, idx), size=96, invert=False)
        if ch:
            r["char"] = ch
            r["source"] = f"paddle1:{sc:.3f}"
        else:
            r["char"] = ""
            r["source"] = "paddle1:none"
            remaining.append(r)

    # 2) Second pass for leftovers (still no xbrz on OCR input).
    for r in remaining:
        idx = int(r["index_dec"])
        ch, sc, raw = predict_char(model, tile_from_sheet(sheet, idx), size=128, invert=True)
        if ch:
            r["char"] = ch
            r["source"] = f"paddle2:{sc:.3f}"
        else:
            r["char"] = ""
            r["source"] = "paddle2:none"

    out_report = Path(args.groups_report_out)
    out_report.parent.mkdir(parents=True, exist_ok=True)
    save_rows(out_report, rows)

    # 3) Audit confirmed: where paddle does not confirm known mapping.
    audit_dir = Path(args.audit_dir)
    audit_dir.mkdir(parents=True, exist_ok=True)
    for p in audit_dir.glob("*.png"):
        p.unlink()

    audit_rows = []
    for r in rows:
        if r["group"] != "confirmed":
            continue
        exp = (r["char"] or "")[:1]
        if not exp:
            continue
        idx = int(r["index_dec"])
        tile = tile_from_sheet(sheet, idx)
        got, sc, raw = predict_char(model, tile, size=96, invert=False)
        if got == exp:
            continue
        # left: game xbrz, middle: expected, right: paddle
        left = xbrz64(tile, args.pair_size)
        mid = render_ttf(exp, args.pair_size, font)
        right = render_ttf(got, args.pair_size, font)
        pair = Image.new("L", (args.pair_size * 3 + 16, args.pair_size), 255)
        pair.paste(left, (0, 0))
        pair.paste(mid, (args.pair_size + 8, 0))
        pair.paste(right, (args.pair_size * 2 + 16, 0))
        pair.save(audit_dir / f"{idx:04d}.png")
        audit_rows.append(
            {
                "index_dec": str(idx),
                "index_hex": f"{idx:04X}",
                "expected": exp,
                "paddle": got,
                "score": f"{sc:.6f}",
                "raw_text": raw,
            }
        )

    with Path(args.audit_csv).open("w", newline="", encoding="utf-8") as fh:
        fields = ["index_dec", "index_hex", "expected", "paddle", "score", "raw_text"]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(audit_rows)

    print(f"out_report={out_report}")
    print(f"unconfirmed_total={len(un_rows)}")
    print(f"unconfirmed_filled={sum(1 for r in un_rows if (r.get('char') or '').strip())}")
    print(f"audit_mismatch_count={len(audit_rows)}")
    print(f"audit_dir={audit_dir}")
    print(f"audit_csv={args.audit_csv}")


if __name__ == "__main__":
    main()
