#!/usr/bin/env python3
import argparse
import struct
from pathlib import Path

from capstone import CS_ARCH_MIPS, CS_MODE_LITTLE_ENDIAN, CS_MODE_MIPS32, Cs


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Static runtime probe for SLPS_018.19 text/script engine anchors.")
    p.add_argument("--exe", default="work/extracted/SLPS_018.19")
    p.add_argument("--out", default="work/scen_analysis/slps_runtime_probe.txt")
    p.add_argument("--range-start", type=lambda x: int(x, 0), default=0x8001CF80)
    p.add_argument("--range-size", type=lambda x: int(x, 0), default=0x6C0)
    return p.parse_args()


def parse_psx_exe_header(blob: bytes) -> tuple[int, int, int]:
    if blob[:8] != b"PS-X EXE":
        raise RuntimeError("Not a PS-X EXE file.")
    pc = struct.unpack_from("<I", blob, 0x10)[0]
    t_addr = struct.unpack_from("<I", blob, 0x18)[0]
    t_size = struct.unpack_from("<I", blob, 0x1C)[0]
    return pc, t_addr, t_size


def disasm_range(text: bytes, t_addr: int, start: int, size: int) -> list[str]:
    off = start - t_addr
    if off < 0:
        return []
    chunk = text[off : off + size]
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 + CS_MODE_LITTLE_ENDIAN)
    out = []
    for ins in md.disasm(chunk, start):
        out.append(f"{ins.address:08X}: {ins.mnemonic:<8} {ins.op_str}")
    return out


def ram_addr(base_800e: int, neg_off: int) -> int:
    return (base_800e + neg_off) & 0xFFFFFFFF


def main() -> None:
    args = parse_args()
    blob = Path(args.exe).read_bytes()
    pc, t_addr, t_size = parse_psx_exe_header(blob)
    text = blob[0x800 : 0x800 + t_size]

    lines = []
    lines.append("Langrisser V SLPS runtime probe")
    lines.append("")
    lines.append(f"EXE: {args.exe}")
    lines.append(f"PC entry:   0x{pc:08X}")
    lines.append(f"Text addr:  0x{t_addr:08X}")
    lines.append(f"Text size:  0x{t_size:X}")
    lines.append("")
    lines.append("Confirmed script interpreter anchors (static):")
    lines.append("- 0x8001CFA0: read first word (lhu) and compare to 0xFFFF")
    lines.append("- 0x8001D174: loop end check against 0xFFFF")
    lines.append("- 0x8001D500: loop condition checks current word != 0xFFFF")
    lines.append("")
    lines.append("Likely runtime state RAM addresses (from lui 0x800e + negative offsets):")
    lines.append(f"- script_ptr_current @ 0x{ram_addr(0x800E0000, -0x45E4):08X}")
    lines.append(f"- script_base_table  @ 0x{ram_addr(0x800E0000, -0x46F4):08X}")
    lines.append(f"- interpreter_flag   @ 0x{ram_addr(0x800E0000, -0x472C):08X}")
    lines.append(f"- mode_state         @ 0x{ram_addr(0x800E0000, -0x4A46):08X}")
    lines.append("")
    lines.append(
        f"Disassembly range 0x{args.range_start:08X}..0x{args.range_start + args.range_size:08X}:"
    )
    lines.append("")
    lines.extend(disasm_range(text, t_addr, args.range_start, args.range_size))
    lines.append("")
    lines.append("DuckStation debugger breakpoint candidates:")
    lines.append("- exec bp 0x8001CFA0")
    lines.append("- exec bp 0x8001D354")
    lines.append("- exec bp 0x8001D500")
    lines.append("- watch/mem breakpoint on 0x800DBA1C (script_ptr_current)")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
