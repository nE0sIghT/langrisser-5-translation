#!/usr/bin/env python3
"""Validate translated chunks against the JP source structure.

Per record: the sequence of control tags (>= 0xE000, except the soft line
break FFFC) and the argument words of F600/FBxx must match the JP source
exactly. Also checks that every EN line encodes, reports leftover JP text
and the per-chunk byte budget (block size + chunk tail padding).
"""
import argparse
import re
from pathlib import Path

from lang5_scen import (Codec, TAG_RE, consumes_argument, find_text_block,
                        load_charmap_tbl, read_chunk_spans)

ASCII_BAD = re.compile(r"[!?;—–]")


def read_records(path: Path) -> dict[int, str]:
    out: dict[int, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if "\t" in raw and not raw.startswith("#"):
            idx, text = raw.split("\t", 1)
            out[int(idx)] = text
    return out


def control_signature(text: str) -> list[str]:
    sig = []
    tags = TAG_RE.findall(text)
    prev = None
    for h in tags:
        v = int(h, 16)
        take = False
        if prev is not None and consumes_argument(prev):
            take = True  # argument word, must match verbatim
        elif v >= 0xE000 and v not in (0xFFFC, 0xFFFD, 0xFFF4, 0xFFF3):
            # FFFC/FFFD are soft breaks; FFF4/FFF3 are highlight toggles
            # (checked for balance separately)
            take = True
        if take:
            sig.append(h.upper())
        prev = v
    return sig


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("chunks", nargs="*", type=int)
    ap.add_argument("--jp-dump", default="work/scriptdump")
    ap.add_argument("--en-dump", default="data/translation/en")
    ap.add_argument("--tbl", default="work/tables/lang5_en.tbl")
    ap.add_argument("--scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--stem", default="SCEN")
    args = ap.parse_args()

    codec = Codec(load_charmap_tbl(Path(args.tbl)))
    data = Path(args.scen).read_bytes()
    spans = read_chunk_spans(data)

    chunk_ids = args.chunks
    if not chunk_ids:
        chunk_ids = sorted(int(p.stem.split("_")[1])
                           for p in Path(args.en_dump, args.stem).glob("chunk_*.txt"))

    problems = 0
    for cidx in chunk_ids:
        jp = read_records(Path(args.jp_dump, args.stem, f"chunk_{cidx:03d}.txt"))
        en = read_records(Path(args.en_dump, args.stem, f"chunk_{cidx:03d}.txt"))
        body = 0
        jp_left = 0
        for idx in sorted(jp):
            if idx not in en:
                print(f"chunk {cidx} rec {idx}: MISSING in EN")
                problems += 1
                continue
            if control_signature(jp[idx]) != control_signature(en[idx]):
                print(f"chunk {cidx} rec {idx}: CONTROL TAG MISMATCH")
                problems += 1
            if en[idx].count("<$FFF4>") != en[idx].count("<$FFF3>"):
                print(f"chunk {cidx} rec {idx}: UNBALANCED highlight tags")
                problems += 1
            if ASCII_BAD.search(TAG_RE.sub("", en[idx])):
                print(f"chunk {cidx} rec {idx}: unsupported ASCII punctuation")
                problems += 1
            try:
                body += 2 * len(codec.encode(en[idx]))
            except ValueError as exc:
                print(f"chunk {cidx} rec {idx}: UNENCODABLE {exc}")
                problems += 1
            if re.search(r"[぀-ヺ一-鿿]", TAG_RE.sub("", en[idx]).replace("・", "")):
                jp_left += 1
        s, e = spans[cidx]
        chunk = data[s:e]
        block = find_text_block(chunk)
        tz = len(chunk) - len(chunk.rstrip(b"\x00"))
        budget = block.size + (tz & ~1) - (2 + 2 * len(block.offsets))
        status = "OK" if body <= budget else "OVER BUDGET"
        if body > budget:
            problems += 1
        print(f"chunk {cidx:03d}: body={body} budget={budget} {status}"
              + (f" jp_left={jp_left}" if jp_left else ""))
    if problems:
        raise SystemExit(f"{problems} problems found")
    print("all good")


if __name__ == "__main__":
    main()
