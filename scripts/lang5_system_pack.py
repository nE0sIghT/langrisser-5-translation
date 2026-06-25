#!/usr/bin/env python3
"""Pack translated SYSTEM.BIN strings back into their offset-table groups.

This is the inverse of `lang5_system_dump.py`. For each group it rebuilds the
`[u16 offset table][strings]` layout from the translation JSON, regenerating the
offset table from the *actual* (possibly changed) string lengths. Because the
table is regenerated, a translated string is no longer bound to the original
string's byte length - only to the group's total size (the group stays at its
fixed base so nothing that points at it has to move).

Per-string the limit is the on-screen line width, not the data: each string is
one display line, so by default a translation may not render wider than the
original line did (`--max-grow` raises that cap deliberately). Strings left
untranslated keep their original bytes; `text == "{BLANK}"` clears the line.

See docs/SYSTEM_BIN_FORMAT.md.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lang5_project import add_language_args, language_from_args
from lang5_scen import Codec, load_charmap_tbl
from lang5_system_dump import find_groups, run_length

FFFF = 0xFFFF


def reserve_leading_cells(orig: list[int]) -> list[int]:
    """Leading 0x0000 cells from the original run, to prepend to a translation.

    Some strings begin with blank cells the engine overdraws at runtime (the
    LOAD-menu stage counter "[N]面", the status-cure unit name, ...). The dump
    renders 0x0000 as nothing, so translations omit them; preserving them keeps
    the translated text from starting under those glyphs and overlapping them.
    """
    lead = 0
    for t in orig:
        if t == 0:
            lead += 1
        else:
            break
    return [0] * lead


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_language_args(ap)
    ap.add_argument("--system-in", default="work/build/SYSTEM.BIN.font")
    ap.add_argument("--system-out", default=None)
    ap.add_argument("--strings", default=None)
    ap.add_argument("--tbl", default=None)
    ap.add_argument("--repack", action="store_true",
                    help="Regenerate each group's offset table so strings may change "
                         "length (default: in-place, table untouched, byte-compatible). "
                         "Only safe if the game locates strings by table index; verify "
                         "in an emulator before enabling.")
    ap.add_argument("--max-grow", type=int, default=0,
                    help="With --repack, allow each line to be at most this many words "
                         "wider than the original (default 0 = display-safe).")
    ap.add_argument("--strict", action="store_true",
                    help="Exit non-zero on any unencodable line or over-budget group.")
    args = ap.parse_args()

    lang = language_from_args(args)
    strings_path = Path(args.strings) if args.strings else lang.system_strings
    tbl = Path(args.tbl) if args.tbl else lang.tbl
    system_out = (Path(args.system_out) if args.system_out
                  else lang.build_path("SYSTEM.BIN.{lang}"))

    codec = Codec(load_charmap_tbl(tbl))
    data = bytearray(Path(args.system_in).read_bytes())
    groups = find_groups(data)
    by_key = {}
    loose = []
    for e in json.loads(strings_path.read_text(encoding="utf-8")):
        if e["group"] == -1:
            loose.append(e)
        else:
            by_key[(e["group"], e["index"])] = e

    problems = []
    changed = 0

    # Loose strings have no table to regenerate: write within the fixed budget.
    for e in loose:
        # rstrip only: a leading space is a deliberate layout choice (it separates
        # the text from an engine-drawn prefix like the LOAD-menu "[N]面" counter),
        # so it must survive into the encoded line.
        text = (e.get("text") or "").rstrip()
        if not text:
            continue
        off = int(e["offset"], 16)
        budget = int(e["words"])
        if text == "{BLANK}":
            struct.pack_into("<%dH" % budget, data, off, *([FFFF] * budget))
            changed += 1
            continue
        try:
            toks = codec.encode(text)
        except Exception as exc:
            problems.append(f"loose {e['offset']}: unencodable ({exc}) :: {text!r}")
            continue
        orig = list(struct.unpack_from("<%dH" % budget, data, off))
        toks = reserve_leading_cells(orig) + toks
        if len(toks) > budget:
            problems.append(f"loose {e['offset']}: {len(toks)}>{budget} :: {text!r}")
            continue
        struct.pack_into("<%dH" % budget, data, off, *(toks + [FFFF] * (budget - len(toks))))
        changed += 1
    for gi, (table_off, table, base) in enumerate(groups):
        n = len(table)
        last_off = base + table[-1] * 2
        group_end = last_off + (run_length(data, last_off) + 1) * 2
        blob_budget = (group_end - base) // 2     # words available for strings+terminators

        # Encode each string's new code sequence (or keep the original).
        seqs: list[list[int]] = []
        lens: list[int] = []
        for k in range(n):
            off = base + table[k] * 2
            orig_len = table[k + 1] - table[k] - 1 if k + 1 < n else run_length(data, off)
            lens.append(orig_len)
            orig = list(struct.unpack_from("<%dH" % orig_len, data, off)) if orig_len else []
            e = by_key.get((gi, k))
            text = (e.get("text") or "").rstrip() if e else ""  # keep leading layout spaces
            if not text:
                seqs.append(orig)
                continue
            if text == "{BLANK}":
                seqs.append([])
                changed += 1
                continue
            try:
                toks = codec.encode(text)
            except Exception as exc:
                problems.append(f"g{gi}#{k} {e['offset']}: unencodable ({exc}) :: {text!r}")
                seqs.append(orig)
                continue
            toks = reserve_leading_cells(orig) + toks
            cap = orig_len + args.max_grow if args.repack else orig_len
            if len(toks) > cap:
                problems.append(f"g{gi}#{k} {e['offset']}: line {len(toks)}>{cap} :: {text!r}")
                seqs.append(orig)
                continue
            seqs.append(toks)
            changed += 1

        if not args.repack:
            # In-place: keep the original table and each string's slot; only the
            # text inside changes (FFFF-padded). Byte-compatible, table untouched.
            for k, s in enumerate(seqs):
                off = base + table[k] * 2
                struct.pack_into("<%dH" % lens[k], data, off, *(s + [FFFF] * (lens[k] - len(s))))
            continue

        # --repack: regenerate the offset table and pack the string blob tight.
        new_table = [0]
        for s in seqs[:-1]:
            new_table.append(new_table[-1] + len(s) + 1)
        blob_words = new_table[-1] + len(seqs[-1]) + 1
        if blob_words > blob_budget:
            problems.append(f"group {gi} @ {table_off:#x}: blob {blob_words}>{blob_budget} words")
            continue
        struct.pack_into("<%dH" % n, data, table_off, *new_table)
        cur = base
        for s in seqs:
            if s:
                struct.pack_into("<%dH" % len(s), data, cur, *s)
            struct.pack_into("<H", data, cur + len(s) * 2, FFFF)
            cur += (len(s) + 1) * 2
        for off in range(cur, group_end, 2):
            struct.pack_into("<H", data, off, FFFF)

    system_out.parent.mkdir(parents=True, exist_ok=True)
    system_out.write_bytes(data)
    print(f"packed {changed} translated lines into {len(groups)} groups -> {system_out}")
    for p in problems:
        print("  PROBLEM", p)
    if problems and args.strict:
        sys.exit(1)


if __name__ == "__main__":
    main()
