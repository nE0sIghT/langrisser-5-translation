#!/usr/bin/env python3
"""Audit the Saturn<->PS1 SCEN correspondence; PS1 is a reference only.

For every non-empty block, the monotone stable-signature alignment proves
which Saturn entries may take the PS1 record's translation. Every entry with
no proven counterpart carries Saturn-edited content and must be resolved with
a platform record (translated from the Saturn original) — until then it is
explicitly preserved in `scen_mapping.json` with `"pending_review": true`.

Outputs:

- a review report with the Saturn original decoded through the *derived*
  Saturn kanji map (built from thousands of matched-pair token positions),
  the closest PS1 record and its current ru/en translations — everything a
  translator needs to author the platform record;
- with `--write-mapping`, a minimal `scen_mapping.json`: the automatic
  alignment needs no ranges, so chunk specs shrink to the exceptional
  entries (platform records carried over, the rest preserve/pending).
"""

from __future__ import annotations

import argparse
import difflib
import json
from collections import Counter, defaultdict
from pathlib import Path

from lang5_saturn_apply import (Normalizer, load_mapping, monotone_alignment,
                                ps1_chunk_records, stable_signature)
from lang5_sceninsert import parse_dump_file
from lang5_project import COMMON_FONT_MAP
from saturn_scen import local_index_entries, parse_catalog

import csv


def ps1_charmap() -> dict[int, str]:
    out: dict[int, str] = {}
    for row in csv.DictReader(open(COMMON_FONT_MAP, encoding="utf-8")):
        if row["index_dec"].isdigit() and row["char"]:
            out[int(row["index_dec"])] = row["char"]
    return out


def derive_saturn_kanji_map(sat: bytes, ps1: bytes, empty: set[int],
                            ps1map: dict[int, str]) -> dict[int, str]:
    """Vote Saturn kanji meanings from positionally-matched record pairs."""
    votes: dict[int, Counter] = defaultdict(Counter)
    for ci, (s, u) in enumerate(parse_catalog(sat)):
        if ci in empty:
            continue
        entries = local_index_entries(sat, s, u)
        if entries is None:
            continue
        ps1_tokens = ps1_chunk_records(ps1, ci)
        mapping, _ = monotone_alignment(entries, ps1_tokens, None)
        for si, pr in mapping.items():
            se, pe = entries[si], ps1_tokens[pr - 1]
            if len(se) != len(pe):
                continue
            for wsat, wps in zip(se, pe):
                if wsat != wps and wsat < 0xE000 and wps < 0xE000:
                    votes[wsat][wps] += 1
    out: dict[int, str] = {}
    for wsat, counter in votes.items():
        (wps, n), *rest = counter.most_common(2)
        if n >= 2 and (not rest or n >= 3 * rest[0][1]):
            if wps in ps1map:
                out[wsat] = ps1map[wps]
    return out


def decoder(charmap: dict[int, str]):
    def dec(words: list[int]) -> str:
        parts: list[str] = []
        for w in words:
            if w == 0xFFFC:
                parts.append("\\n")
            elif w == 0xFFFD:
                parts.append("<PAGE>")
            elif w >= 0xFB00:
                parts.append(f"{{{w:04X}}}")
            else:
                parts.append(charmap.get(w, "?"))
        return "".join(parts)
    return dec


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scen", default="work/build/saturn/SCEN.DAT")
    ap.add_argument("--ps1-scen", default="work/extracted/SCEN.DAT")
    ap.add_argument("--mapping", default="data/platforms/saturn/scen_mapping.json")
    ap.add_argument("--ru-root", default="data/lang/ru/SCEN")
    ap.add_argument("--en-root", default="data/lang/en/SCEN")
    ap.add_argument("--out-report", default="work/build/saturn/scen_platform_review.md")
    ap.add_argument("--out-kanji-map", default="work/build/saturn/saturn_kanji_map.json")
    ap.add_argument("--write-mapping", action="store_true",
                    help="Rewrite the chunk specs to the minimal exceptional form.")
    ap.add_argument("--auto-resolve", action="store_true",
                    help="Author platform records automatically where the Saturn "
                         "original provably equals some PS1 record (duplicates / "
                         "reordered lines), copying that record's ru/en text.")
    args = ap.parse_args()

    sat = Path(args.scen).read_bytes()
    ps1 = Path(args.ps1_scen).read_bytes()
    mapping = load_mapping(Path(args.mapping))
    empty = {int(x) for x in mapping.get("empty_chunks", [])}
    chunk_specs = {int(k): v for k, v in (mapping.get("chunks") or {}).items()}

    ps1map = ps1_charmap()
    satkanji = derive_saturn_kanji_map(sat, ps1, empty, ps1map)
    merged = dict(ps1map)
    merged.update(satkanji)
    Path(args.out_kanji_map).write_text(
        json.dumps({f"{k:04X}": v for k, v in sorted(satkanji.items())},
                   ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    dec_sat = decoder(merged)
    dec_ps1 = decoder(ps1map)
    norm = Normalizer(ps1map, satkanji)

    report: list[str] = [
        "# Saturn-edited SCEN records pending platform translations",
        "",
        "Each entry's JP original differs from every PS1 record "
        "(stable-signature proof). Saturn kanji are decoded through the "
        "derived map; `?` marks tokens the vote could not resolve.",
        "",
    ]
    new_chunks: dict[str, dict] = {}
    pending_total = 0
    platform_total = 0
    for ci, (s, u) in enumerate(parse_catalog(sat)):
        if ci in empty:
            continue
        entries = local_index_entries(sat, s, u)
        if entries is None:
            continue
        ps1_tokens = ps1_chunk_records(ps1, ci)
        _, unmatched = monotone_alignment(entries, ps1_tokens, norm)
        old_spec = chunk_specs.get(ci, {})
        platform_entries = {
            int(item["saturn"]): item
            for item in old_spec.get("entries", [])
            if "platform" in item
        }
        keep: list[dict] = []
        chunk_report: list[str] = []
        ru = parse_dump_file(Path(args.ru_root) / f"chunk_{ci:03d}.txt") \
            if (Path(args.ru_root) / f"chunk_{ci:03d}.txt").exists() else {}
        en = parse_dump_file(Path(args.en_root) / f"chunk_{ci:03d}.txt") \
            if (Path(args.en_root) / f"chunk_{ci:03d}.txt").exists() else {}
        ps_sigs = [stable_signature(t) for t in ps1_tokens]

        def strip_tail(tokens: list[int]) -> tuple[int, ...]:
            t = tuple(tokens)
            while t and t[-1] == 0xFFFF:
                t = t[:-1]
            return t

        def provably_equal_record(si: int) -> int | None:
            """A PS1 record (1-based) whose JP provably equals the Saturn entry.

            Either exact token equality (kana/ASCII lines, duplicates moved
            around), or equality of the decoded strings where every Saturn
            kanji resolved through the derived map — same text, only the
            reordered kanji token ids differ.
            """
            mine = strip_tail(entries[si])
            for r, pt in enumerate(ps1_tokens):
                if strip_tail(pt) == mine:
                    return r + 1
            sat_txt = dec_sat(list(mine))
            if "?" in sat_txt:
                return None
            for r, pt in enumerate(ps1_tokens):
                if dec_ps1(list(strip_tail(pt))) == sat_txt:
                    return r + 1
            return None

        auto_writes: dict[int, int] = {}
        for si in unmatched:
            if si in platform_entries:
                keep.append(platform_entries[si])
                platform_total += 1
                continue
            if args.auto_resolve:
                r = provably_equal_record(si)
                if r is not None and r in ru and r in en:
                    auto_writes[si] = r
                    keep.append({"saturn": si, "platform": si,
                                 "auto_from_ps1": r})
                    platform_total += 1
                    continue
            keep.append({"saturn": si, "preserve": True, "pending_review": True})
            pending_total += 1
            sig = stable_signature(entries[si])
            best = max(
                range(len(ps1_tokens)),
                key=lambda k: difflib.SequenceMatcher(
                    a=sig, b=ps_sigs[k], autojunk=False).ratio(),
                default=None,
            )
            chunk_report.append(f"### chunk {ci:03d} entry {si}")
            chunk_report.append(f"- SAT JP: `{dec_sat(entries[si])}`")
            if best is not None:
                chunk_report.append(f"- closest PS1 record {best + 1}:")
                chunk_report.append(f"  - JP: `{dec_ps1(ps1_tokens[best])}`")
                if best + 1 in ru:
                    chunk_report.append(f"  - RU: `{ru[best + 1]}`")
                if best + 1 in en:
                    chunk_report.append(f"  - EN: `{en[best + 1]}`")
            chunk_report.append("")
        for root, records_map in ((Path(args.ru_root), ru), (Path(args.en_root), en)):
            if not auto_writes:
                break
            pfile = root.parent / "platforms" / "saturn" / "SCEN" / f"chunk_{ci:03d}.txt"
            existing = parse_dump_file(pfile) if pfile.exists() else {}
            additions = [
                f"{si}\t{records_map[r]}"
                for si, r in sorted(auto_writes.items())
                if si not in existing
            ]
            if additions:
                header = ("# Auto-resolved Saturn records: the JP original provably "
                          "equals the named PS1 record (duplicate/reordered line).\n"
                          if not pfile.exists() else "")
                pfile.parent.mkdir(parents=True, exist_ok=True)
                with pfile.open("a", encoding="utf-8") as f:
                    f.write(header + "\n".join(additions) + "\n")
        if keep:
            new_chunks[str(ci)] = {"entries": keep}
        if chunk_report:
            report.append(f"## chunk {ci:03d} — {len(chunk_report) // 6 + 1} records")
            report.extend(chunk_report)

    Path(args.out_report).write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"audit: {platform_total} platform records, {pending_total} pending "
          f"preserve entries; kanji map {len(satkanji)} tokens")
    print(f"report -> {args.out_report}")
    if args.write_mapping:
        mapping["chunks"] = new_chunks
        Path(args.mapping).write_text(
            json.dumps(mapping, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        print(f"mapping rewritten (minimal specs) -> {args.mapping}")


if __name__ == "__main__":
    main()
