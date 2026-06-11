#!/usr/bin/env python3
"""Re-flow EN dump records to the real dialog window width.

Within each record, text between control tags is re-wrapped: existing
<$FFFC> line breaks are treated as soft (replaced by spaces) and new ones
are inserted so that no rendered line exceeds the width budget in glyph
CELLS (pair tokens count as one cell). Words are never split. All other
control tags (FB00+arg, FFFD pages, FFF4/FFF3 highlights, terminators)
stay exactly where they are.

Choice records (text starting with ・) are kept single-line and reported
if they exceed the width.
"""
import argparse
import re
from pathlib import Path

from lang5_scen import TAG_RE, Codec, load_charmap_tbl

LINE_BREAK = "<$FFFC>"


def cells(codec: Codec, text: str) -> int:
    return len(codec.encode(text))


def wrap(codec: Codec, text: str, width: int) -> str:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if cells(codec, cand) <= width:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return LINE_BREAK.join(lines)


def reflow_record(codec: Codec, text: str, width: int) -> str:
    # Split into alternating [text, tag, text, tag, ...] pieces.
    pieces: list[tuple[str, bool]] = []
    pos = 0
    for m in TAG_RE.finditer(text):
        if m.start() > pos:
            pieces.append((text[pos : m.start()], False))
        pieces.append((m.group(0), True))
        pos = m.end()
    if pos < len(text):
        pieces.append((text[pos:], False))

    # Merge FFFC into adjacent text as spaces, keep other tags as barriers.
    out: list[str] = []
    buf = ""
    for piece, is_tag in pieces:
        if is_tag and piece == LINE_BREAK:
            buf += " "
        elif is_tag:
            out.append(("T", buf))
            out.append(("C", piece))
            buf = ""
        else:
            buf += piece
    out.append(("T", buf))

    rebuilt = ""
    for kind, val in out:
        if kind == "C":
            rebuilt += val
        else:
            val = " ".join(val.split())
            if val:
                rebuilt += wrap(codec, val, width)
    return rebuilt


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--en-dump", default="data/translation/en")
    ap.add_argument("--tbl", default="work/tables/lang5_en.tbl")
    ap.add_argument("--width", type=int, default=20)
    ap.add_argument("--choice-width", type=int, default=20)
    ap.add_argument("--max-lines", type=int, default=3)
    args = ap.parse_args()

    codec = Codec(load_charmap_tbl(Path(args.tbl)))
    for fp in sorted(Path(args.en_dump).glob("*/chunk_*.txt")):
        out_lines: list[str] = []
        for raw in fp.read_text(encoding="utf-8").splitlines():
            if "\t" not in raw or raw.startswith("#"):
                out_lines.append(raw)
                continue
            idx, text = raw.split("\t", 1)
            stripped = TAG_RE.sub("", text)
            if stripped.count("・") > 1:
                # multi-bullet objective lists keep their structure verbatim
                out_lines.append(raw)
                continue
            if stripped.startswith("・"):
                # Choices must stay single-line: a wrapped tail becomes a
                # bogus selectable row in the game's menu.
                if "<$FFFE>" in text:
                    head, tail = text.split("<$FFFE>", 1)
                    head = " ".join(head.replace(LINE_BREAK, " ").split())
                    new_text = f"{head}<$FFFE>{tail}"
                else:
                    new_text = " ".join(text.replace(LINE_BREAK, " ").split())
                n = cells(codec, TAG_RE.sub("", new_text.split("<$FFFE>")[0]))
                if n > args.choice_width:
                    print(f"{fp.name} record {idx}: choice is {n} cells (max {args.choice_width})")
                out_lines.append(f"{idx}\t{new_text}")
            else:
                new_text = reflow_record(codec, text, args.width)
                # Page height check: lines between page/terminator controls.
                for page in re.split(r"<\$FFF[ADEF]>|<\$FB00><\$[0-9A-Fa-f]{4}>", new_text):
                    n = page.count(LINE_BREAK) + 1
                    if page.strip() and n > args.max_lines:
                        print(f"{fp.name} record {idx}: page has {n} lines (max {args.max_lines})")
                out_lines.append(f"{idx}\t{new_text}")
        fp.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        print(f"reflowed {fp}")


if __name__ == "__main__":
    main()
