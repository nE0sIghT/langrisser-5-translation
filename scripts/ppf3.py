#!/usr/bin/env python3
import argparse
from pathlib import Path


def write_ppf3(original: bytes, modified: bytes, out_path: Path, description: str) -> int:
    if len(original) != len(modified):
        raise ValueError("PPF3 requires images of the same size.")

    desc = description.encode("ascii", errors="replace")[:50].ljust(50, b"\x00")
    out = bytearray()
    out += b"PPF30"          # format id
    out += b"\x00"           # encoding method
    out += b"\x00"           # image type: BIN
    out += b"\x00"           # block check disabled
    out += b"\x00"           # undo data disabled
    out += desc

    i = 0
    records = 0
    n = len(original)
    while i < n:
        if original[i] == modified[i]:
            i += 1
            continue
        start = i
        while i < n and original[i] != modified[i] and (i - start) < 255:
            i += 1
        chunk = modified[start:i]
        out += start.to_bytes(8, "little")
        out += bytes([len(chunk)])
        out += chunk
        records += 1

    out_path.write_bytes(out)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a PPF3 patch from two BIN images.")
    parser.add_argument("original", help="Original BIN")
    parser.add_argument("modified", help="Modified BIN")
    parser.add_argument("output", help="Output PPF path")
    parser.add_argument(
        "--description",
        default="Langrisser V EN patch",
        help="ASCII description (max 50 chars)",
    )
    args = parser.parse_args()

    original = Path(args.original).read_bytes()
    modified = Path(args.modified).read_bytes()
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    records = write_ppf3(original, modified, out_path, args.description)
    print(f"wrote {out_path} ({records} records)")


if __name__ == "__main__":
    main()
