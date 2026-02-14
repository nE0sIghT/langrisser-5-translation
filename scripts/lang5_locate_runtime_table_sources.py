#!/usr/bin/env python3
import argparse
from pathlib import Path


def best_match(hay: bytes, needle: bytes):
    n = len(needle)
    best_off = -1
    best_eq = -1
    for off in range(0, len(hay) - n + 1):
        seg = hay[off : off + n]
        eq = sum(1 for a, b in zip(seg, needle) if a == b)
        if eq > best_eq:
            best_eq = eq
            best_off = off
    return best_off, best_eq


def diff_positions(a: bytes, b: bytes, max_items: int = 16):
    out = []
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            out.append((i, x, y))
            if len(out) >= max_items:
                break
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Locate runtime table blocks inside extracted game files (exact/best match)."
    )
    ap.add_argument("--extracted-dir", default="work/extracted")
    ap.add_argument(
        "--blocks",
        nargs="+",
        default=[
            "work/scen_analysis/tbl_80108910_raw.bin",
            "work/scen_analysis/tbl_80108B02_raw.bin",
            "work/scen_analysis/tbl_80108C68_raw.bin",
        ],
    )
    ap.add_argument(
        "--max-best-file-size",
        type=int,
        default=8 * 1024 * 1024,
        help="Only files <= this size are considered for expensive best-match scan.",
    )
    args = ap.parse_args()

    files = [p for p in Path(args.extracted_dir).glob("*") if p.is_file()]
    if not files:
        raise SystemExit(f"no files in {args.extracted_dir}")

    for bpath in args.blocks:
        bp = Path(bpath)
        if not bp.exists():
            print(f"{bp}: missing")
            continue
        block = bp.read_bytes()
        print(f"\n[{bp}] len=0x{len(block):X}")
        exact_hits = []
        for f in files:
            raw = f.read_bytes()
            pos = raw.find(block)
            if pos != -1:
                exact_hits.append((f.name, pos))
        if exact_hits:
            for name, pos in exact_hits:
                print(f"  exact: {name} @ 0x{pos:X}")
            continue

        best = None
        for f in files:
            raw = f.read_bytes()
            if len(raw) > args.max_best_file_size:
                continue
            if len(raw) < len(block):
                continue
            off, eq = best_match(raw, block)
            if best is None or eq > best[2]:
                best = (f, off, eq)
        if best is None:
            print("  no candidate")
            continue
        f, off, eq = best
        seg = f.read_bytes()[off : off + len(block)]
        diffs = diff_positions(seg, block)
        ratio = eq / len(block)
        print(f"  best: {f.name} @ 0x{off:X} eq={eq}/{len(block)} ({ratio:.6f})")
        for i, x, y in diffs:
            print(f"    diff +0x{i:X}: file=0x{x:02X} block=0x{y:02X}")


if __name__ == "__main__":
    main()
