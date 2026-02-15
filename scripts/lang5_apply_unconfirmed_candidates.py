#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path


def is_japanese_char(ch: str) -> bool:
    if not ch:
        return False
    cp = ord(ch[0])
    # Hiragana, Katakana, CJK Unified Ideographs, full-width punctuation block.
    return (
        0x3040 <= cp <= 0x309F
        or 0x30A0 <= cp <= 0x30FF
        or 0x4E00 <= cp <= 0x9FFF
        or 0xFF01 <= cp <= 0xFF60
    )


def load_rows(path: Path) -> list[dict[str, str]]:
    out = []
    with path.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            row = {
                "index_dec": (r.get("index_dec") or "").strip(),
                "index_hex": (r.get("index_hex") or "").strip(),
                "group": (r.get("group") or "").strip(),
                "char": (r.get("char") or ""),
                "source": (r.get("source") or "").strip(),
            }
            if row["index_dec"] and row["group"]:
                out.append(row)
    return out


def save_rows(path: Path, rows: list[dict[str, str]]) -> None:
    fields = ["index_dec", "index_hex", "group", "char", "source"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description="Apply candidate CSV to unconfirmed rows in groups_report.")
    ap.add_argument("--groups-report", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--candidates", default="work/font_export/grouped/unconfirmed_dakanji_candidates.csv")
    ap.add_argument("--out-report", default="work/font_export/grouped/groups_report.csv")
    ap.add_argument("--min-score", type=float, default=0.55)
    ap.add_argument("--source-tag", default="dakanji")
    args = ap.parse_args()

    rows = load_rows(Path(args.groups_report))
    cand = {}
    with Path(args.candidates).open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            idx = int(r["index_dec"])
            ch = (r.get("guess_char") or "")[:1]
            score = float(r.get("guess_score") or 0.0)
            cand[idx] = (ch, score)

    applied = 0
    for r in rows:
        if r.get("group") != "unconfirmed":
            continue
        idx = int(r["index_dec"])
        # Reset unconfirmed char; keep only candidates from current model pass.
        r["char"] = ""
        r["source"] = "none"
        if idx not in cand:
            continue
        ch, score = cand[idx]
        if ch and score >= args.min_score and is_japanese_char(ch):
            r["char"] = ch
            r["source"] = f"{args.source_tag}:{score:.3f}"
            applied += 1

    out = Path(args.out_report)
    out.parent.mkdir(parents=True, exist_ok=True)
    save_rows(out, rows)
    print(f"out_report={out}")
    print(f"applied={applied}")


if __name__ == "__main__":
    main()
