#!/usr/bin/env python3
"""Re-flow EN dump records to the real text window width.

Within each record, text between control tags is re-wrapped: existing
<$FFFC> line breaks are treated as soft (replaced by spaces) and new ones
are inserted so that no rendered line exceeds the width budget in glyph
CELLS (pair tokens count as one cell). Words are never split. All other
control tags (FB00+arg, FFFD pages, FFF4/FFF3 highlights, terminators)
stay exactly where they are.

The player-name macro <$F600><$0000> counts as NAME_CELLS (the name entry
screen allows 8 native glyphs — measured in-game); explicit printable
tags such as the <$0000> indent space count as one cell. Both windows
that auto-wrap (dialogue and narration/briefing) are 21 cells wide
(measured in-game with a ruler build); the default width keeps one cell
of safety margin.

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
NAME_MACRO = 0xF600
NAME_CELLS = 8
# Chunks whose dialogue window draws no inline speaker plate (verified
# in-game): the quiz renders full-width text despite FB00 tags.
RESERVE_OVERRIDE = {0: 0}


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


def wrap_stream(codec: Codec, text: str, width: int, reserve: int = 0) -> str:
    """Wrap a mixed text/control stream without treating control tags as a
    visual line reset. Zero-width control tags create safe break points
    before the next printable word; tags glued to the tail of a word (such
    as the highlight-off after the word) stay with that word. The name
    macro and printable tags carry real cell widths.

    `reserve` is the speaker-plate width: the engine draws the name plate
    and its bracket inline at the start of the window, so the first line
    of the record and of every page is shorter by that amount."""
    out: list[str] = []
    pending_tags: list[str] = []
    atom_parts: list[str] = []
    atom_width = 0
    line_width = reserve
    line_has_text = False
    saw_space = False
    saw_tag_boundary = False

    def flush_atom() -> None:
        nonlocal atom_width, line_width, line_has_text, saw_space, saw_tag_boundary
        if not atom_parts and not pending_tags:
            return
        if atom_parts:
            sep = 1 if saw_space and line_has_text else 0
            can_break = line_has_text and (saw_space or saw_tag_boundary)
            if can_break and line_width + sep + atom_width > width:
                out.append(LINE_BREAK)
                line_width = 0
                sep = 0
            elif sep:
                out.append(" ")
                line_width += 1
            out.extend(pending_tags)
            pending_tags.clear()
            out.extend(atom_parts)
            atom_parts.clear()
            line_width += atom_width
            atom_width = 0
            line_has_text = True
            saw_space = False
            saw_tag_boundary = False

    tags = list(TAG_RE.finditer(text))
    pos = 0
    i = 0
    while i <= len(tags):
        raw = text[pos : tags[i].start()] if i < len(tags) else text[pos:]
        for part in re.split(r"(\s+)", raw):
            if not part:
                continue
            if part.isspace():
                flush_atom()
                saw_space = True
            else:
                atom_parts.append(part)
                atom_width += cells(codec, part)
        if i == len(tags):
            break
        m = tags[i]
        tag_text = m.group(0)
        val = int(m.group(1), 16)
        consumed = 1
        if consumes_argument(val) and i + 1 < len(tags) and tags[i + 1].start() == m.end():
            tag_text += tags[i + 1].group(0)
            consumed = 2
        if val == NAME_MACRO:
            atom_parts.append(tag_text)
            atom_width += NAME_CELLS
        elif val < PRINTABLE_TAG_LIMIT:
            atom_parts.append(tag_text)
            atom_width += 1
        elif tag_text == LINE_BREAK:
            flush_atom()
            saw_space = True
        elif tag_text in PAGE_BREAKS:
            flush_atom()
            out.extend(pending_tags)
            pending_tags.clear()
            out.append(tag_text)
            line_width = reserve
            line_has_text = False
            saw_space = False
            saw_tag_boundary = False
        elif atom_parts:
            # zero-width tag glued to a word tail (e.g. highlight-off):
            # keep it inside the atom so it never drifts across a break.
            atom_parts.append(tag_text)
        else:
            pending_tags.append(tag_text)
            saw_tag_boundary = True
        pos = m.start() + len(tag_text)
        i += consumed
    flush_atom()
    out.extend(pending_tags)
    return "".join(out)


def reflow_record(codec: Codec, text: str, width: int, reserve: int = 0) -> str:
    # The plate reserve only applies to spoken records; narration windows
    # have no name plate.
    if "<$FB" not in text:
        reserve = 0
    return wrap_stream(codec, text, width, reserve)


def plate_reserve(codec: Codec, records: list[tuple[str, str]]) -> int:
    """Worst-case speaker plate width for a chunk: the FFFF-terminated
    name records that precede the first FFFE objective record, plus one
    cell for the bracket the engine draws after the name. (The speaker of
    a given line is bound in the chunk's VM bytecode, not in the text, so
    the widest plate is the safe bound.)"""
    widest = 0
    for _idx, text in records:
        if text.endswith("<$FFFE>"):
            break
        if text.endswith("<$FFFF>"):
            widest = max(widest, visible_cells(codec, text[: -len("<$FFFF>")]))
    return widest + 1 if widest else 0


def visible_cells(codec: Codec, text: str) -> int:
    """Rendered width of a tag-bearing string in cells, with the name
    macro at its worst-case width."""
    n = 0
    pos = 0
    tags = list(TAG_RE.finditer(text))
    i = 0
    while i <= len(tags):
        raw = text[pos : tags[i].start()] if i < len(tags) else text[pos:]
        n += cells(codec, raw)
        if i == len(tags):
            break
        val = int(tags[i].group(1), 16)
        consumed = 1
        if consumes_argument(val) and i + 1 < len(tags) \
                and tags[i + 1].start() == tags[i].end():
            consumed = 2
        if val == NAME_MACRO:
            n += NAME_CELLS
        elif val < PRINTABLE_TAG_LIMIT:
            n += 1
        pos = tags[i + consumed - 1].end()
        i += consumed
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--en-dump", default="data/translation/en")
    ap.add_argument("--tbl", default="work/tables/lang5_en.tbl")
    ap.add_argument("--width", type=int, default=20)
    ap.add_argument("--choice-width", type=int, default=20)
    # The JP script routinely shows 4-line pages after engine wrap (594 of
    # them; 5-line pages exist but are rare), so 4 is the safe page height.
    ap.add_argument("--max-lines", type=int, default=4)
    args = ap.parse_args()

    codec = Codec(load_charmap_tbl(Path(args.tbl)))
    for fp in sorted(Path(args.en_dump).glob("*/chunk_*.txt")):
        records = []
        for raw in fp.read_text(encoding="utf-8").splitlines():
            if "\t" in raw and not raw.startswith("#"):
                records.append(tuple(raw.split("\t", 1)))
        chunk_idx = int(fp.stem.split("_")[1])
        reserve = RESERVE_OVERRIDE.get(chunk_idx, plate_reserve(codec, records))
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
                n = visible_cells(codec, new_text.split("<$FFFE>")[0])
                if n > args.choice_width:
                    print(f"{fp.name} record {idx}: choice is {n} cells (max {args.choice_width})")
                out_lines.append(f"{idx}\t{new_text}")
            else:
                new_text = reflow_record(codec, text, args.width, reserve)
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
