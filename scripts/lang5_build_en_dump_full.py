#!/usr/bin/env python3
import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

TAG_RE = re.compile(r"<\$([0-9A-Fa-f]{4})>")
JP_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f]")


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
        if not b:
            continue
        tok2txt[tok] = b
        if b not in txt2tok:
            txt2tok[b] = tok
    return tok2txt, txt2tok


def patch_tbl_with_space(tbl_src: Path, tbl_out: Path) -> None:
    lines = tbl_src.read_text(encoding="utf-8", errors="ignore").splitlines()
    out_lines: List[str] = []
    has_space = False
    for ln in lines:
        if ln.strip().upper().startswith("0000="):
            out_lines.append("0000= ")
            has_space = True
        else:
            out_lines.append(ln)
    if not has_space:
        out_lines.append("0000= ")
    tbl_out.parent.mkdir(parents=True, exist_ok=True)
    tbl_out.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


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
    # Conservative argument protection for control opcodes.
    # Disasm confirms F600 and FBxx consume argument words; other Fxxx control
    # families may do the same in some paths, so keep following words intact.
    if prev_word == 0xF600:
        return True
    if 0xFB00 <= prev_word <= 0xFBFF:
        return True
    if 0xF600 <= prev_word <= 0xFEFF:
        return True
    return False


def is_printable_slot(word: int, prev_word: int | None) -> bool:
    if prev_word is not None and is_protected_arg(prev_word):
        return False
    return word < 0xE000


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
        .replace("（", "(")
        .replace("）", ")")
        .replace("【", "[")
        .replace("】", "]")
        .replace("？", "?")
        .replace("！", "!")
        .replace("：", ":")
        .replace("，", ",")
        .replace("．", ".")
        .replace("％", "%")
        .replace("＆", "&")
        .replace("＠", "@")
        .replace("　", " ")
    )
    out: List[str] = []
    for ch in s:
        if ch in supported and ch in allowed:
            out.append(ch)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def strip_tags(s: str) -> str:
    return TAG_RE.sub("", s or "")


def render_words(words: List[int]) -> str:
    return "".join(f"<$%04X>" % w for w in words)


def load_full_records(path: Path, skip_chunk0: bool = True) -> Dict[Tuple[str, int, int], str]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    recs = obj.get("records", [])
    out: Dict[Tuple[str, int, int], str] = {}
    for r in recs:
        en = (r.get("en_line") or "").strip()
        if not en:
            continue
        src = r.get("source_file", "")
        try:
            cidx = int(r.get("chunk_index"))
            ridx = int(r.get("record_index"))
        except Exception:
            continue
        if skip_chunk0 and cidx == 0:
            continue
        out[(src, cidx, ridx)] = en
    return out


def load_manual_overrides(path: Path) -> Dict[Tuple[str, int, int], str]:
    if not path.exists():
        return {}
    obj = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[Tuple[str, int, int], str] = {}
    for k, v in obj.items():
        if not isinstance(v, str) or not v.strip():
            continue
        # key format: SCEN.DAT:0:19
        parts = k.split(":")
        if len(parts) != 3:
            continue
        src = parts[0]
        try:
            cidx = int(parts[1])
            ridx = int(parts[2])
        except Exception:
            continue
        out[(src, cidx, ridx)] = v.strip()
    return out


def patch_chunk_file(
    source_file: str,
    path: Path,
    chunk_idx: int,
    rep: Dict[Tuple[str, int, int], str],
    txt2tok: Dict[str, int],
    supported: set[str],
) -> Tuple[int, int]:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    out_lines: List[str] = []
    attempted = 0
    changed = 0
    space_tok = txt2tok.get(" ", 0x0000)

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

        key = (source_file, chunk_idx, ridx)
        en_line = rep.get(key)
        if not en_line:
            out_lines.append("# " + ln)
            continue

        attempted += 1
        words = parse_decoded_words(b, txt2tok)
        if not words:
            out_lines.append(ln)
            continue

        en_words = [txt2tok[ch] for ch in normalize_english(en_line, supported) if ch in txt2tok]
        # Replace only printable, non-protected slots in-place.
        # Never change record shape / control ordering / argument positions.
        writable: List[int] = []
        prev: int | None = None
        for i, w in enumerate(words):
            if is_printable_slot(w, prev):
                writable.append(i)
            prev = w

        if len(en_words) > len(writable):
            en_words = en_words[: len(writable)]

        new_words = list(words)
        for k, idx in enumerate(writable):
            new_words[idx] = en_words[k] if k < len(en_words) else space_tok

        new_ln = f"{ridx}\t{render_words(new_words)}"
        if new_ln != ln:
            changed += 1
        out_lines.append(new_ln)

    path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return attempted, changed


def main() -> None:
    ap = argparse.ArgumentParser(description="Build EN script dump from direct EN mapping + manual overrides.")
    ap.add_argument("--src-dump", default="work/scriptdump_groups")
    ap.add_argument("--tbl", default="data/tables/lang5_jp.tbl")
    ap.add_argument("--full-records", default="data/translation/jp_en_full_records.json")
    ap.add_argument("--manual-overrides", default="data/translation/manual_record_overrides.json")
    ap.add_argument("--out-dump", default="work/scriptdump_en")
    ap.add_argument("--out-tbl", default="work/tables/lang5_en_insert.tbl")
    args = ap.parse_args()

    src = Path(args.src_dump)
    out = Path(args.out_dump)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src, out)

    tbl_src = Path(args.tbl)
    out_tbl = Path(args.out_tbl)
    patch_tbl_with_space(tbl_src, out_tbl)

    _, txt2tok = load_tbl_chars(out_tbl)
    supported = set(txt2tok.keys())

    rep = load_full_records(Path(args.full_records), skip_chunk0=True)
    rep.update(load_manual_overrides(Path(args.manual_overrides)))

    attempted_total = 0
    changed_total = 0
    for source_file, stem in (("SCEN.DAT", "SCEN"), ("SCEN2.DAT", "SCEN2")):
        root = out / stem
        if not root.exists():
            continue
        for fp in sorted(root.glob("chunk_*.txt")):
            m = re.match(r"chunk_(\d+)\.txt$", fp.name)
            if not m:
                continue
            cidx = int(m.group(1))
            a, c = patch_chunk_file(source_file, fp, cidx, rep, txt2tok, supported)
            attempted_total += a
            changed_total += c

    print(f"out_dump={out}")
    print(f"out_tbl={out_tbl}")
    print(f"mapping_entries={len(rep)}")
    print(f"attempted={attempted_total} changed={changed_total}")


if __name__ == "__main__":
    main()
