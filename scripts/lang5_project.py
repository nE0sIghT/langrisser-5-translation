#!/usr/bin/env python3
"""Project path helpers for target-language builds.

The toolkit keeps generated source dumps under work/ and durable translation
assets under data/lang/<code>/. This module is the single place that resolves
language manifests and derived output paths.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LANG_ROOT = ROOT / "data" / "lang"
COMMON_ROOT = ROOT / "data" / "common"
COMMON_FONT_MAP = COMMON_ROOT / "font_mapping" / "groups_report.csv"
COMMON_FONT_FIXES = COMMON_ROOT / "font_mapping" / "proposed_fixes.csv"
COMMON_SCENARIO_MAP = COMMON_ROOT / "scenario_map.json"
COMMON_JP_TBL = COMMON_ROOT / "tables" / "lang5_jp.tbl"


def _path(base: Path, value: str | None) -> Path | None:
    if not value:
        return None
    p = Path(value)
    return p if p.is_absolute() else base / p


@dataclass(frozen=True)
class LanguagePack:
    code: str
    root: Path
    _data: dict[str, Any]

    @property
    def label(self) -> str:
        return str(self._data.get("label") or self.code)

    @property
    def suffix(self) -> str:
        return str(self._data.get("patch_suffix") or self.code)

    @property
    def patch_description(self) -> str:
        return str(self._data.get("patch_description") or f"Langrisser V {self.suffix.upper()} script+font")

    @property
    def script_dir(self) -> Path:
        return _path(self.root, str(self._data.get("script_dir") or "SCEN"))  # type: ignore[return-value]

    @property
    def dump_root(self) -> Path:
        return self.script_dir.parent

    @property
    def script_stem(self) -> str:
        return self.script_dir.name

    @property
    def font_assignments(self) -> Path:
        return _path(self.root, str(self._data.get("font_assignments") or "font_slot_assignments.csv"))  # type: ignore[return-value]

    @property
    def system_strings(self) -> Path:
        return _path(self.root, str(self._data.get("system_strings") or "system_strings.json"))  # type: ignore[return-value]

    @property
    def system_layout(self) -> Path:
        return _path(self.root, str(self._data.get("system_layout") or "system_layout.json"))  # type: ignore[return-value]

    @property
    def system_complete(self) -> bool:
        value = self._data.get("system_complete", False)
        if not isinstance(value, bool):
            raise SystemExit(
                f"{self.root / 'manifest.json'}: system_complete must be boolean"
            )
        return value

    @property
    def title_credits(self) -> Path:
        return _path(self.root, str(self._data.get("title_credits") or "title_credits.json"))  # type: ignore[return-value]

    @property
    def names(self) -> Path:
        return _path(self.root, str(self._data.get("names") or "names.csv"))  # type: ignore[return-value]

    @property
    def glossary(self) -> Path:
        return _path(self.root, str(self._data.get("glossary") or "glossary.csv"))  # type: ignore[return-value]

    @property
    def name_entry_grid(self) -> Path:
        return _path(self.root, str(self._data.get("name_entry_grid") or "name_entry_grid.json"))  # type: ignore[return-value]

    @property
    def manual_record_overrides(self) -> Path:
        return _path(self.root, str(self._data.get("manual_record_overrides") or "manual_record_overrides.json"))  # type: ignore[return-value]

    @property
    def review_status(self) -> Path:
        return _path(self.root, str(self._data.get("review_status") or "review_status.csv"))  # type: ignore[return-value]

    @property
    def poem(self) -> Path:
        return _path(self.root, str(self._data.get("poem") or "poem_prologue.txt"))  # type: ignore[return-value]

    @property
    def poem_source(self) -> Path:
        return _path(self.root, str(self._data.get("poem_source") or "poem_prologue_jp.txt"))  # type: ignore[return-value]

    @property
    def virash_monologue(self) -> Path:
        return _path(self.root, str(self._data.get("virash_monologue") or "virash_monologue.json"))  # type: ignore[return-value]

    @property
    def font(self) -> Path | None:
        return _path(self.root, self._data.get("font"))

    @property
    def font_size(self) -> int:
        return int(self._data.get("font_size") or 10)

    @property
    def single_chars(self) -> str:
        return str(self._data.get("single_chars") or "")

    @property
    def forced_pairs(self) -> list[str]:
        pairs = self._data.get("forced_pairs") or []
        if not isinstance(pairs, list) or any(not isinstance(p, str) or len(p) != 2 for p in pairs):
            raise SystemExit(f"{self.root / 'manifest.json'}: forced_pairs must contain two-character strings")
        return list(pairs)

    @property
    def window_width(self) -> int:
        return int(self._data.get("window_width") or 21)

    @property
    def choice_width(self) -> int:
        return int(self._data.get("choice_width") or 21)

    @property
    def max_lines(self) -> int:
        return int(self._data.get("max_lines") or 4)

    def manifest_copy(self) -> dict[str, Any]:
        return dict(self._data)

    @property
    def tbl(self) -> Path:
        return ROOT / "work" / "tables" / f"lang5_{self.suffix}.tbl"

    def build_path(self, name: str) -> Path:
        return ROOT / "work" / "build" / name.format(lang=self.suffix)

    @property
    def work_bin(self) -> Path:
        return self.build_path("langrisser_v_{lang}.bin")

    @property
    def out_ppf(self) -> Path:
        return ROOT / "patches" / f"langrisser_v_{self.suffix}.ppf"

    @property
    def wip_root(self) -> Path:
        return ROOT / "work" / f"wip_{self.suffix}"

    @property
    def review_root(self) -> Path:
        return ROOT / "work" / "review" / self.suffix


def load_language(lang: str = "en", lang_root: str | Path = DEFAULT_LANG_ROOT) -> LanguagePack:
    root = Path(lang_root)
    if not root.is_absolute():
        root = ROOT / root
    pack_root = root / lang
    manifest = pack_root / "manifest.json"
    if not manifest.exists():
        raise SystemExit(f"language manifest not found: {manifest}")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    code = str(data.get("lang") or lang)
    return LanguagePack(code=code, root=pack_root, _data=data)


def add_language_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--lang", default="en", help="Target language code from data/lang/<code>.")
    ap.add_argument("--lang-root", default="data/lang", help="Directory containing language packs.")


def language_from_args(args: argparse.Namespace) -> LanguagePack:
    return load_language(args.lang, args.lang_root)
