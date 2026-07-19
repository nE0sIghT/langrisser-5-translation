#!/usr/bin/env python3
"""Game manifest helpers.

The toolkit targets more than one game: Langrisser IV and V ship as one
two-disc PS1 release (and V also has a Saturn release). They share every
container format — the SCEN chunk/record model, the SYSTEM offset-table
groups, the IMG.DAT VRAM packets and the 12x12 1bpp glyph plane — but each
game has its own disc paths, its own glyph plane contents and its own
language packs.

A game manifest captures exactly those per-game facts, the same way
`lang5_platform` captures per-console ones. Platform stays orthogonal: a
game manifest lists the platforms it has been ported to, and platform
mapping data continues to live under `data/platforms/<code>/`.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lang5_project import ROOT

DEFAULT_GAME_ROOT = ROOT / "data" / "games"
DEFAULT_GAME = "l5"


def _path(base: Path, value: str | None) -> Path | None:
    if not value:
        return None
    p = Path(value)
    return p if p.is_absolute() else base / p


@dataclass(frozen=True)
class GamePack:
    code: str
    root: Path
    _data: dict[str, Any]

    @property
    def label(self) -> str:
        return str(self._data.get("label") or self.code)

    @property
    def disc_dir(self) -> str:
        """Directory holding the game's files on its own disc (`/L5`)."""
        return str(self._data.get("disc_dir") or f"/{self.code.upper()}")

    @property
    def exe(self) -> str:
        """Boot executable path on the disc (`/SLPS_018.19`)."""
        return str(self._data["exe"])

    @property
    def font_map(self) -> Path:
        """Slot->character map for this game's glyph plane.

        Each game generates its own plane, so the kanji bank differs; the
        shared low range (kana/ASCII) is identical and lives in the same CSV
        convention (`index_dec,index_hex,group,char,source`).
        """
        return _path(self.root, str(self._data["font_map"]))  # type: ignore[return-value]

    @property
    def text_table(self) -> Path | None:
        """Curated `HHHH=text` token table, when the game has one.

        Langrisser V ships one (`data/common/tables/lang5_jp.tbl`) with
        editorial fixes on top of the raw glyph map; a game without one reads
        its `font_map` instead.
        """
        return _path(self.root, self._data.get("text_table"))

    @property
    def system_scan_start(self) -> int:
        """File offset where the SYSTEM text groups begin."""
        return int(str(self._data.get("system_scan_start", "0x8052")), 0)

    @property
    def lang_root(self) -> Path:
        """Directory holding this game's language packs."""
        return _path(self.root, str(self._data["lang_root"]))  # type: ignore[return-value]

    @property
    def platforms(self) -> list[str]:
        return [str(p) for p in (self._data.get("platforms") or ["ps1"])]

    def iso_path(self, name: str) -> str:
        """Full on-disc path of a game file (`SCEN.DAT` -> `/L5/SCEN.DAT`)."""
        return f"{self.disc_dir.rstrip('/')}/{name}"


def load_game(game: str = DEFAULT_GAME,
              game_root: str | Path = DEFAULT_GAME_ROOT) -> GamePack:
    root = Path(game_root)
    if not root.is_absolute():
        root = ROOT / root
    pack_root = root / game
    manifest = pack_root / "manifest.json"
    if not manifest.exists():
        raise SystemExit(f"game manifest not found: {manifest}")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    code = str(data.get("game") or game)
    return GamePack(code=code, root=pack_root, _data=data)


def add_game_args(ap: argparse.ArgumentParser, default: str = DEFAULT_GAME) -> None:
    ap.add_argument("--game", default=default,
                    help="Game code from data/games/<code> (l5, l4).")
    ap.add_argument("--game-root", default="data/games",
                    help="Directory containing game manifests.")


def game_from_args(args: argparse.Namespace) -> GamePack:
    return load_game(getattr(args, "game", DEFAULT_GAME),
                     getattr(args, "game_root", DEFAULT_GAME_ROOT))
