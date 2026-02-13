#!/usr/bin/env python3
import argparse
import csv
import json
import re
from pathlib import Path
from typing import Dict, List


TOK_RE = re.compile(r"\[([0-9A-F]{4})\]")

# Hard-confirmed seed mappings
SEED_MAP = {
    0x00C6: "ラ",
    0x00CD: "ン",
    0x00B2: "フ",
    0x0086: "ォ",
    0x00D1: "ー",
    0x00A6: "ド",
    0x020E: "元",
    0x020F: "帥",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Apply OCR-derived font index map to tokenized Langrisser V script rows.")
    p.add_argument("--alignment", default="work/scen_analysis/story_alignment_partial_decode.csv")
    p.add_argument("--font-map", default="work/scen_analysis/font_sheet_ocr_map.csv")
    p.add_argument("--min-conf", type=float, default=70.0)
    p.add_argument("--manual-map", default="scripts/lang5_token_map_manual.json")
    p.add_argument("--out-csv", default="work/scen_analysis/story_alignment_fontdecode.csv")
    p.add_argument("--out-txt", default="work/scen_analysis/source_script_fontdecode.txt")
    return p.parse_args()


def load_font_map(path: Path, min_conf: float) -> Dict[int, str]:
    out: Dict[int, str] = {}
    with path.open("r", encoding="utf-8") as fh:
        r = csv.DictReader(fh)
        for row in r:
            try:
                idx = int(row["index"])
                conf = float(row["conf"])
            except Exception:
                continue
            ch = (row.get("ocr_char") or "").strip()
            if not ch or conf < min_conf:
                continue
            # OCR sometimes outputs joined glyphs; keep 1-char only.
            if len(ch) == 1:
                out[idx] = ch
            elif len(ch) > 1:
                # Heuristic: prefer a CJK/kana punctuation-like last char.
                c = ch[-1]
                out[idx] = c
    out.update(SEED_MAP)
    return out


def load_manual_map(path: Path) -> Dict[int, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[int, str] = {}
    for k, v in data.items():
        try:
            idx = int(k, 16)
        except Exception:
            continue
        if isinstance(v, str) and v:
            out[idx] = v[0]
    return out


def decode_tokenized(tokenized: str, mp: Dict[int, str]) -> str:
    def _sub(m: re.Match) -> str:
        tok = int(m.group(1), 16)
        return mp.get(tok, m.group(0))

    return TOK_RE.sub(_sub, tokenized)


def main() -> None:
    args = parse_args()
    rows: List[dict] = []
    with Path(args.alignment).open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    mp = load_font_map(Path(args.font_map), args.min_conf)
    mp.update(load_manual_map(Path(args.manual_map)))

    out_rows = []
    for r in rows:
        jp_tok = r.get("jp_tokenized", "")
        jp_dec = decode_tokenized(jp_tok, mp) if jp_tok else ""
        out_rows.append(
            {
                "scenario": r.get("scenario", ""),
                "chunk_index": r.get("chunk_index", ""),
                "seq": r.get("seq", ""),
                "jp_record_index": r.get("jp_record_index", ""),
                "jp_tokenized": jp_tok,
                "jp_font_decoded": jp_dec,
                "en_line": r.get("en_line", ""),
            }
        )

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "scenario",
                "chunk_index",
                "seq",
                "jp_record_index",
                "jp_tokenized",
                "jp_font_decoded",
                "en_line",
            ],
        )
        w.writeheader()
        w.writerows(out_rows)

    # text preview
    out_txt = Path(args.out_txt)
    with out_txt.open("w", encoding="utf-8") as fh:
        cur = None
        for r in sorted(out_rows, key=lambda x: (x["scenario"], int(x["seq"] or 0))):
            sc = r["scenario"]
            if sc != cur:
                cur = sc
                fh.write(f"\n=== {sc} (chunk {r['chunk_index']}) ===\n")
            fh.write(f"[{r['seq']:>4}] rec={r['jp_record_index']:>4} JP: {r['jp_font_decoded']}\n")
            if r["en_line"]:
                fh.write(f"       EN: {r['en_line']}\n")

    print(f"loaded font map entries: {len(mp)}")
    print(f"wrote {out_csv}")
    print(f"wrote {out_txt}")


if __name__ == "__main__":
    main()
