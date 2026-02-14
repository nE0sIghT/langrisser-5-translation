#!/usr/bin/env python3
import argparse
import re
import struct
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Probe SYSTEM.BIN for token-like 4-byte tables.")
    p.add_argument("--system", default="work/extracted/SYSTEM.BIN")
    p.add_argument("--tokenized", default="work/scen_analysis/source_script_tokenized.txt")
    p.add_argument("--base", type=lambda x: int(x, 0), default=0x178B0)
    p.add_argument("--entries", type=int, default=256)
    p.add_argument("--out", default="work/scen_analysis/system_table_probe.txt")
    return p.parse_args()


def load_script_tokens(path: Path) -> set[int]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {int(x, 16) for x in re.findall(r"\[([0-9A-F]{4})\]", text)}


def read_u16_table(blob: bytes, base: int, entries: int) -> list[tuple[int, int, int]]:
    out: list[tuple[int, int, int]] = []
    for i in range(entries):
        off = base + i * 4
        if off + 4 > len(blob):
            break
        w = struct.unpack_from("<H", blob, off)[0]
        b2 = blob[off + 2]
        b3 = blob[off + 3]
        out.append((w, b2, b3))
    return out


def main() -> None:
    args = parse_args()
    system = Path(args.system).read_bytes()
    script_tokens = load_script_tokens(Path(args.tokenized))
    table = read_u16_table(system, args.base, args.entries)

    values = [w for (w, _, _) in table]
    uniq = set(values)
    inter = sorted(uniq & script_tokens)
    c = Counter(values)

    lines: list[str] = []
    lines.append("Langrisser V SYSTEM.BIN table probe")
    lines.append("")
    lines.append(f"SYSTEM.BIN: {args.system}")
    lines.append(f"Tokenized source: {args.tokenized}")
    lines.append(f"Probe base: 0x{args.base:X}")
    lines.append(f"Entries read: {len(table)}")
    lines.append("")
    lines.append(f"Unique u16 values in table: {len(uniq)}")
    lines.append(f"0xFFFF count: {c.get(0xFFFF, 0)}")
    lines.append(f"Intersection with script token set: {len(inter)}")
    lines.append("")
    lines.append("Top repeated u16 values in table:")
    for v, n in c.most_common(24):
        lines.append(f"- 0x{v:04X}: {n}")
    lines.append("")
    lines.append("Intersecting values (u16) with script tokens:")
    lines.append(", ".join(f"0x{x:04X}" for x in inter))
    lines.append("")
    lines.append("First 64 entries (index: u16 b2 b3):")
    for i, (w, b2, b3) in enumerate(table[:64]):
        lines.append(f"{i:03d}: {w:04X} {b2:02X} {b3:02X}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
