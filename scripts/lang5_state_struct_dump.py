#!/usr/bin/env python3
import argparse
import struct
from pathlib import Path


BASE = 0x80000000


def read_u16(mem: bytes, addr: int) -> int:
    return struct.unpack_from("<H", mem, addr - BASE)[0]


def read_u32(mem: bytes, addr: int) -> int:
    return struct.unpack_from("<I", mem, addr - BASE)[0]


def read_bytes(mem: bytes, addr: int, size: int) -> bytes:
    return mem[addr - BASE : addr - BASE + size]


def dump_words(mem: bytes, addr: int, count: int) -> str:
    return " ".join(f"{read_u16(mem, addr + i * 2):04X}" for i in range(count))


def main() -> None:
    ap = argparse.ArgumentParser(description="Dump key Langrisser V runtime text structs from RAM dump.")
    ap.add_argument("--ram", default="work/scen_analysis/SLPS-01819_6_ram.bin")
    ap.add_argument("--out", default="work/scen_analysis/state_struct_dump.txt")
    args = ap.parse_args()

    mem = Path(args.ram).read_bytes()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    keys = [
        ("script_base", 0x800DB90C),
        ("script_cur", 0x800DBA1C),
        ("tbl_b34c", 0x800DB34C),
        ("tbl_b508", 0x800DB508),
        ("tbl_b4ec", 0x800DB4EC),
        ("tbl_b538", 0x800DB538),
        ("grid_meta", 0x800DB380),
    ]
    vals = {k: read_u32(mem, a) for k, a in keys}

    lines = []
    lines.append(f"ram={args.ram}")
    for k, a in keys:
        lines.append(f"{k:12s} @ {a:08X} -> {vals[k]:08X}")

    sb = vals["script_base"]
    sc = vals["script_cur"]
    lines.append("")
    lines.append(f"script_off={((sc - sb) & 0xFFFFFFFF):08X}")
    lines.append(f"script_cur_words: {dump_words(mem, sc, 24)}")

    # Dump first visible non-FFFF rels around script_cur.
    rels = [read_u16(mem, sc + i * 2) for i in range(48)]
    useful = [(i, r) for i, r in enumerate(rels) if r != 0xFFFF]
    lines.append("non_ffff_rels(head): " + ", ".join(f"{i}:{r:04X}" for i, r in useful[:12]))
    for i, rel in useful[:8]:
        ep = (sb + rel) & 0xFFFFFFFF
        w = [read_u16(mem, ep + j * 2) for j in range(10)]
        lines.append(
            f"entry[{i:02d}] rel={rel:04X} ep={ep:08X} head={w[0]:04X} "
            f"op={w[1] & 0xFF:02X} arg={w[2]:04X} words={' '.join(f'{x:04X}' for x in w)}"
        )

    # Compare 0x80108910 and derivative buffers.
    b34 = vals["tbl_b34c"]
    b508 = vals["tbl_b508"]
    b4ec = vals["tbl_b4ec"]
    b538 = vals["tbl_b538"]
    blk_b34 = read_bytes(mem, b34, 0x600)
    blk_508 = read_bytes(mem, b508, 0x600)
    blk_4ec = read_bytes(mem, b4ec, 0x600)
    blk_538 = read_bytes(mem, b538, 0x600)
    lines.append("")
    lines.append(
        f"nonzero bytes: b34c={sum(1 for x in blk_b34 if x)} "
        f"b508={sum(1 for x in blk_508 if x)} b4ec={sum(1 for x in blk_4ec if x)} "
        f"b538={sum(1 for x in blk_538 if x)}"
    )
    lines.append(f"b34c[0:48]: {' '.join(f'{x:02X}' for x in blk_b34[:48])}")
    lines.append(f"b508_words[0:24]: {' '.join(f'{read_u16(mem, b508 + i*2):04X}' for i in range(24))}")
    lines.append(f"b4ec[0:48]: {' '.join(f'{x:02X}' for x in blk_4ec[:48])}")
    lines.append(f"b538[0:48]: {' '.join(f'{x:02X}' for x in blk_538[:48])}")

    # Heuristic: b508 often mirrors b34 stream with +1 byte offset in active states.
    stream = blk_b34
    matched = 0
    checked = 0
    for i in range(0, min(0x300, len(blk_508) // 2)):
        w = struct.unpack_from("<H", blk_508, i * 2)[0]
        b_off = i * 2 + 1
        if b_off + 1 < len(stream):
            ww = stream[b_off] | (stream[b_off + 1] << 8)
            checked += 1
            if w == ww:
                matched += 1
    lines.append(f"b508_vs_b34_shift1_word_matches={matched}/{checked}")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
