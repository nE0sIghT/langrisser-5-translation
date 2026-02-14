#!/usr/bin/env python3
import argparse
import lzma
import struct
import zlib
from pathlib import Path

try:
    import zstandard as zstd
except Exception:  # pragma: no cover
    zstd = None


SAVE_STATE_MAGIC = 0x43435544  # "DUCC"

# SAVE_STATE_HEADER from DuckStation, packed(4)
HEADER_FMT = "<II128s32s" + "IIIIIIIIIIII"
HEADER_SIZE = struct.calcsize(HEADER_FMT)

RAM_2MB = 0x200000
MEMCTRL_PREFIX = struct.pack("<II", 0x1F000000, 0x1F802000)
MEMCTRL_EXPECT = (
    0x0013243F,
    0x00003022,
    0x0013243F,
    0x200931E1,
    0x00020843,
    0x00070777,
    0x00031125,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extract DuckStation .sav state_data + RAM for Langrisser V.")
    p.add_argument(
        "--state",
        action="append",
        default=[],
        help="Path to .sav (can be repeated). If omitted, scans work/sstates/SLPS-01819_*.sav",
    )
    p.add_argument("--out-dir", default="work/scen_analysis")
    return p.parse_args()


def read_header(data: bytes) -> dict:
    if len(data) < HEADER_SIZE:
        raise RuntimeError("File too small for save-state header.")
    (
        magic,
        version,
        title_raw,
        serial_raw,
        media_path_length,
        offset_to_media_path,
        media_subimage_index,
        screenshot_compression_type,
        screenshot_width,
        screenshot_height,
        screenshot_compressed_size,
        offset_to_screenshot,
        data_compression_type,
        data_compressed_size,
        data_uncompressed_size,
        offset_to_data,
    ) = struct.unpack_from(HEADER_FMT, data, 0)
    if magic != SAVE_STATE_MAGIC:
        raise RuntimeError(f"Bad magic: 0x{magic:08X} (expected DUCC).")
    return {
        "version": version,
        "serial": serial_raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore"),
        "data_compression_type": data_compression_type,
        "data_compressed_size": data_compressed_size,
        "data_uncompressed_size": data_uncompressed_size,
        "offset_to_data": offset_to_data,
    }


def decompress_block(comp: bytes, comp_type: int, expected_size: int) -> bytes:
    # DuckStation: 0=None 1=Deflate 2=Zstandard 3=XZ
    if comp_type == 0:
        out = comp
    elif comp_type == 1:
        out = zlib.decompress(comp)
    elif comp_type == 2:
        if zstd is None:
            raise RuntimeError("zstandard module is required for zstd-compressed states.")
        out = zstd.ZstdDecompressor().decompress(comp)
    elif comp_type == 3:
        out = lzma.decompress(comp)
    else:
        raise RuntimeError(f"Unknown compression type: {comp_type}")
    if len(out) != expected_size:
        raise RuntimeError(f"Decompressed size mismatch: got {len(out)}, expected {expected_size}")
    return out


def score_memctrl(block: bytes, memctrl_off: int) -> int:
    score = 0
    if block[memctrl_off : memctrl_off + 8] == MEMCTRL_PREFIX:
        score += 2
    for i, exp in enumerate(MEMCTRL_EXPECT):
        off = memctrl_off + 8 + i * 4
        if off + 4 > len(block):
            break
        got = struct.unpack_from("<I", block, off)[0]
        if got == exp:
            score += 1
    return score


def find_ram_start(state_data: bytes) -> int:
    best = (-1, -1)  # (score, ram_start)
    pos = 0
    while True:
        idx = state_data.find(MEMCTRL_PREFIX, pos)
        if idx < 0:
            break
        ram_start = idx - RAM_2MB
        if 0 <= ram_start and (ram_start + RAM_2MB) <= len(state_data):
            sc = score_memctrl(state_data, idx)
            if sc > best[0]:
                best = (sc, ram_start)
        pos = idx + 1
    if best[0] < 6:
        raise RuntimeError("Could not locate RAM block with sufficient confidence.")
    return best[1]


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    states = [Path(s) for s in args.state]
    if not states:
        states = sorted(Path("work/sstates").glob("SLPS-01819_*.sav"))
    if not states:
        raise RuntimeError("No state files found.")

    for st in states:
        raw = st.read_bytes()
        hdr = read_header(raw)
        off = hdr["offset_to_data"]
        csz = hdr["data_compressed_size"]
        comp = raw[off : off + csz]
        state_data = decompress_block(comp, hdr["data_compression_type"], hdr["data_uncompressed_size"])
        ram_start = find_ram_start(state_data)
        ram = state_data[ram_start : ram_start + RAM_2MB]

        base = st.stem
        data_out = out_dir / f"{base}_state_data.bin"
        ram_out = out_dir / f"{base}_ram.bin"
        data_out.write_bytes(state_data)
        ram_out.write_bytes(ram)

        print(
            f"{st}: version={hdr['version']} serial={hdr['serial']!r} "
            f"comp={hdr['data_compression_type']} state_data={len(state_data)} "
            f"ram_start=0x{ram_start:X} -> {ram_out}"
        )


if __name__ == "__main__":
    main()
