#!/usr/bin/env python3
"""Validate translated chunks against the JP source structure.

Per record: the sequence of control tags (>= 0xE000, except the soft line
break FFFC) and the argument words of F600/FBxx must match the JP source
exactly. Also checks that every EN line encodes, reports leftover JP text
and validates the fixed-size SCEN/SCEN2 repack budget used by the builder.
"""
import argparse
import re
from pathlib import Path

from lang5_scen import (Codec, TAG_RE, consumes_argument, find_text_block,
                        load_charmap_tbl, read_chunk_spans, words_to_bytes)

ASCII_BAD = re.compile(r"[!?;—–]")
CHUNK_ALIGN = 0x800


def align_up(value: int, align: int = CHUNK_ALIGN) -> int:
    return (value + align - 1) & ~(align - 1)


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


def repacked_file_size(src: Path, records_by_chunk: dict[int, dict[int, str]],
                       codec: Codec) -> tuple[int, list[str]]:
    data = src.read_bytes()
    spans = read_chunk_spans(data)
    header_size = spans[0][0]
    lengths: list[int] = []
    savings: list[int] = []
    problems: list[str] = []
    for cidx, (s, e) in enumerate(spans):
        chunk = data[s:e]
        tail_zero = len(chunk) - len(chunk.rstrip(b"\x00"))
        edits = records_by_chunk.get(cidx, {})
        if edits:
            block = find_text_block(chunk)
            payloads: list[bytes] = []
            for ridx in range(1, block.record_count + 1):
                a, b = block.record_span(ridx)
                if ridx in edits:
                    payloads.append(words_to_bytes(codec.encode(edits[ridx])))
                else:
                    payloads.append(chunk[a:b])
            table_len = 2 + 2 * len(block.offsets)
            body_len = sum(len(p) for p in payloads)
            needed = table_len + body_len
            if needed > 0xFFFF:
                problems.append(
                    f"{src.name} chunk {cidx:03d}: text block would exceed u16 size"
                )
            out_size = block.size if needed <= block.size else needed
            if out_size <= block.size + (tail_zero & ~1):
                chunk_len = len(chunk)
            else:
                chunk_len = align_up(len(chunk) + out_size - block.size)
        else:
            chunk_len = len(chunk)
        lengths.append(chunk_len)
        savings.append(len(chunk) - align_up(len(chunk.rstrip(b"\x00"))))

    total = header_size + sum(lengths)
    if total > len(data):
        for saved in reversed(savings):
            if saved <= 0:
                continue
            total -= saved
            if total <= len(data):
                break
    return total, problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("chunks", nargs="*", type=int)
    ap.add_argument("--jp-dump", default="work/scriptdump")
    ap.add_argument("--en-dump", default="data/translation/en")
    ap.add_argument("--tbl", default="work/tables/lang5_en.tbl")
    ap.add_argument("--scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--scen2", default="work/extracted/SCEN2.DAT")
    ap.add_argument("--stem", default="SCEN")
    ap.add_argument("--budget-mode", choices=("fixed-repack", "local"),
                    default="fixed-repack")
    args = ap.parse_args()

    codec = Codec(load_charmap_tbl(Path(args.tbl)))
    data = Path(args.scen).read_bytes()
    spans = read_chunk_spans(data)

    chunk_ids = args.chunks
    if not chunk_ids:
        chunk_ids = sorted(int(p.stem.split("_")[1])
                           for p in Path(args.en_dump, args.stem).glob("chunk_*.txt"))

    records_by_chunk: dict[int, dict[int, str]] = {}
    problems = 0
    for cidx in chunk_ids:
        jp = read_records(Path(args.jp_dump, args.stem, f"chunk_{cidx:03d}.txt"))
        en = read_records(Path(args.en_dump, args.stem, f"chunk_{cidx:03d}.txt"))
        records_by_chunk[cidx] = en
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
        if body <= budget:
            status = "OK"
        elif args.budget_mode == "fixed-repack":
            status = "REPACK"
        else:
            status = "OVER BUDGET"
        if body > budget and args.budget_mode == "local":
            problems += 1
        print(f"chunk {cidx:03d}: body={body} budget={budget} {status}"
              + (f" jp_left={jp_left}" if jp_left else ""))
    if args.budget_mode == "fixed-repack":
        for src in (Path(args.scen), Path(args.scen2)):
            total, repack_problems = repacked_file_size(src, records_by_chunk, codec)
            for msg in repack_problems:
                print(msg)
                problems += 1
            status = "OK" if total <= src.stat().st_size else "OVER BUDGET"
            if total > src.stat().st_size:
                problems += 1
            print(f"{src.name}: fixed-size repack={total} file_size={src.stat().st_size} {status}")
    if problems:
        raise SystemExit(f"{problems} problems found")
    print("all good")


if __name__ == "__main__":
    main()
