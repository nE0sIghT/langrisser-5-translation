#!/usr/bin/env python3
import argparse
import csv
import tempfile
from pathlib import Path

from PIL import Image
import paddlex as pdx


def is_japanese_char(ch: str) -> bool:
    if not ch:
        return False
    cp = ord(ch[0])
    return (
        0x3040 <= cp <= 0x309F
        or 0x30A0 <= cp <= 0x30FF
        or 0x4E00 <= cp <= 0x9FFF
        or 0xFF01 <= cp <= 0xFF60
    )


def load_rows(path: Path):
    return list(csv.DictReader(path.open(encoding="utf-8")))


def main() -> None:
    ap = argparse.ArgumentParser(description="Run PaddleOCR recognition-only model on unconfirmed glyphs.")
    ap.add_argument("--groups-report", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--sheet-inv", default="work/font_probe/l512x12qg8_inv_12x12.png")
    ap.add_argument("--out-csv", default="work/font_export/grouped/unconfirmed_paddle_candidates.csv")
    ap.add_argument("--model", default="PP-OCRv5_server_rec")
    ap.add_argument("--size", type=int, default=96)
    ap.add_argument("--min-score", type=float, default=0.55)
    args = ap.parse_args()

    rows = load_rows(Path(args.groups_report))
    un = [r for r in rows if r.get("group") == "unconfirmed"]
    img = Image.open(args.sheet_inv).convert("L")
    cols = img.width // 12

    model = pdx.create_model(args.model)
    tmp = Path(tempfile.gettempdir())
    out_rows = []

    for r in un:
        idx = int(r["index_dec"])
        rr, cc = divmod(idx, cols)
        tile = img.crop((cc * 12, rr * 12, (cc + 1) * 12, (rr + 1) * 12)).resize((args.size, args.size), Image.NEAREST)
        p = tmp / f"lang5_u_{idx}.png"
        tile.save(p)
        pred = list(model.predict(str(p)))
        text = (pred[0].get("rec_text") or "") if pred else ""
        score = float(pred[0].get("rec_score") or 0.0) if pred else 0.0
        ch = text[:1] if text else ""
        if not is_japanese_char(ch) or score < args.min_score:
            ch = ""
        out_rows.append(
            {
                "index_dec": str(idx),
                "index_hex": f"{idx:04X}",
                "guess_char": ch,
                "guess_score": f"{score:.6f}",
                "raw_text": text,
            }
        )

    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        fields = ["index_dec", "index_hex", "guess_char", "guess_score", "raw_text"]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)

    kept = sum(1 for r in out_rows if r["guess_char"])
    print(f"model={args.model}")
    print(f"rows={len(out_rows)} kept={kept}")
    print(f"out_csv={out}")


if __name__ == "__main__":
    main()
