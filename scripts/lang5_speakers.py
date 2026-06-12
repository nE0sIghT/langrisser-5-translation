#!/usr/bin/env python3
"""Extract dialogue speaker evidence from Langrisser V SCEN VM blocks.

Text records only contain ``FB00 <id>`` dialogue IDs. The speaker plate is
selected by chunk VM command records before the text block. This module keeps
the extraction conservative: static VM sites are exposed as evidence, but no
speaker mapping is marked confirmed until it follows decoded runtime behavior.
"""

from __future__ import annotations

import argparse
import csv
import struct
from dataclasses import dataclass
from pathlib import Path

from lang5_scen import Codec, find_text_block, load_charmap_csv, read_chunk_spans, words_from_bytes


def u16(blob: bytes, off: int) -> int:
    return struct.unpack_from("<H", blob, off)[0]


def u32(blob: bytes, off: int) -> int:
    return struct.unpack_from("<I", blob, off)[0]


@dataclass(frozen=True)
class ActorPlateEntry:
    key: int
    field2: int
    field3: int


@dataclass(frozen=True)
class SpeakerSite:
    source_file: str
    chunk_index: int
    chunk_start: int
    text_base: int
    text_records: int
    vm_off: int | None
    vm_rel_off: int | None
    form: str
    fb_id: int
    record_indices: tuple[int, ...]
    speaker_slot: int | None
    speaker_record: int | None
    speaker_name: str
    confidence: str
    state_word: int | None
    extra_words: tuple[int, ...]
    tail_words: tuple[int, ...]
    name_pool: tuple[tuple[int, str], ...]
    actor_table: tuple[ActorPlateEntry, ...]


def decode_record(codec: Codec, words: list[int]) -> str:
    return codec.decode(words)


def chunk_fb_refs(chunk: bytes, block) -> tuple[dict[int, list[int]], dict[int, list[int]]]:
    by_arg: dict[int, list[int]] = {}
    by_record: dict[int, list[int]] = {}
    for idx in range(1, block.record_count + 1):
        a, b = block.record_span(idx)
        words = words_from_bytes(chunk[a:b])
        args: list[int] = []
        for i, word in enumerate(words[:-1]):
            if word == 0xFB00:
                arg = words[i + 1]
                by_arg.setdefault(arg, []).append(idx)
                args.append(arg)
        if args:
            by_record[idx] = args
    return by_arg, by_record


def name_pool(codec: Codec, chunk: bytes, block) -> list[tuple[int, str]]:
    names: list[tuple[int, str]] = []
    for idx in range(1, block.record_count + 1):
        a, b = block.record_span(idx)
        words = words_from_bytes(chunk[a:b])
        if not words:
            continue
        if words[-1] == 0xFFFF:
            names.append((idx, decode_record(codec, words[:-1])))
            continue
        if words[-1] == 0xFFFE:
            break
    return names


def vm_block(chunk: bytes, block) -> tuple[int, bytes, int]:
    """Return (chunk-local VM offset, VM bytes, command stream start)."""
    if len(chunk) >= 0x44:
        off = u32(chunk, 0)
        if 0 <= off <= len(chunk) - 0x40 and u32(chunk, off) == 0x44:
            size = u32(chunk, off + 0x3C)
            if 0x40 <= size <= len(chunk) - off and off + size <= block.base:
                start = u32(chunk, off + 0x30)
                if start >= size:
                    start = 0x40
                return off, chunk[off : off + size], start
    return 0, chunk[: block.base], 0


def actor_plate_table(chunk: bytes) -> tuple[ActorPlateEntry, ...]:
    """Return the chunk-local table loaded into runtime global 0x800eba38.

    The loader at 0x8003b44c uses header u32 +0x14 as the table offset and the
    low byte of header u32 +0x2c as the entry count. The lookup routine at
    0x800b2da4 treats entries as u16 key, u8 field2, u8 field3.
    """
    if len(chunk) < 0x30:
        return ()
    off = u32(chunk, 0x14)
    count = u32(chunk, 0x2C) & 0xFF
    if count == 0 or off + count * 4 > len(chunk):
        return ()
    rows: list[ActorPlateEntry] = []
    for idx in range(count):
        pos = off + idx * 4
        rows.append(
            ActorPlateEntry(
                key=u16(chunk, pos),
                field2=chunk[pos + 2],
                field3=chunk[pos + 3],
            )
        )
    return tuple(rows)


def parse_ff0b_command_records(vm: bytes, stream_start: int) -> list[tuple[int, list[int]]]:
    """Find legacy evidence records ending in ``FF0B flags FFFF FFFF``.

    These patterns are useful cross-references for FB00 IDs, but they are not
    trusted execution-order data. The real VM is bytecode-driven and can skip
    such patterns as payload.
    """
    records: list[tuple[int, list[int]]] = []
    p = stream_start
    while p + 8 <= len(vm):
        if u16(vm, p) == 0xFFFF:
            p += 2
            continue
        rec_start = p
        words: list[int] = []
        found = False
        while p + 2 <= len(vm) and len(words) < 192:
            words.append(u16(vm, p))
            p += 2
            if (
                len(words) >= 4
                and words[-4] == 0xFF0B
                and words[-2] == 0xFFFF
                and words[-1] == 0xFFFF
            ):
                found = True
                break
        if found:
            records.append((rec_start, words))
        else:
            p = rec_start + 2
    return records


def slot_to_name(slot: int | None, names: list[tuple[int, str]]) -> tuple[int | None, str]:
    if slot is None or slot <= 0 or slot > len(names):
        return None, ""
    return names[slot - 1]


def _site(
    *,
    source_file: str,
    chunk_index: int,
    chunk_start: int,
    block,
    names: list[tuple[int, str]],
    fb_id: int,
    records: list[int],
    vm_off: int | None,
    vm_rel_off: int | None,
    form: str,
    speaker_slot: int | None,
    confidence: str,
    state_word: int | None = None,
    extra_words: list[int] | tuple[int, ...] = (),
    tail_words: list[int] | tuple[int, ...] = (),
    actor_table: tuple[ActorPlateEntry, ...] = (),
) -> SpeakerSite:
    speaker_record, speaker_name = slot_to_name(speaker_slot, names)
    if speaker_record is None and confidence == "confirmed":
        confidence = "unresolved"
    return SpeakerSite(
        source_file=source_file,
        chunk_index=chunk_index,
        chunk_start=chunk_start,
        text_base=block.base,
        text_records=block.record_count,
        vm_off=vm_off,
        vm_rel_off=vm_rel_off,
        form=form,
        fb_id=fb_id,
        record_indices=tuple(records),
        speaker_slot=speaker_slot,
        speaker_record=speaker_record,
        speaker_name=speaker_name,
        confidence=confidence,
        state_word=state_word,
        extra_words=tuple(extra_words),
        tail_words=tuple(tail_words),
        name_pool=tuple(names),
        actor_table=actor_table,
    )


def scan_vm_speakers(
    *,
    source_file: str,
    chunk_index: int,
    chunk_start: int,
    chunk: bytes,
    block,
    codec: Codec,
) -> list[SpeakerSite]:
    fb_by_arg, _fb_by_record = chunk_fb_refs(chunk, block)
    if not fb_by_arg:
        return []

    names = name_pool(codec, chunk, block)
    table = actor_plate_table(chunk)
    vm_off, vm, stream_start = vm_block(chunk, block)
    rows: list[SpeakerSite] = []
    for rec_off, words in parse_ff0b_command_records(vm, stream_start):
        if len(words) < 5:
            continue
        term = len(words) - 4
        w0 = words[0]
        w1 = words[1] if len(words) > 1 else None
        state_opcode = w0 & 0x00FF
        state_param = (w0 >> 8) & 0x00FF
        extra = words[2:term]

        if w1 in fb_by_arg and state_opcode == 0x00 and state_param not in (0x00, 0xFF):
            rows.append(
                _site(
                    source_file=source_file,
                    chunk_index=chunk_index,
                    chunk_start=chunk_start,
                    block=block,
                    names=names,
                    fb_id=w1,
                    records=fb_by_arg[w1],
                    vm_off=vm_off + rec_off,
                    vm_rel_off=rec_off,
                    form="vm_state_byte_rejected",
                    speaker_slot=None,
                    confidence="unresolved",
                    state_word=w0,
                    extra_words=extra,
                    tail_words=words[:12],
                    actor_table=table,
                )
            )
        elif w0 == 0xFF00 and w1 in fb_by_arg:
            rows.append(
                _site(
                    source_file=source_file,
                    chunk_index=chunk_index,
                    chunk_start=chunk_start,
                    block=block,
                    names=names,
                    fb_id=w1,
                    records=fb_by_arg[w1],
                    vm_off=vm_off + rec_off,
                    vm_rel_off=rec_off,
                    form="vm_ff00",
                    speaker_slot=None,
                    confidence="unresolved",
                    state_word=w0,
                    extra_words=extra,
                    tail_words=words[:12],
                    actor_table=table,
                )
            )
        elif w1 in fb_by_arg:
            rows.append(
                _site(
                    source_file=source_file,
                    chunk_index=chunk_index,
                    chunk_start=chunk_start,
                    block=block,
                    names=names,
                    fb_id=w1,
                    records=fb_by_arg[w1],
                    vm_off=vm_off + rec_off,
                    vm_rel_off=rec_off,
                    form="vm_indirect",
                    speaker_slot=None,
                    confidence="unresolved",
                    state_word=w0,
                    extra_words=extra,
                    tail_words=words[:12],
                    actor_table=table,
                )
            )

    for arg, records in sorted(fb_by_arg.items()):
        if not any(r.fb_id == arg for r in rows):
            rows.append(
                _site(
                    source_file=source_file,
                    chunk_index=chunk_index,
                    chunk_start=chunk_start,
                    block=block,
                    names=names,
                    fb_id=arg,
                    records=records,
                    vm_off=None,
                    vm_rel_off=None,
                    form="missing",
                    speaker_slot=None,
                    confidence="unresolved",
                    actor_table=table,
                )
            )
    return rows


def scan_file(path: Path, codec: Codec, chunk_filter: set[int] | None = None) -> list[SpeakerSite]:
    data = path.read_bytes()
    spans = read_chunk_spans(data)
    rows: list[SpeakerSite] = []
    for cidx, (start, end) in enumerate(spans):
        if chunk_filter is not None and cidx not in chunk_filter:
            continue
        chunk = data[start:end]
        try:
            block = find_text_block(chunk)
        except ValueError:
            continue
        rows.extend(
            scan_vm_speakers(
                source_file=path.name,
                chunk_index=cidx,
                chunk_start=start,
                chunk=chunk,
                block=block,
                codec=codec,
            )
        )
    return rows


def confirmed_speaker_slots(path: Path, codec: Codec, chunk_index: int) -> dict[int, int]:
    """Return ``FB00`` argument -> local name-record index for confirmed rows."""
    rows = scan_file(path, codec, {chunk_index})
    out: dict[int, int] = {}
    for row in rows:
        if row.confidence == "confirmed" and row.speaker_record is not None:
            out.setdefault(row.fb_id, row.speaker_record)
    return out


def row_dict(row: SpeakerSite) -> dict[str, str]:
    return {
        "source_file": row.source_file,
        "chunk_index": str(row.chunk_index),
        "chunk_start": f"0x{row.chunk_start:06X}",
        "text_base": f"0x{row.text_base:04X}",
        "text_records": str(row.text_records),
        "name_pool": " | ".join(f"{idx}:{name}" for idx, name in row.name_pool),
        "actor_table": " ".join(
            f"{entry.key:04X}:{entry.field2:02X}:{entry.field3:02X}"
            for entry in row.actor_table
        ),
        "vm_off": "" if row.vm_off is None else f"0x{row.vm_off:04X}",
        "vm_rel_off": "" if row.vm_rel_off is None else f"0x{row.vm_rel_off:04X}",
        "form": row.form,
        "fb_id": f"{row.fb_id:04X}",
        "record_indices": " ".join(str(i) for i in row.record_indices),
        "speaker_slot": "" if row.speaker_slot is None else str(row.speaker_slot),
        "speaker_record": "" if row.speaker_record is None else str(row.speaker_record),
        "speaker_name": row.speaker_name,
        "confidence": row.confidence,
        "state_word": "" if row.state_word is None else f"{row.state_word:04X}",
        "extra_words": " ".join(f"{x:04X}" for x in row.extra_words),
        "tail_words": " ".join(f"{x:04X}" for x in row.tail_words),
    }


def write_csv(rows: list[SpeakerSite], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "source_file",
        "chunk_index",
        "chunk_start",
        "text_base",
        "text_records",
        "name_pool",
        "actor_table",
        "vm_off",
        "vm_rel_off",
        "form",
        "fb_id",
        "record_indices",
        "speaker_slot",
        "speaker_record",
        "speaker_name",
        "confidence",
        "state_word",
        "extra_words",
        "tail_words",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        for row in rows:
            writer.writerow(row_dict(row))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--scen2", default="work/extracted/SCEN2.DAT")
    ap.add_argument("--font-map", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--out", default="work/vm_dialog_refs/speaker_refs.csv")
    ap.add_argument("--chunk", type=int, action="append", help="scan only this chunk index; may repeat")
    args = ap.parse_args()

    codec = Codec(load_charmap_csv(Path(args.font_map)))
    chunk_filter = set(args.chunk) if args.chunk else None
    rows: list[SpeakerSite] = []
    for src in (Path(args.scen), Path(args.scen2)):
        if src.exists():
            rows.extend(scan_file(src, codec, chunk_filter))
    write_csv(rows, Path(args.out))
    confirmed = sum(1 for r in rows if r.confidence == "confirmed")
    unresolved = sum(1 for r in rows if r.confidence != "confirmed")
    print(f"wrote {args.out} rows={len(rows)} confirmed={confirmed} unresolved={unresolved}")


if __name__ == "__main__":
    main()
