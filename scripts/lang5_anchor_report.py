#!/usr/bin/env python3
import argparse
import csv
import json
import re
from pathlib import Path
from typing import Iterable


HEX4 = re.compile(r"^[0-9A-F]{4}$")


def load_token_map(path: Path) -> dict[int, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[int, str] = {}
    for k, v in data.items():
        try:
            out[int(k, 16)] = str(v)[0]
        except Exception:
            continue
    return out


def parse_words(words_hex: str) -> list[int]:
    return [int(x, 16) for x in words_hex.split() if HEX4.match(x)]


def decode(words: Iterable[int], mp: dict[int, str]) -> str:
    out: list[str] = []
    for w in words:
        if w in mp:
            out.append(mp[w])
        elif w == 0xFB00:
            out.append("{FB00}")
        elif w in (0xFFFC, 0xFFFD, 0xFFFE, 0xFFFF):
            out.append(f"{{{w:04X}}}")
        else:
            out.append(f"[{w:04X}]")
    return "".join(out)


def main() -> None:
    p = argparse.ArgumentParser(description="Build anchor report for name-token records.")
    p.add_argument("--records", default="work/scen_analysis/records.csv")
    p.add_argument("--token-map", default="scripts/lang5_token_map_manual.json")
    p.add_argument("--out-csv", default="work/scen_analysis/anchor_report.csv")
    p.add_argument("--out-txt", default="work/scen_analysis/anchor_report.txt")
    args = p.parse_args()

    mp = load_token_map(Path(args.token_map))
    # anchor tokens
    gizarof = [0x008B, 0x0093, 0x00CA, 0x00B2]
    lanford = [0x00C6, 0x00CD, 0x00B2, 0x0086, 0x00D1, 0x00A6]

    rows_out: list[dict[str, str]] = []
    for r in csv.DictReader(Path(args.records).open("r", encoding="utf-8")):
        words = parse_words(r["words_hex"])
        kind = ""
        if any(words[i : i + len(gizarof)] == gizarof for i in range(max(0, len(words) - len(gizarof) + 1))):
            kind = "gizarof"
        if any(words[i : i + len(lanford)] == lanford for i in range(max(0, len(words) - len(lanford) + 1))):
            kind = f"{kind}+lanford" if kind else "lanford"
        if not kind:
            continue

        known = sum(1 for w in words if w in mp)
        ratio = known / max(1, len(words))
        rows_out.append(
            {
                "kind": kind,
                "chunk_index": r["chunk_index"],
                "record_index": r["record_index"],
                "offset": r["offset"],
                "word_count": r["word_count"],
                "known_ratio": f"{ratio:.3f}",
                "decoded": decode(words, mp),
                "words_hex": r["words_hex"],
            }
        )

    # prioritize short and more readable anchor lines
    rows_out.sort(key=lambda x: (x["kind"], -float(x["known_ratio"]), int(x["word_count"]), int(x["chunk_index"]), int(x["record_index"])))

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["kind", "chunk_index", "record_index", "offset", "word_count", "known_ratio", "decoded", "words_hex"],
        )
        w.writeheader()
        w.writerows(rows_out)

    out_txt = Path(args.out_txt)
    with out_txt.open("w", encoding="utf-8") as fh:
        cur = None
        for r in rows_out:
            if r["kind"] != cur:
                cur = r["kind"]
                fh.write(f"\n=== {cur} ===\n")
            fh.write(
                f"chunk={r['chunk_index']} rec={r['record_index']} off=0x{int(r['offset']):04X} "
                f"words={r['word_count']} known={r['known_ratio']}\n"
            )
            fh.write(f"DEC: {r['decoded']}\n")
            fh.write(f"TOK: {r['words_hex']}\n\n")

    print(f"anchors: {len(rows_out)}")
    print(f"wrote {out_csv}")
    print(f"wrote {out_txt}")


if __name__ == "__main__":
    main()

