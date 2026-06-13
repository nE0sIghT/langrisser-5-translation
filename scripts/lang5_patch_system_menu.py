#!/usr/bin/env python3
"""Patch SYSTEM.BIN menu/UI strings using the decoded-run dictionary.

Strings are FFFF-terminated token runs at fixed offsets, so an EN
replacement must fit into the run's printable slots. The EN table includes
pair glyphs (two letters per cell), which makes most labels fit. Runs whose
translation does not fit are reported and left untouched.

Two passes: first whole runs between FFFF terminators are matched against
the map; then the file is scanned for verbatim leftover JP strings (token
sequence + FFFF). The second pass catches strings preceded by binary data
instead of a terminator (the first entry of each name table, strings inside
unit records), which the run splitter merges into overlong junk runs.
"""
import argparse
import csv
import json
import struct
from pathlib import Path

from lang5_scen import Codec, load_charmap_csv, load_charmap_tbl

ASCII_NORMALIZE = str.maketrans({"?": "？", "!": "！", "’": "'", "‘": "'"})


def encode_replacement(en: str, seg: list[int], codec: Codec) -> list[int]:
    """Encode a SYSTEM replacement without folding leading reserved spaces.

    Some save/menu templates start with literal 0x0000 cells that the game
    later uses as an overlay field (for example the scenario number in save
    titles). The compact encoder can otherwise merge the last reserved space
    with the first Latin letter into a " space+letter" pair, which makes the
    runtime overlay draw on top of the Latin glyph.
    """
    text = en.translate(ASCII_NORMALIZE)
    lead_zeroes = 0
    for w in seg:
        if w != 0x0000:
            break
        lead_zeroes += 1
    if not lead_zeroes:
        return codec.encode(text)

    stripped = text
    removed = 0
    while removed < lead_zeroes and stripped.startswith(" "):
        stripped = stripped[1:]
        removed += 1
    space = codec.char2tok.get(" ", 0)
    return [space] * lead_zeroes + codec.encode(stripped)


def decode_run(words: list[int], tok2ch: dict[int, str]) -> str:
    out = []
    for w in words:
        if w in tok2ch:
            out.append(tok2ch[w])
        elif w >= 0xFF00:
            out.append("{%04X}" % w)
        else:
            out.append("[%04X]" % w)
    return "".join(out)


def split_ffff_runs(words: list[int], min_len: int = 2, max_len: int = 80):
    runs = []
    start = 0
    for i, w in enumerate(words):
        if w != 0xFFFF:
            continue
        if min_len <= i + 1 - start <= max_len:
            runs.append((start, i + 1))
        start = i + 1
    return runs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--system-in", default="work/extracted/SYSTEM.BIN")
    ap.add_argument("--system-out", default="work/build/SYSTEM.BIN.menu")
    ap.add_argument("--groups-report", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--tbl", default="work/tables/lang5_en.tbl")
    ap.add_argument("--menu-map", action="append", default=None,
                    help="Translation map JSON (repeatable).")
    ap.add_argument("--min-offset", type=lambda x: int(x, 0), default=0x8100,
                    help="Do not touch runs below this byte offset.")
    ap.add_argument("--report-csv", default="work/scen_analysis/system_menu_occurrences.csv")
    args = ap.parse_args()

    tok2ch = load_charmap_csv(Path(args.groups_report))
    codec = Codec(load_charmap_tbl(Path(args.tbl)))
    menu_map: dict[str, str] = {}
    for mp in args.menu_map or ["data/translation/system_menu_map.json"]:
        menu_map.update(json.loads(Path(mp).read_text(encoding="utf-8")))

    src = Path(args.system_in).read_bytes()
    words = list(struct.unpack(f"<{len(src)//2}H", src[: len(src) & ~1]))

    patched = misfit = 0
    rows = []
    for a, b in split_ffff_runs(words):
        if a * 2 < args.min_offset:
            continue  # font plane + offset tables; never patch there
        seg = words[a:b]
        dec = decode_run(seg, tok2ch)
        en = menu_map.get(dec)
        status = ""
        if en:
            slots = [i for i, w in enumerate(seg) if w < 0xE000]
            try:
                toks = encode_replacement(en, seg, codec)
            except ValueError as exc:
                rows.append({"offset_hex": f"0x{a*2:05X}", "word_count": str(len(seg)),
                             "decoded_jp": dec, "mapped_en": en,
                             "status": f"UNENCODABLE {exc}"})
                misfit += 1
                continue
            if len(toks) > len(slots):
                status = f"MISFIT {len(toks)}>{len(slots)}"
                misfit += 1
            else:
                out = list(seg)
                space = codec.char2tok.get(" ", 0)
                for k, idx in enumerate(slots):
                    out[idx] = toks[k] if k < len(toks) else space
                words[a:b] = out
                patched += 1
                status = "ok"
        rows.append({"offset_hex": f"0x{a*2:05X}", "word_count": str(len(seg)),
                     "decoded_jp": dec, "mapped_en": en or "", "status": status})

    # Second pass: scan for verbatim JP strings the run splitter missed.
    ch2tok_jp: dict[str, int] = {}
    for tok, ch in tok2ch.items():
        if len(ch) == 1 and ch not in ch2tok_jp:
            ch2tok_jp[ch] = tok

    candidates = []
    for dec, en in menu_map.items():
        body = dec[: -len("{FFFF}")]
        if not en or not dec.endswith("{FFFF}") or "{" in body or len(body) < 2:
            continue
        try:
            jp = [ch2tok_jp[c] for c in body]
        except KeyError:
            continue
        candidates.append((jp, dec, en))
    # Longest first so a key never patches the tail of a longer JP string.
    candidates.sort(key=lambda kv: len(kv[0]), reverse=True)

    blob = bytearray(struct.pack(f"<{len(words)}H", *words))
    GLYPH_MAX = 1820

    def at_string_start(i: int) -> bool:
        """A match must begin a string, not continue one: tails of longer
        strings (装備 inside 剣装備) and words inside untranslated
        descriptions must stay untouched. A string starts after a
        terminator, a padding space, a non-glyph word, or the tail of an
        ascending small-step offset table that indexes the string block."""
        if i <= args.min_offset:
            return True
        prev = struct.unpack_from("<H", blob, i - 2)[0]
        if prev in (0x0000, 0xFFFF) or prev > GLYPH_MAX:
            return True
        if i < 8:
            return False
        w = struct.unpack_from("<4H", blob, i - 8)
        return all(0 < w[k + 1] - w[k] <= 16 for k in range(3))

    space = None
    for jp, dec, en in candidates:
        try:
            toks = codec.encode(en.translate(ASCII_NORMALIZE))
        except ValueError:
            continue
        if len(toks) > len(jp):
            continue  # does not fit; first pass already reported the misfit
        if space is None:
            space = codec.char2tok.get(" ", 0)
        pat = struct.pack(f"<{len(jp) + 1}H", *jp, 0xFFFF)
        new = struct.pack(f"<{len(jp)}H", *(toks + [space] * (len(jp) - len(toks))))
        start = args.min_offset
        while True:
            i = blob.find(pat, start)
            if i < 0:
                break
            if i % 2:
                start = i + 1
                continue
            if not at_string_start(i):
                start = i + 2
                continue
            if blob[i : i + len(new)] != new:
                blob[i : i + len(new)] = new
                patched += 1
                rows.append({"offset_hex": f"0x{i:05X}",
                             "word_count": str(len(jp) + 1),
                             "decoded_jp": dec, "mapped_en": en,
                             "status": "ok-scan"})
            start = i + len(pat)

    out_path = Path(args.system_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(blob) + src[len(words) * 2 :])

    rep = Path(args.report_csv)
    rep.parent.mkdir(parents=True, exist_ok=True)
    with rep.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["offset_hex", "word_count", "decoded_jp", "mapped_en", "status"])
        w.writeheader()
        w.writerows(rows)

    print(f"patched_runs={patched} misfits={misfit} out={out_path} report={rep}")


if __name__ == "__main__":
    main()
