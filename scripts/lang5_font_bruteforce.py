#!/usr/bin/env python3
import argparse
import csv
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from PIL import Image, ImageOps


@dataclass
class Variant:
    kind: str
    msb: bool
    hi12: Optional[bool] = None


KNOWN_MAP = {
    0x00C6: "ラ",
    0x00CD: "ン",
    0x00B2: "フ",
    0x0086: "ォ",
    0x00D1: "ー",
    0x00A6: "ド",
    0x020E: "元",
    0x020F: "帥",
}


def render_row16(data: bytes, base: int, idx: int, msb: bool, hi12: bool) -> Optional[Image.Image]:
    off = base + idx * 24
    if off + 24 > len(data):
        return None
    tile = Image.new("L", (12, 12), 255)
    px = tile.load()
    for y in range(12):
        w = (data[off + y * 2] << 8) | data[off + y * 2 + 1]
        bits = ((w >> 4) & 0x0FFF) if hi12 else (w & 0x0FFF)
        for x in range(12):
            bi = (11 - x) if msb else x
            px[x, y] = 0 if ((bits >> bi) & 1) else 255
    return tile


def render_stream18(data: bytes, base: int, idx: int, msb: bool) -> Optional[Image.Image]:
    off = base + idx * 18
    if off + 18 > len(data):
        return None
    bits: List[int] = []
    for by in data[off : off + 18]:
        if msb:
            bits.extend((by >> (7 - i)) & 1 for i in range(8))
        else:
            bits.extend((by >> i) & 1 for i in range(8))
    bits = bits[: 12 * 12]
    tile = Image.new("L", (12, 12), 255)
    px = tile.load()
    for n, v in enumerate(bits):
        x = n % 12
        y = n // 12
        px[x, y] = 0 if v else 255
    return tile


def ocr_char(tile: Image.Image, lang: str) -> str:
    img = tile.resize((240, 240), Image.NEAREST)
    img = ImageOps.expand(img, border=24, fill=255)
    tmp = Path("/tmp/lang5_font_bruteforce_tile.png")
    img.save(tmp)
    out = subprocess.run(
        ["tesseract", str(tmp), "stdout", "-l", lang, "--psm", "10"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    ).stdout
    return out.strip().replace(" ", "")


def iter_variants() -> Iterable[Variant]:
    for msb in (True, False):
        for hi12 in (True, False):
            yield Variant(kind="row16", msb=msb, hi12=hi12)
    for msb in (True, False):
        yield Variant(kind="stream18", msb=msb)


def render(data: bytes, base: int, token: int, v: Variant) -> Optional[Image.Image]:
    if v.kind == "row16":
        return render_row16(data, base, token, v.msb, bool(v.hi12))
    return render_stream18(data, base, token, v.msb)


def main() -> None:
    p = argparse.ArgumentParser(description="Bruteforce Langrisser V font layout/offset candidates with OCR seed checks.")
    p.add_argument("--file", default="work/extracted/SYSTEM.BIN")
    p.add_argument("--offset-start", type=lambda x: int(x, 0), default=0x0)
    p.add_argument("--offset-end", type=lambda x: int(x, 0), default=0x8000)
    p.add_argument("--offset-step", type=lambda x: int(x, 0), default=0x100)
    p.add_argument("--ocr-lang", default="jpn")
    p.add_argument("--out", default="work/scen_analysis/font_bruteforce_candidates.csv")
    args = p.parse_args()

    data = Path(args.file).read_bytes()
    out_rows: List[Dict[str, str]] = []

    for base in range(args.offset_start, min(args.offset_end, len(data)), args.offset_step):
        for v in iter_variants():
            score = 0
            details = []
            for tok, exp in KNOWN_MAP.items():
                tile = render(data, base, tok, v)
                if tile is None:
                    continue
                got = ocr_char(tile, args.ocr_lang)
                if got == exp:
                    score += 1
                details.append(f"{tok:04X}:{exp}->{got}")
            out_rows.append(
                {
                    "base_offset": f"0x{base:X}",
                    "variant": f"{v.kind}|msb={int(v.msb)}|hi12={'' if v.hi12 is None else int(v.hi12)}",
                    "exact_score": str(score),
                    "details": " ; ".join(details),
                }
            )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["base_offset", "variant", "exact_score", "details"])
        w.writeheader()
        w.writerows(sorted(out_rows, key=lambda r: int(r["exact_score"]), reverse=True))

    print(f"wrote {out}")


if __name__ == "__main__":
    main()
