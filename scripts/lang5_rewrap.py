#!/usr/bin/env python3
"""Re-flow EN dump records to the real text window width.

Within each record, text between control tags is re-wrapped: existing
<$FFFC> line breaks are treated as soft (replaced by spaces) and new ones
are inserted so that no rendered line exceeds the width budget in glyph
CELLS (pair tokens count as one cell). Words are never split. In non-battle
scene chunks, <$FFFD> page breaks are compacted only when the following page
is plain text with no event controls; battle chunks keep page breaks hard
because battle scripts can couple paging to portrait/event state. All other
control tags (FB00+arg, FFF4/FFF3 highlights, terminators) stay exactly
where they are.

The player-name macro <$F600><$0000> counts as NAME_CELLS (the name entry
screen allows 8 native glyphs — measured in-game); explicit printable
tags such as the <$0000> indent space count as one cell. All windows
that auto-wrap (dialogue, narration/briefing, quiz) are 21 cells wide
(measured in-game with a ruler build).

The engine draws the speaker name plate inline at the start of a plated
window, so plated first lines are shorter by the plate width. When the
static VM tracer reaches a display command, its byte9 field is used as a
zero-based speaker-pool slot (0xff means no plate). Missing trace rows
fall back to the widest plate in the chunk's speaker pool. The pool size
comes from the chunk VM header (+0x38) in the original SCEN.DAT, which
excludes location plates; speaker plate names are kept short (<= 5 cells)
so the fallback bound stays tight.

Choice records (text starting with ・) are kept single-line and reported
if they exceed the width.
"""
import argparse
import re
from pathlib import Path

from lang5_scen import TAG_RE, Codec, consumes_argument, find_text_block, \
    load_charmap_tbl, read_chunk_spans, words_from_bytes
from lang5_speakers import trace_vm_bytecode, u32, vm_block

LINE_BREAK = "<$FFFC>"
PAGE_BREAK = "<$FFFD>"
TERMINATORS = {"<$FFFE>", "<$FFFF>"}
PAGE_BREAKS = {PAGE_BREAK, *TERMINATORS}
PRINTABLE_TAG_LIMIT = 0xE000
NAME_MACRO = 0xF600
NAME_CELLS = 8
# Records whose window keeps the previous speaker plate even though the
# record carries no FB00 marker of its own. Quiz prompts with their own FB00
# markers are not plated in-game; record 199 engine-broke at exactly 21 minus
# the Operator plate width during playtest, so only that tail prompt is forced.
FORCE_PLATED_RECORDS = {(0, 199)}
BATTLE_CHUNKS = set(range(1, 43))


def can_compact_pages(chunk_idx: int, compact_battle_pages: bool = False) -> bool:
    """Only scene/recap chunks get automatic FFFD demotion by default.

    Battle chunks have VM/event state around dialogue and portraits; playtest
    found that demoting seemingly plain FFFD continuations there can corrupt
    character images. Keep those page breaks structural unless explicitly
    requested for experiments.
    """
    return compact_battle_pages or chunk_idx not in BATTLE_CHUNKS


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
    of a plated record is shorter by that amount. Continuation pages after
    <$FFFD> do not redraw the plate and therefore restart at full width."""
    out: list[str] = []
    line_parts: list[str] = []
    pending_tags: list[str] = []
    atom_parts: list[str] = []
    line_reserve = reserve
    line_has_text = False
    saw_space = False
    saw_tag_boundary = False

    def flush_atom() -> None:
        nonlocal line_reserve, line_has_text, saw_space, saw_tag_boundary
        if not atom_parts and not pending_tags:
            return
        if atom_parts:
            sep = " " if saw_space and line_has_text else ""
            can_break = line_has_text and (saw_space or saw_tag_boundary)
            candidate = "".join(line_parts + ([sep] if sep else [])
                                + pending_tags + atom_parts)
            if can_break and line_reserve + visible_cells(codec, candidate) > width:
                out.append(LINE_BREAK)
                line_parts.clear()
                line_reserve = 0
                sep = ""
            elif sep:
                out.append(sep)
                line_parts.append(sep)
            out.extend(pending_tags)
            line_parts.extend(pending_tags)
            pending_tags.clear()
            out.extend(atom_parts)
            line_parts.extend(atom_parts)
            atom_parts.clear()
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
        elif val < PRINTABLE_TAG_LIMIT:
            atom_parts.append(tag_text)
        elif tag_text == LINE_BREAK:
            flush_atom()
            saw_space = True
        elif tag_text in PAGE_BREAKS:
            flush_atom()
            out.extend(pending_tags)
            pending_tags.clear()
            out.append(tag_text)
            line_parts.clear()
            line_reserve = 0
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


def safe_page_continuation(text: str, start: int) -> bool:
    """True if the page after an FFFD can be treated as plain continuation.

    The check is intentionally conservative: scan until the next page/end
    marker and reject any event/control opcode. Printable tags, line breaks,
    highlights, and the player-name macro are text-like and safe.
    """
    tags = [m for m in TAG_RE.finditer(text) if m.start() >= start]
    i = 0
    while i < len(tags):
        m = tags[i]
        tag_text = m.group(0)
        val = int(m.group(1), 16)
        if tag_text in PAGE_BREAKS:
            return True
        if tag_text == LINE_BREAK or tag_text in ("<$FFF4>", "<$FFF3>"):
            i += 1
            continue
        if val < PRINTABLE_TAG_LIMIT:
            i += 1
            continue
        if val == NAME_MACRO:
            if i + 1 >= len(tags) or tags[i + 1].start() != m.end():
                return False
            i += 2
            continue
        return False
    return True


def structural_page_markers(text: str) -> list[tuple[int, int, str]]:
    """Return page/end markers that are not arguments of control opcodes."""
    out: list[tuple[int, int, str]] = []
    tags = list(TAG_RE.finditer(text))
    i = 0
    while i < len(tags):
        m = tags[i]
        val = int(m.group(1), 16)
        consumed = 1
        if consumes_argument(val) and i + 1 < len(tags) \
                and tags[i + 1].start() == m.end():
            consumed = 2
        if consumed == 1 and m.group(0) in PAGE_BREAKS:
            out.append((m.start(), m.end(), m.group(0)))
        i += consumed
    return out


def page_segments(text: str) -> list[str]:
    """Split on structural page/end markers, ignoring control arguments."""
    out: list[str] = []
    start = 0
    for a, b, _tag in structural_page_markers(text):
        out.append(text[start:a])
        start = b
    out.append(text[start:])
    return out


def page_heights_ok(text: str, max_lines: int) -> bool:
    """Check rendered page height after wrapping."""
    for page in page_segments(text):
        if page.strip() and page.count(LINE_BREAK) + 1 > max_lines:
            return False
    return True


def compact_safe_pages(codec: Codec, text: str, width: int, reserve: int,
                       max_lines: int) -> str:
    """Iteratively demote safe FFFD page breaks to soft line breaks.

    Each candidate is rewrapped and accepted only if it stays within the
    page-height budget. This keeps voiced/event boundaries intact while
    allowing plain continuation pages to fill the window.
    """
    current = text
    while True:
        changed = False
        for pos, end, tag in structural_page_markers(current):
            if tag != PAGE_BREAK:
                continue
            if not safe_page_continuation(current, end):
                continue
            candidate = current[:pos] + LINE_BREAK + current[end:]
            wrapped = wrap_stream(codec, candidate, width, reserve)
            if page_heights_ok(wrapped, max_lines):
                current = candidate
                changed = True
                break
        if not changed:
            return current


def reflow_record(codec: Codec, text: str, width: int, reserve: int = 0,
                  force_plate: bool = False, max_lines: int = 4,
                  compact_pages: bool = True) -> str:
    # The plate reserve only applies to spoken records; narration windows
    # have no name plate. Some windows keep the previous speaker's plate
    # on records without their own FB00 marker (force_plate).
    if "<$FB" not in text and not force_plate:
        reserve = 0
    if compact_pages:
        text = compact_safe_pages(codec, text, width, reserve, max_lines)
    return wrap_stream(codec, text, width, reserve)



def speaker_pool_sizes(scen_path: Path) -> dict[int, int]:
    """Speaker-name pool size per chunk from the original SCEN.DAT.

    The chunk VM header word +0x38 counts the FFFF-terminated speaker
    plates at the head of the record list. Location plates and scene
    captions that follow the pool are not counted (verified against all
    131 chunks), so this is the exact set of names the engine can draw
    inline in the dialogue window."""
    sizes: dict[int, int] = {}
    data = scen_path.read_bytes()
    for ci, (start, end) in enumerate(read_chunk_spans(data)):
        chunk = data[start:end]
        try:
            block = find_text_block(chunk)
        except Exception:
            continue
        if not block or not block.record_count:
            continue
        off, _vm, _stream = vm_block(chunk, block)
        if off:
            sizes[ci] = u32(chunk, off + 0x38)
    return sizes


def traced_plate_slots(scen_path: Path) -> dict[int, dict[int, int | None]]:
    """Return chunk -> record -> speaker slot from decoded display commands.

    Display opcodes 0x0b..0x10 pass a zero-based text id and byte9 to
    handler 0x80024424. In chunk 45 the text id is relative to the first
    FB00-bearing text record, and byte9 is a zero-based speaker-pool slot;
    0xff means the window has no speaker plate. The tracer is incomplete for
    many chunks, so this function only returns rows that map cleanly back to
    an original FB00 record. Missing records deliberately fall back to the
    conservative chunk-wide reserve.
    """
    out: dict[int, dict[int, int | None]] = {}
    data = scen_path.read_bytes()
    for ci, (start, end) in enumerate(read_chunk_spans(data)):
        chunk = data[start:end]
        try:
            block = find_text_block(chunk)
        except Exception:
            continue
        fb_records: set[int] = set()
        for idx in range(1, block.record_count + 1):
            a, b = block.record_span(idx)
            words = words_from_bytes(chunk[a:b])
            if any(word == 0xFB00 for word in words):
                fb_records.add(idx)
        if not fb_records:
            continue
        first_fb_record = min(fb_records)
        rows = trace_vm_bytecode(
            source_file=scen_path.name,
            chunk_index=ci,
            chunk_start=start,
            chunk=chunk,
            block=block,
        )
        for row in rows:
            if row.kind != "display_24424" or row.display_text_id is None:
                continue
            rec_idx = first_fb_record + row.display_text_id
            if rec_idx not in fb_records:
                continue
            if row.display_byte9 == 0xFF:
                out.setdefault(ci, {})[rec_idx] = None
            elif row.display_byte9 is not None:
                out.setdefault(ci, {})[rec_idx] = row.display_byte9
    return out


def slot_plate_reserves(codec: Codec, records: list[tuple[str, str]],
                        pool_size: int | None = None) -> dict[int, int]:
    """Zero-based speaker-pool slot -> plate reserve in rendered cells."""
    if pool_size is None:
        return {}
    by_idx = {int(idx): text for idx, text in records if idx.isdigit()}
    reserves: dict[int, int] = {}
    for slot in range(pool_size):
        text = by_idx.get(slot + 1)
        if not text or not text.endswith("<$FFFF>"):
            continue
        plate = text[: -len("<$FFFF>")]
        reserves[slot] = visible_cells(codec, plate) + 1
    return reserves


def plate_reserve(codec: Codec, records: list[tuple[str, str]],
                  pool_size: int | None = None) -> int:
    """Worst-case speaker plate width for a chunk, plus one cell for the
    bracket the engine draws after the name. (The speaker of a given line
    is bound by VM runtime state, so the widest pool plate is the safe
    bound.) With a known pool size, exactly the first pool_size records
    are the speaker plates; without one, fall back to the FFFF-terminated
    records before the first FFFE objective record."""
    widest = 0
    for idx, text in records:
        if pool_size is not None:
            if not idx.isdigit() or int(idx) > pool_size:
                break
        elif text.endswith("<$FFFE>"):
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
    ap.add_argument("--scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--width", type=int, default=21)
    ap.add_argument("--choice-width", type=int, default=21)
    # The JP script routinely shows 4-line pages after engine wrap (594 of
    # them; 5-line pages exist but are rare), so 4 is the safe page height.
    ap.add_argument("--max-lines", type=int, default=4)
    ap.add_argument("--compact-battle-pages", action="store_true",
                    help="Experimental: also demote safe-looking FFFD breaks in battle chunks.")
    args = ap.parse_args()

    codec = Codec(load_charmap_tbl(Path(args.tbl)))
    scen_path = Path(args.scen)
    pool_sizes = speaker_pool_sizes(scen_path) if scen_path.exists() else {}
    traced_slots = traced_plate_slots(scen_path) if scen_path.exists() else {}
    if not pool_sizes:
        print(f"WARNING: {args.scen} not found; falling back to the FFFF-prefix "
              "plate heuristic (location plates may inflate the reserve)")
    for fp in sorted(Path(args.en_dump).glob("*/chunk_*.txt")):
        records = []
        for raw in fp.read_text(encoding="utf-8").splitlines():
            if "\t" in raw and not raw.startswith("#"):
                records.append(tuple(raw.split("\t", 1)))
        chunk_idx = int(fp.stem.split("_")[1])
        pool_size = pool_sizes.get(chunk_idx)
        chunk_reserve = plate_reserve(codec, records, pool_size)
        compact_pages = can_compact_pages(chunk_idx, args.compact_battle_pages)
        slot_reserves = slot_plate_reserves(codec, records, pool_size)
        record_slots = traced_slots.get(chunk_idx, {})
        width = args.width
        out_lines: list[str] = []
        for raw in fp.read_text(encoding="utf-8").splitlines():
            if "\t" not in raw or raw.startswith("#"):
                out_lines.append(raw)
                continue
            idx, text = raw.split("\t", 1)
            reserve = chunk_reserve
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
                force_plate = (chunk_idx, int(idx)) in FORCE_PLATED_RECORDS
                rec_idx = int(idx)
                if rec_idx in record_slots:
                    slot = record_slots[rec_idx]
                    if slot is None:
                        reserve = 0
                    elif slot in slot_reserves:
                        reserve = slot_reserves[slot]
                if chunk_idx == 0 and not force_plate:
                    reserve = 0
                new_text = reflow_record(
                    codec, text, width, reserve, force_plate,
                    max_lines=args.max_lines,
                    compact_pages=compact_pages,
                )
                # Page height check: lines between page/terminator controls.
                for page in page_segments(new_text):
                    n = page.count(LINE_BREAK) + 1
                    if page.strip() and n > args.max_lines:
                        print(f"{fp.name} record {idx}: page has {n} lines (max {args.max_lines})")
                out_lines.append(f"{idx}\t{new_text}")
        fp.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        print(f"reflowed {fp}")


if __name__ == "__main__":
    main()
