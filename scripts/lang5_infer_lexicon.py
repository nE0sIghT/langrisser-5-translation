#!/usr/bin/env python3
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


TOK_RE = re.compile(r"\[([0-9A-F]{4})\]")
CTRL_RE = re.compile(r"\{[A-Z0-9_:]+\}")
SPEAKER_RE = re.compile(r"^([A-Za-z][A-Za-z0-9' .-]{1,30})\s*:\s*(.+)$")
BAD_SPEAKER_WORDS = {
    "victory",
    "defeat",
    "requirement",
    "requirements",
    "ennemies",
    "enemies",
    "renforts",
    "optional",
}

# Confirmed token map seed from community reverse-engineering:
# [00C6][00CD][00B2][0086][00D1][00A6][020E][020F] -> ランフォード元帥
KNOWN_TOKEN_MAP = {
    "00C6": "ラ",
    "00CD": "ン",
    "00B2": "フ",
    "0086": "ォ",
    "00D1": "ー",
    "00A6": "ド",
    "020E": "元",
    "020F": "帥",
}


def extract_hex_tokens(tokenized: str) -> List[str]:
    out = []
    for m in TOK_RE.finditer(tokenized):
        out.append(m.group(1))
    return out


def tokens_before_first_ctrl(tokenized: str) -> List[str]:
    parts = CTRL_RE.split(tokenized, maxsplit=1)
    return extract_hex_tokens(parts[0] if parts else tokenized)


def sanitize_name(name: str) -> str:
    return name.strip().replace("  ", " ")


def likely_real_speaker(name: str) -> bool:
    low = name.lower()
    if any(w in low for w in BAD_SPEAKER_WORDS):
        return False
    # Prefer proper names/titles, avoid long sentence-like labels.
    if len(name.split()) > 3:
        return False
    return True


def build_speaker_lexicon(rows: List[Dict[str, str]]) -> Dict[str, Dict]:
    by_name: Dict[str, Counter] = defaultdict(Counter)
    by_cmd: Dict[str, Counter] = defaultdict(Counter)

    for r in rows:
        en = r["en_line"].strip()
        jp = r["jp_tokenized"].strip()
        if not en or not jp:
            continue
        m = SPEAKER_RE.match(en)
        if not m:
            continue
        name = sanitize_name(m.group(1))
        if not likely_real_speaker(name):
            continue
        if "{DIALOG_CMD}" not in jp:
            continue
        prefix = tuple(tokens_before_first_ctrl(jp)[:10])
        if len(prefix) < 2:
            continue
        by_name[name][prefix] += 1

        # record trailing dialog command id if present
        cmd = re.search(r"\{DIALOG_CMD\}\[([0-9A-F]{4})\]$", jp)
        if cmd:
            by_cmd[name][cmd.group(1)] += 1

    out = {}
    for name, ctr in by_name.items():
        seq, count = ctr.most_common(1)[0]
        out[name] = {
            "best_prefix_tokens": list(seq),
            "samples": count,
            "top_prefixes": [
                {"tokens": list(t), "count": c}
                for t, c in ctr.most_common(5)
            ],
            "top_dialog_cmds": [
                {"cmd": cmd, "count": c}
                for cmd, c in by_cmd.get(name, Counter()).most_common(5)
            ],
        }
    return out


def apply_partial_decode(tokenized: str, lex: Dict[str, Dict]) -> str:
    toks = extract_hex_tokens(tokenized)
    # Prefix substitution for likely speaker names.
    out = tokenized
    for name, info in lex.items():
        pref = info["best_prefix_tokens"]
        if len(pref) >= 2 and toks[: len(pref)] == pref:
            # Replace only the first exact token sequence.
            needle = "".join(f"[{t}]" for t in pref)
            out = out.replace(needle, f"<{name}>", 1)
            break

    # Token-level JP decode for confirmed mappings.
    def _decode_token(m: re.Match) -> str:
        tok = m.group(1)
        return KNOWN_TOKEN_MAP.get(tok, m.group(0))

    out = TOK_RE.sub(_decode_token, out)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Infer speaker/token lexicon from aligned Langrisser V story dump.")
    p.add_argument("--alignment", default="work/scen_analysis/story_alignment_preview.csv")
    p.add_argument("--out-dir", default="work/scen_analysis")
    args = p.parse_args()

    align_path = Path(args.alignment)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, str]] = []
    with align_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows.extend(reader)

    lex = build_speaker_lexicon(rows)
    (out_dir / "speaker_lexicon.json").write_text(json.dumps(lex, ensure_ascii=False, indent=2))

    out_rows = []
    for r in rows:
        decoded = apply_partial_decode(r["jp_tokenized"], lex) if r["jp_tokenized"] else ""
        out_rows.append(
            {
                "scenario": r["scenario"],
                "chunk_index": r["chunk_index"],
                "seq": r["seq"],
                "jp_record_index": r["jp_record_index"],
                "jp_tokenized": r["jp_tokenized"],
                "jp_partially_decoded": decoded,
                "en_line": r["en_line"],
            }
        )

    out_csv = out_dir / "story_alignment_partial_decode.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "scenario",
                "chunk_index",
                "seq",
                "jp_record_index",
                "jp_tokenized",
                "jp_partially_decoded",
                "en_line",
            ],
        )
        w.writeheader()
        w.writerows(out_rows)

    print(f"wrote {out_dir / 'speaker_lexicon.json'}")
    print(f"wrote {out_csv}")


if __name__ == "__main__":
    main()
