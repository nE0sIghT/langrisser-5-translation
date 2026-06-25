#!/usr/bin/env python3
"""Create a new target-language scaffold under data/lang/<code>.

The scaffold copies durable editorial assets from an existing language pack
(font slots, SYSTEM strings, name/glossary tables, graphics transcript text),
but does not copy SCEN chunks unless --copy-script is given. Generated JP dumps
belong in work/scriptdump/ and are never created here.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from lang5_project import DEFAULT_LANG_ROOT, load_language


SCALAR_FILES = [
    "font_assignments",
    "system_strings",
    "names",
    "glossary",
    "name_entry_grid",
    "manual_record_overrides",
    "poem",
    "poem_source",
    "virash_monologue",
]


def rel_to_root(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("lang", help="New language code, e.g. ru.")
    ap.add_argument("--label", default=None, help="Human-readable language label.")
    ap.add_argument("--from-lang", default="en", help="Source pack to copy scaffold data from.")
    ap.add_argument("--lang-root", default=str(DEFAULT_LANG_ROOT.relative_to(DEFAULT_LANG_ROOT.parent.parent)))
    ap.add_argument("--copy-script", action="store_true",
                    help="Also copy translated SCEN chunks from the source language.")
    ap.add_argument("--force", action="store_true", help="Overwrite an existing scaffold file.")
    args = ap.parse_args()

    lang_root = Path(args.lang_root)
    if not lang_root.is_absolute():
        lang_root = Path.cwd() / lang_root
    src = load_language(args.from_lang, lang_root)
    dst_root = lang_root / args.lang
    dst_root.mkdir(parents=True, exist_ok=True)
    (dst_root / "SCEN").mkdir(exist_ok=True)
    (dst_root / "SCEN" / ".gitkeep").touch()

    manifest = src.manifest_copy()
    manifest["lang"] = args.lang
    manifest["label"] = args.label or args.lang.upper()
    manifest["patch_suffix"] = args.lang
    manifest["patch_description"] = f"Langrisser V {args.lang.upper()} script+font"

    for key in SCALAR_FILES:
        value = manifest.get(key)
        if not value:
            continue
        src_path = (src.root / value).resolve()
        dst_path = dst_root / Path(value).name
        if dst_path.exists() and not args.force:
            print(f"skip existing {dst_path}")
            continue
        shutil.copyfile(src_path, dst_path)
        manifest[key] = dst_path.name
        print(f"copied {src_path} -> {dst_path}")

    manifest["script_dir"] = "SCEN"
    if args.copy_script:
        for fp in sorted(src.script_dir.glob("chunk_*.txt")):
            dst = dst_root / "SCEN" / fp.name
            if dst.exists() and not args.force:
                continue
            shutil.copyfile(fp, dst)
        print(f"copied script chunks from {src.script_dir}")

    out_manifest = dst_root / "manifest.json"
    if out_manifest.exists() and not args.force:
        raise SystemExit(f"{out_manifest} exists; use --force to overwrite")
    out_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out_manifest}")


if __name__ == "__main__":
    main()
