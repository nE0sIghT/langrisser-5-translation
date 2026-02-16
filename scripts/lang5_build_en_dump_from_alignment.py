#!/usr/bin/env python3
import argparse
import csv
import re
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

TAG_RE = re.compile(r"<\$([0-9A-Fa-f]{4})>")
BRACKET_RE = re.compile(r"\[([0-9A-Fa-f]{4})\]")


def load_tbl_chars(tbl_path: Path) -> Tuple[Dict[int, str], Dict[str, int]]:
    tok2txt: Dict[int, str] = {}
    txt2tok: Dict[str, int] = {}
    for raw in tbl_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = raw.rstrip("\n")
        if not s.strip() or s.lstrip().startswith("#") or "=" not in s:
            continue
        a, b = s.split("=", 1)
        try:
            tok = int(a.strip(), 16)
        except Exception:
            continue
        txt = b
        if not txt:
            continue
        tok2txt[tok] = txt
        if txt not in txt2tok:
            txt2tok[txt] = tok
    return tok2txt, txt2tok


def patch_tbl_with_space(tbl_path: Path, out_path: Path) -> None:
    lines = tbl_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    has_space = False
    out_lines: List[str] = []
    for ln in lines:
        if ln.strip().upper().startswith("0000="):
            out_lines.append("0000= ")
            has_space = True
        else:
            out_lines.append(ln)
    if not has_space:
        out_lines.append("0000= ")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


def controls_from_tokenized(tok: str) -> str:
    out: List[int] = []
    i = 0
    n = len(tok)
    need_dialog_arg = False

    while i < n:
        if tok.startswith("{END}", i):
            out.append(0xFFFF)
            i += 5
            continue
        if tok.startswith("{BR}", i):
            out.append(0xFFFE)
            i += 4
            continue
        if tok.startswith("{CTRL_FFFC}", i):
            out.append(0xFFFC)
            i += 11
            continue
        if tok.startswith("{DIALOG_CMD}", i):
            out.append(0xFB00)
            need_dialog_arg = True
            i += 12
            continue
        if tok.startswith("{FF:", i) and i + 7 <= n and tok[i + 6] == "}":
            try:
                vv = int(tok[i + 4 : i + 6], 16)
                out.append(0xFF00 | vv)
                i += 7
                continue
            except Exception:
                pass

        m = BRACKET_RE.match(tok, i)
        if m:
            w = int(m.group(1), 16)
            if need_dialog_arg:
                out.append(w)
                need_dialog_arg = False
            elif w >= 0xFF00 or w == 0xF600:
                out.append(w)
            i = m.end()
            continue

        i += 1

    return "".join(f"<$%04X>" % w for w in out)


def controls_from_decoded(decoded: str) -> str:
    toks: List[int] = [int(m.group(1), 16) for m in TAG_RE.finditer(decoded)]
    out: List[int] = []
    i = 0
    while i < len(toks):
        w = toks[i]
        if w >= 0xFF00:
            out.append(w)
        elif w in (0xFB00, 0xF600):
            out.append(w)
            if i + 1 < len(toks):
                out.append(toks[i + 1])
                i += 1
        i += 1
    return "".join(f"<$%04X>" % w for w in out)


def normalize_english(text: str, supported: set[str]) -> str:
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,!?;:'\"-()[]/%&@+*=<>~_\\/")
    s = (text or "").strip()
    if not s:
        return ""

    s = (
        s.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2026", "...")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u00a0", " ")
    )

    char_map = {
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "？": "?",
        "！": "!",
        "：": ":",
        "，": ",",
        "．": ".",
        "％": "%",
        "＆": "&",
        "＠": "@",
        "　": " ",
    }

    out: List[str] = []
    for ch in s:
        mapped = char_map.get(ch, "")
        if mapped:
            for mc in mapped:
                if mc in supported and mc in allowed:
                    out.append(mc)
            continue
        if ch in supported and ch in allowed:
            out.append(ch)
            continue

    txt = "".join(out)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def load_alignment(path: Path) -> Dict[Tuple[int, int], Tuple[str, str]]:
    rep: Dict[Tuple[int, int], Tuple[str, str]] = {}
    with path.open(encoding="utf-8", errors="ignore") as fh:
        for row in csv.DictReader(fh):
            en = (row.get("en_line") or "").strip()
            ridx_s = (row.get("jp_record_index") or "").strip()
            if not en or not ridx_s:
                continue
            try:
                chunk = int(row.get("chunk_index") or "")
                ridx = int(ridx_s)
            except Exception:
                continue
            jp_tok = row.get("jp_tokenized") or ""
            rep[(chunk, ridx)] = (en, jp_tok)
    return rep


def token_count_from_decoded(s: str) -> int:
    count = 0
    i = 0
    n = len(s)
    while i < n:
        m = TAG_RE.match(s, i)
        if m:
            count += 1
            i = m.end()
        else:
            count += 1
            i += 1
    return count


def patch_chunk_file(path: Path, chunk_idx: int, rep: Dict[Tuple[int, int], Tuple[str, str]], supported: set[str]) -> Tuple[int, int]:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    out_lines: List[str] = []
    changed = 0
    attempted = 0

    for ln in lines:
        if not ln or ln.startswith("#") or "\t" not in ln:
            out_lines.append(ln)
            continue
        a, b = ln.split("\t", 1)
        try:
            ridx = int(a.strip())
        except Exception:
            out_lines.append(ln)
            continue

        key = (chunk_idx, ridx)
        if key not in rep:
            out_lines.append("# " + ln)
            continue

        attempted += 1
        en_line, jp_tok = rep[key]
        norm = normalize_english(en_line, supported)
        ctrl = controls_from_tokenized(jp_tok)
        if not ctrl:
            ctrl = controls_from_decoded(b)
        orig_budget = token_count_from_decoded(b)
        ctrl_tokens = len(TAG_RE.findall(ctrl))
        text_budget = max(0, orig_budget - ctrl_tokens)
        if len(norm) > text_budget:
            norm = norm[:text_budget]

        new_text = (norm + ctrl) if norm else ctrl
        if not new_text:
            out_lines.append("# " + ln)
            continue

        new_ln = f"{ridx}\t{new_text}"
        if new_ln != ln:
            changed += 1
        out_lines.append(new_ln)

    path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return attempted, changed


def main() -> None:
    ap = argparse.ArgumentParser(description="Build English-edited scriptdump from alignment CSV.")
    ap.add_argument("--src-dump", default="work/scriptdump_groups")
    ap.add_argument("--alignment", default="work/scen_analysis/story_alignment_partial_decode.csv")
    ap.add_argument("--tbl", default="work/lang5_lang3_format/scripts/jp/lang5.tbl")
    ap.add_argument("--out-dump", default="work/scriptdump_en")
    ap.add_argument("--out-tbl", default="work/tables/lang5_en_insert.tbl")
    args = ap.parse_args()

    src_dump = Path(args.src_dump)
    out_dump = Path(args.out_dump)
    if out_dump.exists():
        shutil.rmtree(out_dump)
    shutil.copytree(src_dump, out_dump)

    patch_tbl_with_space(Path(args.tbl), Path(args.out_tbl))
    _, txt2tok = load_tbl_chars(Path(args.out_tbl))
    supported = set(txt2tok.keys())

    rep = load_alignment(Path(args.alignment))

    total_attempted = 0
    total_changed = 0
    chunk_hits = 0

    for stem in ("SCEN", "SCEN2"):
        root = out_dump / stem
        if not root.exists():
            continue
        for fp in sorted(root.glob("chunk_*.txt")):
            m = re.match(r"chunk_(\d+)\.txt$", fp.name)
            if not m:
                continue
            cidx = int(m.group(1))
            attempted, changed = patch_chunk_file(fp, cidx, rep, supported)
            if attempted:
                chunk_hits += 1
            total_attempted += attempted
            total_changed += changed

    print(f"out_dump={out_dump}")
    print(f"out_tbl={args.out_tbl}")
    print(f"alignment_replacements={len(rep)}")
    print(f"attempted={total_attempted} changed={total_changed} chunks_touched={chunk_hits}")


if __name__ == "__main__":
    main()
