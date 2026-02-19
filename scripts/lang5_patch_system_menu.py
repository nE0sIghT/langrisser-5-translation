#!/usr/bin/env python3
import argparse
import csv
import json
import struct
from pathlib import Path
from typing import Dict, List, Tuple


def load_token_map(groups_report: Path) -> Dict[int, str]:
    out: Dict[int, str] = {}
    with groups_report.open(encoding="utf-8", errors="ignore") as fh:
        r = csv.DictReader(fh)
        for row in r:
            ch = (row.get("char") or "").strip()
            if not ch:
                continue
            try:
                tok = int(row["index_dec"])
            except Exception:
                continue
            out[tok] = ch
    return out


def load_tbl_reverse(tbl_path: Path) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for raw in tbl_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = raw.rstrip("\n")
        if not s.strip() or s.lstrip().startswith("#") or "=" not in s:
            continue
        a, b = s.split("=", 1)
        try:
            tok = int(a.strip(), 16)
        except Exception:
            continue
        if b and b not in out:
            out[b] = tok
    return out


def words_from_bytes(blob: bytes) -> List[int]:
    return [struct.unpack_from("<H", blob, i)[0] for i in range(0, len(blob) & ~1, 2)]


def bytes_from_words(words: List[int]) -> bytes:
    out = bytearray()
    for w in words:
        out += struct.pack("<H", w & 0xFFFF)
    return bytes(out)


def decode_words(words: List[int], tok2ch: Dict[int, str]) -> str:
    out: List[str] = []
    for w in words:
        if w in tok2ch:
            out.append(tok2ch[w])
        elif w >= 0xFF00:
            out.append("{" + f"{w:04X}" + "}")
        else:
            out.append(f"[{w:04X}]")
    return "".join(out)


def split_ffff_runs(words: List[int], min_len: int = 2, max_len: int = 80) -> List[Tuple[int, int]]:
    runs: List[Tuple[int, int]] = []
    start = 0
    for i, w in enumerate(words):
        if w != 0xFFFF:
            continue
        n = i + 1 - start
        if min_len <= n <= max_len:
            runs.append((start, i + 1))
        start = i + 1
    return runs


def encode_ascii(text: str, txt2tok: Dict[str, int]) -> List[int]:
    out: List[int] = []
    for ch in text:
        tok = txt2tok.get(ch)
        if tok is not None:
            out.append(tok)
    return out


def _compact_word(w: str) -> str:
    if len(w) <= 3:
        return w
    out = [w[0]]
    for ch in w[1:]:
        if ch.upper() in "AEIOU":
            continue
        out.append(ch)
    return "".join(out)


def fit_ascii(en: str, max_len: int) -> str:
    s = (en or "").upper()
    s = s.replace("CONFIG", "CNFG")
    s = s.replace("MEMORY", "MEM")
    s = s.replace("CHECKING", "CHECK")
    s = s.replace("SCENARIO", "SCN")
    s = s.replace("CLASS", "CLS")
    s = s.replace("SKILL", "SKL")
    s = s.replace("CHANGE", "CHG")
    s = s.replace("AVAILABLE", "AVL")
    s = s.replace("RESUME", "CONT")
    s = s.replace("CANCEL", "BACK")
    s = " ".join(s.split())
    if len(s) <= max_len:
        return s
    parts = [_compact_word(p) for p in s.split()]
    s2 = " ".join(parts)
    if len(s2) <= max_len:
        return s2
    return s2[:max_len]


def patch_run_words(words: List[int], en: str, txt2tok: Dict[str, int]) -> List[int]:
    # Replace only printable slots (<E000) and keep controls verbatim.
    slots = [i for i, w in enumerate(words) if w < 0xE000]
    en_fit = fit_ascii(en, len(slots))
    en_words = encode_ascii(en_fit, txt2tok)
    if len(en_words) > len(slots):
        en_words = en_words[: len(slots)]
    space_tok = txt2tok.get(" ", 0x0000)
    out = list(words)
    for k, idx in enumerate(slots):
        out[idx] = en_words[k] if k < len(en_words) else space_tok
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Patch SYSTEM.BIN menu/UI text using decoded run dictionary.")
    ap.add_argument("--system-in", default="work/extracted/SYSTEM.BIN")
    ap.add_argument("--system-out", default="work/build/SYSTEM.BIN.en")
    ap.add_argument("--groups-report", default="data/font_mapping/groups_report.csv")
    ap.add_argument("--tbl", default="work/tables/lang5_en_insert.tbl")
    ap.add_argument("--menu-map", default="data/translation/system_menu_map.json")
    ap.add_argument("--report-csv", default="work/scen_analysis/system_menu_occurrences.csv")
    args = ap.parse_args()

    tok2ch = load_token_map(Path(args.groups_report))
    txt2tok = load_tbl_reverse(Path(args.tbl))
    menu_map: Dict[str, str] = json.loads(Path(args.menu_map).read_text(encoding="utf-8"))

    src = Path(args.system_in).read_bytes()
    words = words_from_bytes(src)
    runs = split_ffff_runs(words)

    patched = 0
    rows: List[dict] = []
    for a, b in runs:
        seg = words[a:b]
        dec = decode_words(seg, tok2ch)
        en = menu_map.get(dec)
        rows.append(
            {
                "offset_hex": f"0x{a*2:05X}",
                "word_count": str(len(seg)),
                "decoded_jp": dec,
                "mapped_en": en or "",
            }
        )
        if not en:
            continue
        words[a:b] = patch_run_words(seg, en, txt2tok)
        patched += 1

    out = Path(args.system_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(bytes_from_words(words))

    rep = Path(args.report_csv)
    rep.parent.mkdir(parents=True, exist_ok=True)
    with rep.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["offset_hex", "word_count", "decoded_jp", "mapped_en"])
        w.writeheader()
        w.writerows(rows)

    print(f"patched_runs={patched}")
    print(f"system_out={out}")
    print(f"report={rep}")


if __name__ == "__main__":
    main()
