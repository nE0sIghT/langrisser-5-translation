#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build token->glyph map using the confirmed identity rule for Langrisser V text streams."
    )
    p.add_argument("--records-csv", default="work/scen_analysis/records.csv")
    p.add_argument("--out-csv", default="work/scen_analysis/token_to_glyph_identity.csv")
    return p.parse_args()


def iter_tokens(records_csv: Path):
    with records_csv.open(encoding="utf-8") as fh:
        r = csv.DictReader(fh)
        for row in r:
            words = (row.get("words_hex") or "").strip().split()
            for w in words:
                try:
                    yield int(w, 16)
                except ValueError:
                    continue


def classify(token: int):
    if token == 0xFFFF:
        return ("terminator", "")
    if 0x8000 <= token <= 0x8008:
        return ("control_800x", "")
    if token < 0x8000:
        return ("glyph_identity", f"{token:04X}")
    return ("control_other", "")


def main() -> None:
    args = parse_args()
    tokens = sorted(set(iter_tokens(Path(args.records_csv))))

    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["token_u16", "kind", "glyph_u16"])
        for t in tokens:
            kind, glyph = classify(t)
            w.writerow([f"{t:04X}", kind, glyph])

    print(f"wrote {out} tokens={len(tokens)}")


if __name__ == "__main__":
    main()
