#!/usr/bin/env python3
"""Read-only Sega Saturn BIN/CUE helpers for Langrisser V.

The PS1 tooling in this repository assumes one MODE2/2352 data track with
2048-byte user sectors at raw offset 24. The Saturn release is a mixed-mode
disc: track 1 is MODE1/2352 ISO9660, track 2 is a separate MODE2 XA/ADPCM area,
and later tracks are CD audio. This module intentionally exposes only read-only
operations.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterator


SECTOR_RAW_SIZE = 2352
MODE1_USER_OFFSET = 16
MODE1_USER_SIZE = 2048
XA_SUBHEADER_OFFSET = 16
XA_SUBHEADER_SIZE = 8


@dataclass(frozen=True)
class Track:
    number: int
    mode: str
    index_lba: int
    pregap_frames: int = 0

    @property
    def raw_offset(self) -> int:
        return self.index_lba * SECTOR_RAW_SIZE


@dataclass(frozen=True)
class CueSheet:
    cue_path: Path
    bin_path: Path
    tracks: tuple[Track, ...]

    def track(self, number: int) -> Track:
        for track in self.tracks:
            if track.number == number:
                return track
        raise KeyError(f"track {number:02d} not found")


@dataclass(frozen=True)
class IsoEntry:
    name: str
    extent_lba: int
    size: int
    is_dir: bool
    parent: str

    @property
    def path(self) -> str:
        return f"/{self.name}" if self.parent == "/" else f"{self.parent}/{self.name}"


def mmssff_to_lba(mmssff: str) -> int:
    minute, second, frame = [int(part) for part in mmssff.split(":")]
    return minute * 60 * 75 + second * 75 + frame


def parse_cue(cue_path: Path) -> CueSheet:
    cue_path = cue_path.resolve()
    bin_path: Path | None = None
    tracks: list[Track] = []
    current_number: int | None = None
    current_mode: str | None = None
    current_pregap = 0

    for raw in cue_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r'FILE\s+"([^"]+)"\s+BINARY', line, flags=re.IGNORECASE)
        if m:
            bin_path = (cue_path.parent / m.group(1)).resolve()
            continue
        m = re.match(r"TRACK\s+(\d+)\s+(\S+)", line, flags=re.IGNORECASE)
        if m:
            current_number = int(m.group(1))
            current_mode = m.group(2).upper()
            current_pregap = 0
            continue
        m = re.match(r"PREGAP\s+(\d\d:\d\d:\d\d)", line, flags=re.IGNORECASE)
        if m:
            current_pregap = mmssff_to_lba(m.group(1))
            continue
        m = re.match(r"INDEX\s+01\s+(\d\d:\d\d:\d\d)", line, flags=re.IGNORECASE)
        if m and current_number is not None and current_mode is not None:
            tracks.append(
                Track(
                    number=current_number,
                    mode=current_mode,
                    index_lba=mmssff_to_lba(m.group(1)),
                    pregap_frames=current_pregap,
                )
            )
            continue

    if bin_path is None:
        raise ValueError(f"no BINARY FILE entry in {cue_path}")
    if not tracks:
        raise ValueError(f"no tracks in {cue_path}")
    return CueSheet(cue_path=cue_path, bin_path=bin_path, tracks=tuple(tracks))


def read_raw_sector(fh, lba: int) -> bytes:
    fh.seek(lba * SECTOR_RAW_SIZE)
    data = fh.read(SECTOR_RAW_SIZE)
    if len(data) != SECTOR_RAW_SIZE:
        raise ValueError(f"incomplete raw sector at LBA {lba}")
    return data


def read_mode1_user_sector(fh, absolute_lba: int) -> bytes:
    raw = read_raw_sector(fh, absolute_lba)
    return raw[MODE1_USER_OFFSET : MODE1_USER_OFFSET + MODE1_USER_SIZE]


def read_mode1_user_bytes(fh, track1: Track, start_lba: int, size: int) -> bytes:
    out = bytearray()
    pos = 0
    while pos < size:
        sector = read_mode1_user_sector(fh, track1.index_lba + start_lba + pos // MODE1_USER_SIZE)
        offset = pos % MODE1_USER_SIZE
        take = min(size - pos, MODE1_USER_SIZE - offset)
        out += sector[offset : offset + take]
        pos += take
    return bytes(out)


def parse_dir_records(blob: bytes) -> Iterator[tuple[int, int, bool, str]]:
    i = 0
    while i < len(blob):
        rec_len = blob[i]
        if rec_len == 0:
            i = ((i // MODE1_USER_SIZE) + 1) * MODE1_USER_SIZE
            continue
        rec = blob[i : i + rec_len]
        if len(rec) < 34:
            break
        extent_lba = struct.unpack_from("<I", rec, 2)[0]
        size = struct.unpack_from("<I", rec, 10)[0]
        flags = rec[25]
        name_len = rec[32]
        ident = rec[33 : 33 + name_len]
        is_dir = bool(flags & 0x02)
        name = ident.decode("latin-1", errors="replace")
        if name == "\x00":
            name = "."
        elif name == "\x01":
            name = ".."
        else:
            name = name.split(";", 1)[0]
        yield extent_lba, size, is_dir, name
        i += rec_len


def read_pvd(fh, track1: Track) -> bytes:
    pvd = read_mode1_user_sector(fh, track1.index_lba + 16)
    if pvd[0] != 1 or pvd[1:6] != b"CD001":
        raise ValueError("primary volume descriptor not found on track 1 LBA 16")
    return pvd


def walk_iso(cue: CueSheet) -> list[IsoEntry]:
    track1 = cue.track(1)
    entries: list[IsoEntry] = []
    with cue.bin_path.open("rb") as fh:
        pvd = read_pvd(fh, track1)
        root_rec = pvd[156:190]
        root_lba = struct.unpack_from("<I", root_rec, 2)[0]
        root_size = struct.unpack_from("<I", root_rec, 10)[0]

        stack = [("/", root_lba, root_size)]
        seen: set[tuple[str, int, int]] = set()
        while stack:
            parent, lba, size = stack.pop()
            key = (parent, lba, size)
            if key in seen:
                continue
            seen.add(key)
            raw = read_mode1_user_bytes(fh, track1, lba, size)
            for extent, ent_size, is_dir, name in parse_dir_records(raw):
                if name in (".", ".."):
                    continue
                ent = IsoEntry(name=name, extent_lba=extent, size=ent_size, is_dir=is_dir, parent=parent)
                entries.append(ent)
                if is_dir:
                    stack.append((ent.path, extent, ent_size))
    return sorted(entries, key=lambda entry: entry.path.lower())


def extract_iso_file(cue: CueSheet, path: str, out_path: Path) -> None:
    wanted = "/" + path.strip("/")
    entry = next((ent for ent in walk_iso(cue) if ent.path.upper() == wanted.upper()), None)
    if entry is None or entry.is_dir:
        raise FileNotFoundError(path)
    track1 = cue.track(1)
    with cue.bin_path.open("rb") as fh:
        payload = read_mode1_user_bytes(fh, track1, entry.extent_lba, entry.size)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(payload)


def _xa_entries(cue: CueSheet) -> list[IsoEntry]:
    return [
        ent for ent in walk_iso(cue)
        if not ent.is_dir and ent.path.upper().startswith("/ADPCM/") and ent.path.upper().endswith(".XA")
    ]


def xa_logical_to_physical_lba(cue: CueSheet, logical_lba: int) -> int:
    return logical_lba - cue.track(2).pregap_frames


def xa_sector_spans(cue: CueSheet) -> list[tuple[IsoEntry, int, int]]:
    entries = sorted(_xa_entries(cue), key=lambda ent: ent.extent_lba)
    out: list[tuple[IsoEntry, int, int]] = []
    with cue.bin_path.open("rb") as fh:
        for i, ent in enumerate(entries):
            physical = xa_logical_to_physical_lba(cue, ent.extent_lba)
            if i + 1 < len(entries):
                sectors = entries[i + 1].extent_lba - ent.extent_lba
            else:
                sectors = 0
                while True:
                    raw = read_raw_sector(fh, physical + sectors)
                    sub = raw[XA_SUBHEADER_OFFSET : XA_SUBHEADER_OFFSET + XA_SUBHEADER_SIZE]
                    sectors += 1
                    if sub[2] & 0x80:
                        break
            out.append((ent, physical, sectors))
    return out


def xa_info(cue: CueSheet) -> dict:
    spans = xa_sector_spans(cue)
    subheaders: dict[str, int] = {}
    eof_count = 0
    with cue.bin_path.open("rb") as fh:
        for _ent, physical, sectors in spans:
            for sector in range(sectors):
                raw = read_raw_sector(fh, physical + sector)
                sub = raw[XA_SUBHEADER_OFFSET : XA_SUBHEADER_OFFSET + XA_SUBHEADER_SIZE]
                key = sub.hex().upper()
                subheaders[key] = subheaders.get(key, 0) + 1
                if sub[2] & 0x80:
                    eof_count += 1
    return {
        "files": len(spans),
        "directories": len({Path(ent.path).parent.as_posix() for ent, _physical, _sectors in spans}),
        "first": {
            "path": spans[0][0].path,
            "logical_lba": spans[0][0].extent_lba,
            "physical_lba": spans[0][1],
            "sectors": spans[0][2],
            "size": spans[0][0].size,
        } if spans else None,
        "last": {
            "path": spans[-1][0].path,
            "logical_lba": spans[-1][0].extent_lba,
            "physical_lba": spans[-1][1],
            "sectors": spans[-1][2],
            "size": spans[-1][0].size,
        } if spans else None,
        "physical_range": [
            min((physical for _ent, physical, _sectors in spans), default=0),
            max((physical + sectors for _ent, physical, sectors in spans), default=0),
        ],
        "referenced_sectors": sum(sectors for _ent, _physical, sectors in spans),
        "eof_sectors": eof_count,
        "subheaders": dict(sorted(subheaders.items())),
    }


def extract_xa_raw(cue: CueSheet, path: str, out_path: Path) -> None:
    wanted = "/" + path.strip("/")
    spans = xa_sector_spans(cue)
    match = next((span for span in spans if span[0].path.upper() == wanted.upper()), None)
    if match is None:
        raise FileNotFoundError(path)
    _ent, physical, sectors = match
    out = bytearray()
    with cue.bin_path.open("rb") as fh:
        for sector in range(sectors):
            out += read_raw_sector(fh, physical + sector)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(out))


def cmd_info(args: argparse.Namespace) -> None:
    cue = parse_cue(Path(args.cue))
    print(json.dumps({
        "cue": str(cue.cue_path),
        "bin": str(cue.bin_path),
        "bin_size": cue.bin_path.stat().st_size,
        "tracks": [asdict(track) | {"raw_offset": track.raw_offset} for track in cue.tracks],
    }, indent=2))


def cmd_list(args: argparse.Namespace) -> None:
    cue = parse_cue(Path(args.cue))
    entries = walk_iso(cue)
    if args.json:
        print(json.dumps([asdict(ent) | {"path": ent.path} for ent in entries], indent=2))
        return
    for ent in entries:
        kind = "dir " if ent.is_dir else "file"
        print(f"{kind} {ent.extent_lba:6d} {ent.size:9d} {ent.path}")


def cmd_extract(args: argparse.Namespace) -> None:
    cue = parse_cue(Path(args.cue))
    extract_iso_file(cue, args.path, Path(args.out))


def cmd_xainfo(args: argparse.Namespace) -> None:
    cue = parse_cue(Path(args.cue))
    print(json.dumps(xa_info(cue), indent=2))


def cmd_extract_xa(args: argparse.Namespace) -> None:
    cue = parse_cue(Path(args.cue))
    extract_xa_raw(cue, args.path, Path(args.out))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cue", default="iso/saturn/LANGRISSER_5.cue")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("info")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("list")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("extract")
    p.add_argument("path")
    p.add_argument("out")
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("xainfo")
    p.set_defaults(func=cmd_xainfo)

    p = sub.add_parser("extract-xa-raw")
    p.add_argument("path")
    p.add_argument("out")
    p.set_defaults(func=cmd_extract_xa)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
