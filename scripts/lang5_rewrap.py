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

from lang5_scen import TAG_RE, Codec, consumes_argument, load_charmap_tbl

LINE_BREAK = "<$FFFC>"
PAGE_BREAKS = {"<$FFFD>", "<$FFFE>", "<$FFFF>"}
PRINTABLE_TAG_LIMIT = 0xE000


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


def wrap_stream(codec: Codec, text: str, width: int) -> str:
    """Wrap a mixed text/control stream without treating control tags as a
    visual line reset. Tags have zero width but create safe break points
    before the next printable word."""
    out: list[str] = []
    pending_tags: list[str] = []
    line_text = ""
    saw_space = False
    saw_tag_boundary = False
    pos = 0

    def flush_word(word: str) -> None:
        nonlocal line_text, saw_space, saw_tag_boundary
        if not word:
            return
        sep = " " if saw_space and line_text else ""
        cand = f"{line_text}{sep}{word}"
        can_break = bool(line_text) and (saw_space or saw_tag_boundary)
        if can_break and cells(codec, cand) > width:
            out.append(LINE_BREAK)
            line_text = ""
            sep = ""
        elif sep:
            out.append(sep)
            line_text += sep
        out.extend(pending_tags)
        pending_tags.clear()
        out.append(word)
        line_text += word
        saw_space = False
        saw_tag_boundary = False

    for m in TAG_RE.finditer(text):
        raw = text[pos : m.start()]
        for part in re.split(r"(\s+)", raw):
            if not part:
                continue
            if part.isspace():
                saw_space = True
            else:
                flush_word(part)
        tag = m.group(0)
        if tag == LINE_BREAK:
            saw_space = True
        elif tag in PAGE_BREAKS:
            out.extend(pending_tags)
            pending_tags.clear()
            out.append(tag)
            line_text = ""
            saw_space = False
            saw_tag_boundary = False
        else:
            pending_tags.append(tag)
            saw_tag_boundary = True
        pos = m.end()

    raw = text[pos:]
    for part in re.split(r"(\s+)", raw):
        if not part:
            continue
        if part.isspace():
            saw_space = True
        else:
            flush_word(part)
    out.extend(pending_tags)
    return "".join(out)


def reflow_record(codec: Codec, text: str, width: int) -> str:
    return wrap_stream(codec, text, width)


def has_explicit_printable_or_macro_tags(text: str) -> bool:
    prev: int | None = None
    for h in TAG_RE.findall(text):
        v = int(h, 16)
        if prev is not None and consumes_argument(prev):
            prev = v
            continue
        if v == 0xF600 or v < PRINTABLE_TAG_LIMIT:
            return True
        prev = v
    return False


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
                if has_explicit_printable_or_macro_tags(text):
                    new_text = text
                else:
                    new_text = reflow_record(codec, text, args.width)
                # Page height check: lines between page/terminator controls.
                for page in re.split(r"<\$FFFD>|<\$FFFE>|<\$FFFF>", new_text):
                    n = page.count(LINE_BREAK) + 1
                    if page.strip() and n > args.max_lines:
                        print(f"{fp.name} record {idx}: page has {n} lines (max {args.max_lines})")
                out_lines.append(f"{idx}\t{new_text}")
        fp.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        print(f"reflowed {fp}")


if __name__ == "__main__":
    main()
