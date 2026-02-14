#!/usr/bin/env python3
import argparse
import struct
from pathlib import Path


def read_chunk_pointers(data: bytes) -> list[int]:
    out: list[int] = []
    o = 0
    while o + 4 <= len(data):
        v = struct.unpack_from("<I", data, o)[0]
        out.append(v)
        o += 4
        if v == len(data):
            break
    return out


def dump_words(blob: bytes, off: int, count: int) -> list[int]:
    end = min(len(blob), off + count * 2)
    return [struct.unpack_from("<H", blob, i)[0] for i in range(off, end, 2)]


def main() -> None:
    p = argparse.ArgumentParser(description="Probe internal structure of a SCEN chunk using SLPS runtime field layout.")
    p.add_argument("--scen", default="work/extracted/SCEN.DAT")
    p.add_argument("--chunk-index", type=int, default=56)
    p.add_argument("--out", default="work/scen_analysis/chunk_struct_probe_56.txt")
    p.add_argument("--script-preview", type=int, default=64, help="number of u16 words to preview from script table head")
    args = p.parse_args()

    scen = Path(args.scen).read_bytes()
    pts = read_chunk_pointers(scen)
    if args.chunk_index < 0 or args.chunk_index + 1 >= len(pts):
        raise RuntimeError(f"chunk index {args.chunk_index} out of range")

    c_start = pts[args.chunk_index]
    c_end = pts[args.chunk_index + 1]
    chunk = scen[c_start:c_end]

    base0 = struct.unpack_from("<I", chunk, 0x00)[0]
    field_14 = struct.unpack_from("<I", chunk, 0x14)[0]
    field_2c = struct.unpack_from("<I", chunk, 0x2C)[0]
    sub_30 = struct.unpack_from("<I", chunk, base0 + 0x30)[0]
    sub_34 = struct.unpack_from("<I", chunk, base0 + 0x34)[0]
    sub_38 = struct.unpack_from("<I", chunk, base0 + 0x38)[0]
    sub_3c = struct.unpack_from("<I", chunk, base0 + 0x3C)[0]

    script_base = base0
    ptr_a1 = script_base + sub_3c
    ptr_v30 = script_base + sub_30
    ptr_v34 = script_base + sub_34
    ptr_v14 = field_14

    lines: list[str] = []
    lines.append("Langrisser V SCEN chunk structural probe")
    lines.append("")
    lines.append(f"SCEN: {args.scen}")
    lines.append(f"chunk_index: {args.chunk_index}")
    lines.append(f"chunk_file_range: 0x{c_start:X}..0x{c_end:X}")
    lines.append(f"chunk_size: 0x{len(chunk):X}")
    lines.append("")
    lines.append("Header fields (runtime-relevant):")
    lines.append(f"- word0/base0: 0x{base0:X}")
    lines.append(f"- field_14:    0x{field_14:X}")
    lines.append(f"- field_2c:    0x{field_2c:X}")
    lines.append("")
    lines.append("Subheader fields at base0:")
    lines.append(f"- +0x30: 0x{sub_30:X}")
    lines.append(f"- +0x34: 0x{sub_34:X}")
    lines.append(f"- +0x38: 0x{sub_38:X}")
    lines.append(f"- +0x3C: 0x{sub_3c:X}")
    lines.append("")
    lines.append("Derived pointers inside chunk:")
    lines.append(f"- script_base (a3): 0x{script_base:X}")
    lines.append(f"- ptr_a1:           0x{ptr_a1:X}")
    lines.append(f"- ptr_v30:          0x{ptr_v30:X}")
    lines.append(f"- ptr_v34:          0x{ptr_v34:X}")
    lines.append(f"- ptr_v14:          0x{ptr_v14:X}")
    lines.append("")

    lines.append(f"u16 preview at script_base (first {args.script_preview} words):")
    sb_words = dump_words(chunk, script_base, args.script_preview)
    lines.append(" ".join(f"{w:04X}" for w in sb_words))
    lines.append("")

    lines.append(f"u16 preview at ptr_a1 (first {args.script_preview} words):")
    a1_words = dump_words(chunk, ptr_a1, args.script_preview)
    lines.append(" ".join(f"{w:04X}" for w in a1_words))
    lines.append("")

    lines.append(f"u16 preview at ptr_v30 (first {args.script_preview} words):")
    v30_words = dump_words(chunk, ptr_v30, args.script_preview)
    lines.append(" ".join(f"{w:04X}" for w in v30_words))
    lines.append("")

    lines.append(f"u16 preview at ptr_v34 (first {args.script_preview} words):")
    v34_words = dump_words(chunk, ptr_v34, args.script_preview)
    lines.append(" ".join(f"{w:04X}" for w in v34_words))
    lines.append("")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
