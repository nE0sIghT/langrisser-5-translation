#!/usr/bin/env python3
import argparse
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Tuple


SECTOR_RAW_SIZE = 2352
SECTOR_USER_OFFSET = 24
SECTOR_USER_SIZE = 2048


@dataclass
class IsoEntry:
    name: str
    extent_lba: int
    size: int
    is_dir: bool
    parent: str

    @property
    def path(self) -> str:
        if self.parent == "/":
            return f"/{self.name}"
        return f"{self.parent}/{self.name}"


def mmssff_to_lba(mmssff: str) -> int:
    m, s, f = [int(x) for x in mmssff.split(":")]
    return (m * 60 * 75) + (s * 75) + f


def read_user_sector(fh, lba: int) -> bytes:
    fh.seek((lba * SECTOR_RAW_SIZE) + SECTOR_USER_OFFSET)
    data = fh.read(SECTOR_USER_SIZE)
    if len(data) != SECTOR_USER_SIZE:
        raise ValueError(f"incomplete sector at LBA {lba}")
    return data


def read_user_bytes(fh, start_lba: int, size: int) -> bytes:
    out = bytearray()
    pos = 0
    while pos < size:
        sector = read_user_sector(fh, start_lba + (pos // SECTOR_USER_SIZE))
        offset = pos % SECTOR_USER_SIZE
        take = min(size - pos, SECTOR_USER_SIZE - offset)
        out += sector[offset : offset + take]
        pos += take
    return bytes(out)


def write_user_bytes(fh, start_lba: int, payload: bytes) -> None:
    pos = 0
    total = len(payload)
    while pos < total:
        sector_index = start_lba + (pos // SECTOR_USER_SIZE)
        offset = pos % SECTOR_USER_SIZE
        take = min(total - pos, SECTOR_USER_SIZE - offset)
        fh.seek((sector_index * SECTOR_RAW_SIZE) + SECTOR_USER_OFFSET + offset)
        fh.write(payload[pos : pos + take])
        pos += take


def parse_dir_records(blob: bytes) -> Iterator[Tuple[int, int, bool, str]]:
    i = 0
    while i < len(blob):
        rec_len = blob[i]
        if rec_len == 0:
            i = ((i // SECTOR_USER_SIZE) + 1) * SECTOR_USER_SIZE
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
            if ";" in name:
                name = name.split(";", 1)[0]
        yield extent_lba, size, is_dir, name
        i += rec_len


def read_pvd(fh) -> bytes:
    pvd = read_user_sector(fh, 16)
    if pvd[1:6] != b"CD001" or pvd[0] != 1:
        raise ValueError("primary volume descriptor not found at sector 16")
    return pvd


def walk_iso(fh) -> List[IsoEntry]:
    pvd = read_pvd(fh)
    root_rec = pvd[156:190]
    root_lba = struct.unpack_from("<I", root_rec, 2)[0]
    root_size = struct.unpack_from("<I", root_rec, 10)[0]

    entries: List[IsoEntry] = []
    stack = [("/", root_lba, root_size)]
    seen = set()

    while stack:
        parent, lba, size = stack.pop()
        key = (parent, lba, size)
        if key in seen:
            continue
        seen.add(key)
        raw = read_user_bytes(fh, lba, size)
        for extent, ent_size, is_dir, name in parse_dir_records(raw):
            if name in (".", ".."):
                continue
            ent = IsoEntry(name=name, extent_lba=extent, size=ent_size, is_dir=is_dir, parent=parent)
            entries.append(ent)
            if is_dir:
                stack.append((ent.path, extent, ent_size))
    entries.sort(key=lambda e: e.path.lower())
    return entries


def extract_file(fh, path: str, out_path: str) -> None:
    wanted = path.strip("/")
    with open(fh.name, "rb") as handle:
        entries = walk_iso(handle)
        for ent in entries:
            if ent.is_dir:
                continue
            if ent.path.strip("/") == wanted:
                data = read_user_bytes(handle, ent.extent_lba, ent.size)
                Path(out_path).parent.mkdir(parents=True, exist_ok=True)
                Path(out_path).write_bytes(data)
                return
    raise FileNotFoundError(f"ISO file not found: {path}")


def inject_file(fh, path: str, in_path: str) -> None:
    wanted = path.strip("/")
    payload = Path(in_path).read_bytes()
    entries = walk_iso(fh)
    for ent in entries:
        if ent.is_dir:
            continue
        if ent.path.strip("/") == wanted:
            if len(payload) > ent.size:
                raise ValueError(
                    f"payload too large for {path}: {len(payload)} > {ent.size}. "
                    "In-place injection must not grow file size."
                )
            if len(payload) < ent.size:
                payload = payload + (b"\x00" * (ent.size - len(payload)))
            write_user_bytes(fh, ent.extent_lba, payload)
            return
    raise FileNotFoundError(f"ISO file not found: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Read PS1 MODE2/2352 ISO9660 filesystem.")
    parser.add_argument("bin_path", help="Path to MODE2/2352 BIN")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List files in ISO filesystem")
    p_list.add_argument("--dirs", action="store_true", help="Include directories in output")

    p_extract = sub.add_parser("extract", help="Extract a file from ISO")
    p_extract.add_argument("iso_path", help="Path in ISO (e.g. /SCUS_123.45)")
    p_extract.add_argument("output", help="Output path")

    p_inject = sub.add_parser("inject", help="Inject file into ISO in-place")
    p_inject.add_argument("iso_path", help="Path in ISO (e.g. /SCUS_123.45)")
    p_inject.add_argument("input", help="Input file to inject")

    args = parser.parse_args()
    mode = "rb+" if args.cmd == "inject" else "rb"
    with open(args.bin_path, mode) as fh:
        if args.cmd == "list":
            for ent in walk_iso(fh):
                if ent.is_dir and not args.dirs:
                    continue
                kind = "d" if ent.is_dir else "f"
                print(f"{kind} {ent.extent_lba:7d} {ent.size:9d} {ent.path}")
        elif args.cmd == "extract":
            extract_file(fh, args.iso_path, args.output)
            print(f"extracted {args.iso_path} -> {args.output}")
        elif args.cmd == "inject":
            inject_file(fh, args.iso_path, args.input)
            print(f"injected {args.input} -> {args.iso_path}")


if __name__ == "__main__":
    main()
