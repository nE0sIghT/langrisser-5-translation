#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path


def load_map(path: Path) -> dict[int, str]:
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


def decode_words(words: list[int], mp: dict[int, str]) -> str:
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
    p = argparse.ArgumentParser(description="Probe records around a chunk-relative offset.")
    p.add_argument("--records", default="work/scen_analysis/records.csv")
    p.add_argument("--chunk", type=int, required=True)
    p.add_argument("--offset", type=lambda s: int(s, 0), required=True, help="Chunk-relative byte offset (e.g. 0x5488)")
    p.add_argument("--radius", type=int, default=8, help="How many records before/after nearest record")
    p.add_argument("--token-map", default="scripts/lang5_token_map_manual.json")
    args = p.parse_args()

    rows = [r for r in csv.DictReader(Path(args.records).open("r", encoding="utf-8")) if int(r["chunk_index"]) == args.chunk]
    rows.sort(key=lambda r: int(r["offset"]))
    if not rows:
        raise SystemExit(f"no records for chunk {args.chunk}")

    mp = load_map(Path(args.token_map))
    idx = min(range(len(rows)), key=lambda i: abs(int(rows[i]["offset"]) - args.offset))

    lo = max(0, idx - args.radius)
    hi = min(len(rows), idx + args.radius + 1)
    for r in rows[lo:hi]:
        words = [int(x, 16) for x in r["words_hex"].split()]
        dec = decode_words(words, mp)
        print(
            f"chunk={r['chunk_index']} rec={r['record_index']} off=0x{int(r['offset']):04X} "
            f"size={r['size']} words={r['word_count']}"
        )
        print(f"DEC: {dec}")
        print(f"TOK: {r['words_hex']}")
        print()


if __name__ == "__main__":
    main()

