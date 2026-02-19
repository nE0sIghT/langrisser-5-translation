#!/usr/bin/env python3
import argparse
import csv
import re
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

TAG_RE = re.compile(r"<\$([0-9A-Fa-f]{4})>")
BRACKET_RE = re.compile(r"\[([0-9A-Fa-f]{4})\]")
CTRL_RE = re.compile(r"\{([A-Za-z0-9_:]+)\}")


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


def parse_tokenized_words(tok: str) -> List[int]:
    out: List[int] = []
    i = 0
    n = len(tok)
    while i < n:
        m = BRACKET_RE.match(tok, i)
        if m:
            out.append(int(m.group(1), 16))
            i = m.end()
            continue

        c = CTRL_RE.match(tok, i)
        if c:
            tag = c.group(1).upper()
            if tag == "END":
                out.append(0xFFFF)
            elif tag == "BR":
                out.append(0xFFFE)
            elif tag == "DIALOG_CMD":
                out.append(0xFB00)
            elif tag.startswith("CTRL_") and len(tag) == 9:
                try:
                    out.append(int(tag[5:], 16))
                except Exception:
                    pass
            elif tag.startswith("FF:") and len(tag) == 5:
                try:
                    out.append(0xFF00 | int(tag[3:], 16))
                except Exception:
                    pass
            i = c.end()
            continue

        i += 1
    return out


def parse_decoded_words(decoded: str, txt2tok: Dict[str, int]) -> List[int]:
    out: List[int] = []
    i = 0
    n = len(decoded)
    keys = sorted(txt2tok.keys(), key=len, reverse=True)
    while i < n:
        m = TAG_RE.match(decoded, i)
        if m:
            out.append(int(m.group(1), 16))
            i = m.end()
            continue
        matched = False
        for k in keys:
            if k and decoded.startswith(k, i):
                out.append(txt2tok[k])
                i += len(k)
                matched = True
                break
        if matched:
            continue
        i += 1
    return out


def is_protected_arg(prev_word: int) -> bool:
    return prev_word in (0xF600, 0xFB00)


def is_printable_slot(word: int, prev_word: int | None) -> bool:
    if prev_word is not None and is_protected_arg(prev_word):
        return False
    return word < 0xE000


def render_words(words: List[int], _tok2txt: Dict[int, str]) -> str:
    # Use strict tag stream for deterministic re-encode (no ambiguous multi-char table entries).
    return "".join(f"<$%04X>" % w for w in words)


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


def patch_chunk_file(
    path: Path,
    chunk_idx: int,
    rep: Dict[Tuple[int, int], Tuple[str, str]],
    tok2txt: Dict[int, str],
    txt2tok: Dict[str, int],
    supported: set[str],
) -> Tuple[int, int]:
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
        # Canonical source is the current dump record itself; this preserves
        # exact per-record size/layout even when alignment-side tokenized rows
        # are noisy or merged.
        jp_words = parse_decoded_words(b, txt2tok)
        if not jp_words:
            jp_words = parse_tokenized_words(jp_tok)
        if not jp_words:
            out_lines.append("# " + ln)
            continue

        en_words: List[int] = []
        for ch in norm:
            tok = txt2tok.get(ch)
            if tok is not None:
                en_words.append(tok)

        printable_slots: List[int] = []
        prev: int | None = None
        for idx, w in enumerate(jp_words):
            if is_printable_slot(w, prev):
                printable_slots.append(idx)
            prev = w

        if len(en_words) > len(printable_slots):
            en_words = en_words[: len(printable_slots)]

        space_tok = txt2tok.get(" ", 0x0000)
        new_words = list(jp_words)
        for k, slot_idx in enumerate(printable_slots):
            if k < len(en_words):
                new_words[slot_idx] = en_words[k]
            else:
                new_words[slot_idx] = space_tok

        new_text = render_words(new_words, tok2txt)
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
    tok2txt, txt2tok = load_tbl_chars(Path(args.out_tbl))
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
            attempted, changed = patch_chunk_file(fp, cidx, rep, tok2txt, txt2tok, supported)
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
