#!/usr/bin/env python3
"""Generate side-by-side JP/target review pages for translated chunks.

One HTML page per chunk: record index, JP source line, target translation.
Control tags are shown dimmed so the dialogue reads naturally.
"""
import argparse
import html
import re
from pathlib import Path

from lang5_project import add_language_args, language_from_args

TAG_RE = re.compile(r"<\$[0-9A-Fa-f]{4}>")

CSS = """
body{font-family:sans-serif;background:#1e1e1e;color:#ddd;margin:20px}
table{border-collapse:collapse;width:100%}
td,th{border:1px solid #444;padding:6px 10px;vertical-align:top}
td.idx{color:#888;text-align:right;width:3em}
td.jp{width:47%;font-size:15px}
td.target{width:47%;font-size:15px;color:#cfc}
.tag{color:#666;font-size:11px}
h1{font-size:20px}
"""


def pretty(text: str) -> str:
    out = []
    pos = 0
    for m in TAG_RE.finditer(text):
        if m.start() > pos:
            out.append(html.escape(text[pos : m.start()]))
        out.append(f"<span class='tag'>{html.escape(m.group(0))}</span>")
        pos = m.end()
    if pos < len(text):
        out.append(html.escape(text[pos:]))
    return "".join(out)


def read_records(path: Path) -> dict[int, str]:
    out: dict[int, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        if "\t" in raw and not raw.startswith("#"):
            idx, text = raw.split("\t", 1)
            out[int(idx)] = text
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_language_args(ap)
    ap.add_argument("--jp-dump", default="work/scriptdump")
    ap.add_argument("--translation-root", default=None,
                    help="Override the language pack's translated-text root.")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--stem", default="SCEN")
    args = ap.parse_args()

    lang = language_from_args(args)
    translation_root = (Path(args.translation_root)
                        if args.translation_root else lang.dump_root)
    out_dir = Path(args.out_dir) if args.out_dir else lang.review_root
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = []
    for target_fp in sorted(Path(translation_root, args.stem).glob("chunk_*.txt")):
        jp = read_records(Path(args.jp_dump, args.stem, target_fp.name))
        target = read_records(target_fp)
        rows = []
        for idx in sorted(jp):
            rows.append(
                f"<tr><td class='idx'>{idx}</td>"
                f"<td class='jp'>{pretty(jp[idx])}</td>"
                f"<td class='target'>{pretty(target.get(idx, ''))}</td></tr>"
            )
        name = target_fp.stem
        page = out_dir / f"{name}.html"
        page.write_text(
            f"<!doctype html><meta charset='utf-8'><title>{name}</title>"
            f"<style>{CSS}</style><h1>{args.stem} / {name}</h1>"
            f"<table><tr><th>#</th><th>JP</th><th>{html.escape(lang.label)}</th></tr>"
            f"{''.join(rows)}</table>",
            encoding="utf-8",
        )
        pages.append(name)
        print(f"wrote {page}")
    index = out_dir / "index.html"
    links = "".join(f"<li><a href='{p}.html'>{p}</a></li>" for p in pages)
    index.write_text(
        f"<!doctype html><meta charset='utf-8'><title>review</title>"
        f"<style>{CSS}</style><h1>Translated chunks</h1><ul>{links}</ul>",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
