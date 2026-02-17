#!/usr/bin/env python3
import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

CTRL_RE = re.compile(r"\{[^}]+\}")
TOK_RE = re.compile(r"\[[0-9A-Fa-f]{4}\]")
TOK_CAPTURE_RE = re.compile(r"\[([0-9A-Fa-f]{4})\]")


def normalize_jp_text(s: str) -> str:
    s = (s or "").strip()
    s = CTRL_RE.sub("", s)
    s = TOK_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_en_text(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def load_font_map(path: Path) -> Dict[int, str]:
    out: Dict[int, str] = {}
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        for row in csv.DictReader(fh):
            ch = (row.get("char") or "")
            if not ch:
                continue
            try:
                idx = int((row.get("index_dec") or "").strip())
            except ValueError:
                continue
            out[idx] = ch
    return out


def decode_tokenized(tok: str, font_map: Dict[int, str]) -> str:
    def sub(m: re.Match) -> str:
        t = int(m.group(1), 16)
        return font_map.get(t, f"<${t:04X}>")
    return TOK_CAPTURE_RE.sub(sub, tok or "")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build canonical JP<->EN JSON mapping from alignment CSV.")
    ap.add_argument("--alignment", default="work/scen_analysis/story_alignment_partial_decode.csv")
    ap.add_argument("--font-map", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--out", default="data/translation/jp_en_mapping.json")
    args = ap.parse_args()

    rows: List[Dict] = []
    jp_to_en: Dict[str, Dict] = {}
    en_to_jp: Dict[str, Dict] = {}
    by_record: Dict[str, Dict] = {}
    scenario_counts = defaultdict(int)
    font_map = load_font_map(Path(args.font_map))

    with Path(args.alignment).open("r", encoding="utf-8", errors="ignore") as fh:
        for row_idx, row in enumerate(csv.DictReader(fh), start=1):
            en = normalize_en_text(row.get("en_line", ""))
            ridx = (row.get("jp_record_index") or "").strip()

            chunk_raw = (row.get("chunk_index") or "").strip()
            scenario = (row.get("scenario") or "").strip()
            jp_tok = (row.get("jp_tokenized") or "").strip()
            jp_dec = decode_tokenized(jp_tok, font_map) if jp_tok else ""
            jp_norm = normalize_jp_text(jp_dec)
            unresolved = bool(TOK_RE.search(jp_dec))

            try:
                chunk = int(chunk_raw)
            except ValueError:
                chunk = -1
            try:
                rec = int(ridx)
            except ValueError:
                rec = -1

            rec_key = f"{chunk:03d}:{rec:04d}" if chunk >= 0 and rec >= 0 else f"ROW:{row_idx:05d}"
            rec_obj = {
                "scenario": scenario,
                "chunk_index": chunk,
                "record_index": rec,
                "seq": int((row.get("seq") or "0").strip() or 0),
                "jp_tokenized": jp_tok,
                "jp_decoded_from_font_map": jp_dec,
                "jp_normalized": jp_norm,
                "en_line": en,
                "has_unresolved_tokens": unresolved,
            }
            rows.append(rec_obj)
            by_record[rec_key] = rec_obj
            scenario_counts[scenario] += 1

            if jp_norm and en:
                slot = jp_to_en.setdefault(
                    jp_norm, {"en_candidates": defaultdict(int), "example_records": [], "has_unresolved_tokens": False}
                )
                slot["en_candidates"][en] += 1
                if len(slot["example_records"]) < 6:
                    slot["example_records"].append(rec_key)
                slot["has_unresolved_tokens"] = slot["has_unresolved_tokens"] or unresolved

            if en:
                rev = en_to_jp.setdefault(
                    en, {"jp_candidates": defaultdict(int), "example_records": [], "has_unresolved_tokens": False}
                )
                jp_candidate = jp_norm if jp_norm else jp_dec
                rev["jp_candidates"][jp_candidate] += 1
                if len(rev["example_records"]) < 6:
                    rev["example_records"].append(rec_key)
                rev["has_unresolved_tokens"] = rev["has_unresolved_tokens"] or unresolved

    def finalize_bucket(bucket: Dict[str, Dict], field_name: str) -> Dict[str, Dict]:
        out: Dict[str, Dict] = {}
        for key, value in bucket.items():
            ranked = sorted(value[field_name].items(), key=lambda x: (-x[1], x[0]))
            out[key] = {
                field_name: [{"text": t, "count": c} for t, c in ranked],
                "example_records": value["example_records"],
                "has_unresolved_tokens": value["has_unresolved_tokens"],
            }
        return out

    out_obj = {
        "meta": {
            "source_alignment_csv": str(Path(args.alignment)),
            "source_font_map_csv": str(Path(args.font_map)),
            "mapping_rows": len(rows),
            "unique_jp_normalized": len(jp_to_en),
            "unique_en_lines": len(en_to_jp),
            "scenarios": dict(sorted(scenario_counts.items(), key=lambda x: x[0])),
            "note": "Derived from scenario alignment CSV; quiz/tutorial coverage depends on source alignment.",
        },
        "by_record": dict(sorted(by_record.items(), key=lambda x: x[0])),
        "jp_to_en": finalize_bucket(jp_to_en, "en_candidates"),
        "en_to_jp": finalize_bucket(en_to_jp, "jp_candidates"),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_path}")
    print(
        f"rows={len(rows)} unique_jp={len(jp_to_en)} unique_en={len(en_to_jp)} "
        f"scenarios={len(scenario_counts)}"
    )


if __name__ == "__main__":
    main()
