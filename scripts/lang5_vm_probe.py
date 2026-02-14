#!/usr/bin/env python3
import argparse
import csv
import json
import struct
from pathlib import Path
from typing import Dict, List, Tuple


def load_map(path: Path) -> Dict[int, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[int, str] = {}
    for k, v in raw.items():
        try:
            t = int(k, 16)
        except Exception:
            continue
        if isinstance(v, str) and v:
            out[t] = v[0]
    return out


def decode_words(words: List[int], mp: Dict[int, str]) -> str:
    out: List[str] = []
    for w in words:
        if w in mp:
            out.append(mp[w])
        elif 0xFF00 <= w <= 0xFFFF:
            out.append("{" + f"{w:04X}" + "}")
        else:
            out.append("[" + f"{w:04X}" + "]")
    return "".join(out)


def read_u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def read_u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def parse_u32_offsets(data: bytes, base: int, max_items: int = 256) -> List[int]:
    vals: List[int] = []
    prev = -1
    for i in range(max_items):
        off = base + i * 4
        if off + 4 > len(data):
            break
        v = read_u32(data, off)
        if v == 0 or v >= 0x100000:
            break
        if prev != -1 and v < prev:
            break
        vals.append(v)
        prev = v
    return vals


def main() -> None:
    ap = argparse.ArgumentParser(description="Probe Langrisser V runtime VM records from RAM dump.")
    ap.add_argument("--ram", default="work/ram.bin")
    ap.add_argument("--base", type=lambda x: int(x, 0), default=0x16A194)
    ap.add_argument("--cur", type=lambda x: int(x, 0), default=0x16A1DA)
    ap.add_argument("--token-map", default="scripts/lang5_token_map_manual.json")
    ap.add_argument("--out-csv", default="work/scen_analysis/vm_probe_records.csv")
    args = ap.parse_args()

    ram = Path(args.ram).read_bytes()
    mp = load_map(Path(args.token_map))

    offs = parse_u32_offsets(ram, args.base, max_items=256)
    rows: List[dict] = []
    for idx, rel in enumerate(offs):
        addr = args.base + rel
        if addr + 8 > len(ram):
            continue
        head = ram[addr : addr + 16]
        h0 = read_u16(ram, addr + 0)
        h1 = read_u16(ram, addr + 2)
        op = ram[addr + 2]
        # Heuristic small stream after [u16 + u8 + ...]
        body = ram[addr + 3 : addr + 3 + 32]
        body_words = [struct.unpack_from("<H", body, i)[0] for i in range(0, len(body) & ~1, 2)]
        contains_cur = "yes" if (args.cur >= addr and args.cur < addr + 64) else ""
        rows.append(
            {
                "entry_index": idx,
                "rel_off": f"0x{rel:04X}",
                "abs_addr": f"0x{addr:06X}",
                "contains_cur": contains_cur,
                "head_u16_0": f"{h0:04X}",
                "head_u16_1": f"{h1:04X}",
                "op_u8": f"{op:02X}",
                "head_hex": head.hex(),
                "body_words_hex": " ".join(f"{w:04X}" for w in body_words),
                "body_decode": decode_words(body_words, mp),
            }
        )

    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "entry_index",
                "rel_off",
                "abs_addr",
                "contains_cur",
                "head_u16_0",
                "head_u16_1",
                "op_u8",
                "head_hex",
                "body_words_hex",
                "body_decode",
            ],
        )
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
