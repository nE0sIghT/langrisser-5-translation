#!/usr/bin/env python3
import argparse
import csv
import struct
from pathlib import Path


def load_tbl(path: Path) -> dict[int, str]:
    mp: dict[int, str] = {}
    if not path.exists():
        return mp
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = raw.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        try:
            mp[int(k, 16)] = v.strip()
        except Exception:
            continue
    return mp


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Dump Langrisser V runtime glyph cache rows from RAM dump.")
    p.add_argument(
        "--ram",
        action="append",
        default=[],
        help="Path to 2MB RAM dump. Repeatable. If omitted: work/scen_analysis/SLPS-01819_*_ram.bin",
    )
    p.add_argument("--tbl", default="work/tables/lang5_merged.tbl")
    p.add_argument("--out", default="work/scen_analysis/runtime_cache_dump.csv")
    return p.parse_args()


def u32_at(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def u16_at(buf: bytes, off: int) -> int:
    return struct.unpack_from("<H", buf, off)[0]


def pick_glyph_table_ptr(ram: bytes) -> int | None:
    # Observed candidate location around DB910..DB91C.
    for off in (0xDB910, 0xDB914, 0xDB918, 0xDB91C):
        v = u32_at(ram, off)
        if 0x80100000 <= v < 0x80120000:
            return v
    return None


def infer_entry_count(ram: bytes, glyph_ptr: int) -> int:
    g = glyph_ptr - 0x80000000
    end = g
    max_end = min(len(ram), g + 0x2000)  # hard cap
    while end + 64 <= max_end:
        if all(x == 0 for x in ram[end : end + 64]):
            break
        end += 4
    return max(0, (end - g) // 4)


def main() -> None:
    args = parse_args()
    tbl = load_tbl(Path(args.tbl))

    rams = [Path(p) for p in args.ram]
    if not rams:
        rams = sorted(Path("work/scen_analysis").glob("SLPS-01819_*_ram.bin"))
    if not rams:
        raise RuntimeError("No RAM dumps found.")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "ram_file",
                "ctx_ptr",
                "glyph_table_ptr",
                "slot",
                "cache_code_u16",
                "tbl_guess",
                "entry_b0",
                "entry_b1",
                "entry_b2",
                "entry_b3",
                "entry_hex",
            ]
        )
        for rp in rams:
            ram = rp.read_bytes()
            if len(ram) < 0x200000:
                continue
            ctx_ptr = u32_at(ram, 0xDB90C)
            glyph_ptr = pick_glyph_table_ptr(ram)
            if ctx_ptr < 0x80000000 or glyph_ptr is None:
                w.writerow([rp.name, f"0x{ctx_ptr:08X}", "", "", "", "", "", "", "", "", ""])
                continue

            ctx = ctx_ptr - 0x80000000
            g = glyph_ptr - 0x80000000
            entry_count = infer_entry_count(ram, glyph_ptr)
            # Observed u16 cache-code list start near +0x56 from ctx.
            # NOTE: these values are not yet proven to be direct script token ids.
            tok_base = ctx + 0x56

            for slot in range(entry_count):
                eoff = g + slot * 4
                toff = tok_base + slot * 2
                if eoff + 4 > len(ram) or toff + 2 > len(ram):
                    break
                code = u16_at(ram, toff)
                b0, b1, b2, b3 = ram[eoff], ram[eoff + 1], ram[eoff + 2], ram[eoff + 3]
                ch = tbl.get(code, "")
                w.writerow(
                    [
                        rp.name,
                        f"0x{ctx_ptr:08X}",
                        f"0x{glyph_ptr:08X}",
                        slot,
                        f"{code:04X}",
                        ch,
                        b0,
                        b1,
                        b2,
                        b3,
                        f"{b0:02X}{b1:02X}{b2:02X}{b3:02X}",
                    ]
                )

    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
