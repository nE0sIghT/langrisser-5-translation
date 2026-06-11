#!/usr/bin/env python3
"""Pre-fill EN chunk files from translation memory before manual work.

Sources, in priority order:
1. exact-match translation memory built from all already-translated chunks
   (same JP record text -> same EN record text);
2. name-plate records (text + <$FFFF>) resolved via names_base.csv and
   glossary_names.csv.

Untranslated records keep their JP text and their indices are printed, so
the output goes to a staging directory (work/wip_en by default): files in
data/translation/en must be fully translated or the build fails on kanji
whose font slots were sacrificed for EN letter pairs. Move a chunk file to
data/translation/en only once it passes lang5_validate_en.
"""
import argparse
import csv
import re
from pathlib import Path

TAG_RE = re.compile(r"<\$[0-9A-Fa-f]{4}>")


def read_records(path: Path) -> dict[int, str]:
    out: dict[int, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if "\t" in raw and not raw.startswith("#"):
            idx, text = raw.split("\t", 1)
            out[int(idx)] = text
    return out


def jp_like(text: str) -> bool:
    return bool(re.search(r"[぀-ヺ一-鿿]", TAG_RE.sub("", text).replace("・", "")))


def build_tm(jp_dump: Path, en_dump: Path, stem: str) -> dict[str, str]:
    tm: dict[str, str] = {}
    for en_fp in sorted((en_dump / stem).glob("chunk_*.txt")):
        jp_fp = jp_dump / stem / en_fp.name
        if not jp_fp.exists():
            continue
        jp = read_records(jp_fp)
        en = read_records(en_fp)
        for idx, jp_text in jp.items():
            en_text = en.get(idx)
            if en_text and en_text != jp_text and not jp_like(en_text):
                tm.setdefault(jp_text, en_text)
    return tm


def load_names() -> dict[str, str]:
    names: dict[str, str] = {}
    for fp, jp_col, en_col in (
        (Path("data/translation/names_base.csv"), "jp", "en"),
        (Path("data/translation/glossary_names.csv"), "jp", "proposal"),
    ):
        if not fp.exists():
            continue
        for row in csv.DictReader(open(fp, encoding="utf-8")):
            jp = row[jp_col].split("/")[0].strip()
            en = row[en_col].strip()
            if jp and en and en != "?":
                names.setdefault(jp, en)
    return names


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("chunks", nargs="+", type=int)
    ap.add_argument("--jp-dump", default="work/scriptdump")
    ap.add_argument("--en-dump", default="data/translation/en")
    ap.add_argument("--out-dir", default="work/wip_en")
    ap.add_argument("--stem", default="SCEN")
    args = ap.parse_args()

    jp_dump, en_dump = Path(args.jp_dump), Path(args.en_dump)
    tm = build_tm(jp_dump, en_dump, args.stem)
    names = load_names()

    for cidx in args.chunks:
        jp_fp = jp_dump / args.stem / f"chunk_{cidx:03d}.txt"
        jp = read_records(jp_fp)
        header = [l for l in jp_fp.read_text(encoding="utf-8").splitlines()
                  if l.startswith("#")]
        out_lines = list(header)
        todo: list[int] = []
        filled = 0
        for idx in sorted(jp):
            text = jp[idx]
            if text in tm:
                text = tm[text]
                filled += 1
            elif text.endswith("<$FFFF>") and "<$" not in text[:-7]:
                base = text[:-7]
                if base in names:
                    text = names[base] + "<$FFFF>"
                    filled += 1
                elif jp_like(text):
                    todo.append(idx)
            elif jp_like(text):
                todo.append(idx)
            out_lines.append(f"{idx}\t{text}")
        out_fp = Path(args.out_dir) / args.stem / jp_fp.name
        out_fp.parent.mkdir(parents=True, exist_ok=True)
        out_fp.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        print(f"chunk {cidx:03d}: records={len(jp)} prefilled={filled} todo={len(todo)}")
        print(f"  todo indices: {todo}")


if __name__ == "__main__":
    main()
