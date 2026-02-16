#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont

GLYPH_W = 12
GLYPH_H = 12
GLYPH_COUNT = 32 * 57
FONT_BYTES = GLYPH_COUNT * 18  # 12x12 1bpp packed contiguous bits


def load_groups(path: Path) -> List[dict]:
    with path.open(encoding="utf-8", errors="ignore") as fh:
        return list(csv.DictReader(fh))


def pick_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    candidates = []
    if path:
        candidates.append(path)
    candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]
    for c in candidates:
        p = Path(c)
        if p.exists():
            return ImageFont.truetype(str(p), size=size)
    raise SystemExit("No suitable TTF font found. Install DejaVu or pass --font.")


def render_tile(ch: str, font: ImageFont.FreeTypeFont) -> Image.Image:
    img = Image.new("L", (GLYPH_W, GLYPH_H), 255)  # white bg
    d = ImageDraw.Draw(img)
    bbox = d.textbbox((0, 0), ch, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (GLYPH_W - tw) // 2 - bbox[0]
    y = (GLYPH_H - th) // 2 - bbox[1]
    d.text((x, y), ch, font=font, fill=0)  # black glyph
    # hard threshold to 1-bit style
    return img.point(lambda v: 0 if v < 128 else 255)


def pack_tile_12x12(img: Image.Image) -> bytes:
    g = img.convert("L")
    px = g.load()
    bits: List[int] = []
    for y in range(GLYPH_H):
        for x in range(GLYPH_W):
            # bit=1 is black pixel in SYSTEM.BIN glyph plane
            bits.append(1 if px[x, y] < 128 else 0)
    out = bytearray(18)
    for i, b in enumerate(bits):
        if b:
            out[i // 8] |= 1 << (7 - (i % 8))
    return bytes(out)


def write_tile(buf: bytearray, idx: int, tile18: bytes) -> None:
    off = idx * 18
    buf[off : off + 18] = tile18


def main() -> None:
    ap = argparse.ArgumentParser(description="Patch SYSTEM.BIN with EN glyphs and build EN insert table.")
    ap.add_argument("--groups-report", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--system-bin", default="work/extracted/SYSTEM.BIN")
    ap.add_argument("--out-system-bin", default="work/build/SYSTEM.BIN.en")
    ap.add_argument("--out-tbl", default="work/tables/lang5_en_full.tbl")
    ap.add_argument("--out-map", default="work/font_export/en_font_added_map.csv")
    ap.add_argument("--font", default="")
    ap.add_argument("--font-size", type=int, default=12)
    args = ap.parse_args()

    rows = load_groups(Path(args.groups_report))

    # Base token->char from canonical mapping.
    tok2char: Dict[int, str] = {}
    for r in rows:
        grp = (r.get("group") or "").strip()
        if grp not in ("confirmed", "symbol"):
            continue
        ch = (r.get("char") or "")
        if not ch:
            continue
        tok = int(r["index_dec"])
        tok2char[tok] = ch

    # Preserve native punctuation where available.
    tok2char[0x0000] = " "
    tok2char[0x0005] = "?"
    tok2char[0x0006] = "!"

    required = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,!?;:'\"-()[]/%&@+*=<>~_\\/"

    char2tok: Dict[str, int] = {}
    for tok in sorted(tok2char):
        ch = tok2char[tok]
        if ch and ch not in char2tok:
            char2tok[ch] = tok

    missing = [ch for ch in required if ch not in char2tok]

    # Sacrifice confirmed JP glyph slots from high indices down, but protect
    # tokens already used for required EN chars and core punctuation.
    protected_tokens = set()
    keep_chars = set(required) | {"?", "!", " "}
    for tok, ch in tok2char.items():
        if ch in keep_chars:
            protected_tokens.add(tok)

    pool: List[int] = []
    for r in sorted(rows, key=lambda x: int(x["index_dec"]), reverse=True):
        tok = int(r["index_dec"])
        if (r.get("group") or "") != "confirmed":
            continue
        ch = (r.get("char") or "")
        if not ch:
            continue
        if tok in protected_tokens:
            continue
        pool.append(tok)

    if len(pool) < len(missing):
        raise SystemExit(f"Not enough sacrificial slots: need {len(missing)}, have {len(pool)}")

    added: List[Tuple[int, str]] = []
    for ch in missing:
        tok = pool.pop(0)
        tok2char[tok] = ch
        char2tok[ch] = tok
        added.append((tok, ch))

    # Patch SYSTEM.BIN glyph plane.
    src = Path(args.system_bin).read_bytes()
    if len(src) < FONT_BYTES:
        raise SystemExit(f"SYSTEM.BIN too small: {len(src)} < {FONT_BYTES}")
    out = bytearray(src)

    font = pick_font(args.font, args.font_size)
    for tok, ch in added:
        tile = render_tile(ch, font)
        write_tile(out, tok, pack_tile_12x12(tile))

    out_path = Path(args.out_system_bin)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(out))

    # Write final tbl.
    tbl_lines = ["# Langrisser V EN full table", "# Format: HHHH=text"]
    for tok in sorted(tok2char):
        ch = tok2char[tok]
        if ch:
            tbl_lines.append(f"{tok:04X}={ch}")
    tbl_path = Path(args.out_tbl)
    tbl_path.parent.mkdir(parents=True, exist_ok=True)
    tbl_path.write_text("\n".join(tbl_lines) + "\n", encoding="utf-8")

    # Write assignment map.
    map_path = Path(args.out_map)
    map_path.parent.mkdir(parents=True, exist_ok=True)
    with map_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["index_dec", "index_hex", "char"])
        for tok, ch in added:
            w.writerow([tok, f"{tok:04X}", ch])

    print(f"added_glyphs={len(added)}")
    print(f"out_system_bin={out_path}")
    print(f"out_tbl={tbl_path}")
    print(f"out_map={map_path}")


if __name__ == "__main__":
    main()
