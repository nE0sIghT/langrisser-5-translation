#!/usr/bin/env python3
"""Validate SYSTEM.BIN text sequences with engine-specific layout constraints."""
import argparse
import json
import sys
from pathlib import Path

from lang5_project import ROOT, add_language_args, language_from_args
from lang5_scen import Codec, load_charmap_tbl


def load_object(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: expected a JSON object")
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    add_language_args(ap)
    ap.add_argument("--tbl", default=None)
    ap.add_argument("--strings", default=None)
    ap.add_argument("--system-source", default="work/systemdump/system_strings.json")
    ap.add_argument(
        "--constraints",
        default="data/common/system_ui_constraints.json",
    )
    args = ap.parse_args()

    lang = language_from_args(args)
    tbl = Path(args.tbl) if args.tbl else lang.tbl
    strings_path = Path(args.strings) if args.strings else lang.system_strings
    source_path = Path(args.system_source)
    constraints_path = Path(args.constraints)
    if not constraints_path.is_absolute():
        constraints_path = ROOT / constraints_path

    codec = Codec(load_charmap_tbl(tbl))
    overlay = load_object(strings_path)
    source_data = json.loads(source_path.read_text(encoding="utf-8"))
    source = {entry["id"]: entry["jp"] for entry in source_data}
    constraints = load_object(constraints_path)

    problems = 0
    for sequence in constraints.get("atlas_sequences", []):
        name = sequence["name"]
        columns = int(sequence["columns"])
        slot = int(sequence.get("start_slot", 0))
        for entry_id in sequence["ids"]:
            if entry_id not in source:
                print(f"{name}: unknown SYSTEM id {entry_id}")
                problems += 1
                continue
            text = overlay.get(entry_id, source[entry_id])
            if text == "{BLANK}":
                text = ""
            try:
                length = len(codec.encode(str(text).rstrip()))
            except ValueError as exc:
                print(f"{name}: {entry_id} is unencodable: {exc}")
                problems += 1
                continue
            column = slot % columns
            if length and column + length > columns:
                print(
                    f"{name}: {entry_id} {text!r} crosses the {columns}-cell "
                    f"atlas row: start={slot} column={column} length={length}"
                )
                problems += 1
            else:
                print(
                    f"{name}: {entry_id} {text!r} "
                    f"slots={slot}..{slot + length - 1} OK"
                )
            slot += length

    for field in constraints.get("fixed_width_fields", []):
        name = field["name"]
        max_cells = int(field["max_cells"])
        entry_ids = field.get("ids", [field.get("id")])
        for entry_id in entry_ids:
            if entry_id not in source:
                print(f"{name}: unknown SYSTEM id {entry_id}")
                problems += 1
                continue
            text = overlay.get(entry_id, source[entry_id])
            if text == "{BLANK}":
                text = ""
            try:
                length = len(codec.encode(str(text).rstrip()))
            except ValueError as exc:
                print(f"{name}: {entry_id} is unencodable: {exc}")
                problems += 1
                continue
            if length > max_cells:
                print(
                    f"{name}: {entry_id} {text!r} uses {length}>{max_cells} cells"
                )
                problems += 1
            else:
                print(
                    f"{name}: {entry_id} {text!r} "
                    f"uses {length}/{max_cells} cells OK"
                )

    if problems:
        print(f"{problems} SYSTEM UI layout problem(s)")
        sys.exit(1)
    print("SYSTEM UI layout OK")


if __name__ == "__main__":
    main()
