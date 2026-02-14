#!/usr/bin/env python3
import argparse
import csv
import os
import struct
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

from lang5_gdb_remote import GDBRemote, parse_regs_g


def load_token_map(path: Path) -> Dict[int, str]:
    import json

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


def wait_port(host: str, port: int, timeout: float) -> bool:
    import socket

    end = time.time() + timeout
    while time.time() < end:
        try:
            s = socket.create_connection((host, port), timeout=0.5)
            s.close()
            return True
        except Exception:
            time.sleep(0.1)
    return False


def parse_offsets_dword(block: bytes, max_size: int) -> List[int]:
    vals: List[int] = []
    prev = -1
    for i in range(0, len(block) - 3, 4):
        v = struct.unpack_from("<I", block, i)[0]
        if v >= max_size:
            break
        if prev != -1 and v <= prev:
            break
        vals.append(v)
        prev = v
    return vals


def read_mem_chunked(cli: GDBRemote, addr: int, size: int, chunk: int = 0x800) -> bytes:
    out = bytearray()
    off = 0
    while off < size:
        take = min(chunk, size - off)
        data = bytes.fromhex(cli.request(f"m{addr + off:08x},{take:x}", deadline_s=3.0))
        if len(data) != take:
            raise RuntimeError(f"short read at 0x{addr+off:08X}: got {len(data)} expected {take}")
        out.extend(data)
        off += take
    return bytes(out)


def chunk_words(data: bytes) -> List[int]:
    n = len(data) & ~1
    return [struct.unpack_from("<H", data, i)[0] for i in range(0, n, 2)]


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract runtime script segments from DuckStation savestates.")
    ap.add_argument("--state-glob", default="work/sstates/*.sav")
    ap.add_argument("--iso", default="iso/SLPS-01818-9-B.cue")
    ap.add_argument("--duck-bin", default="external/squashfs-root/usr/bin/duckstation-qt")
    ap.add_argument("--token-map", default="scripts/lang5_token_map_manual.json")
    ap.add_argument("--out-csv", default="work/scen_analysis/runtime_state_segments.csv")
    ap.add_argument("--dump-size", type=lambda x: int(x, 0), default=0x10000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9012)
    ap.add_argument("--display", default=":126")
    ap.add_argument("--max-stops", type=int, default=1, help="How many breakpoint hits to capture per state.")
    args = ap.parse_args()

    states = sorted(Path().glob(args.state_glob))
    if not states:
        raise SystemExit(f"no states matched: {args.state_glob}")

    mp = load_token_map(Path(args.token_map))
    out_rows: List[dict] = []
    win_rows: List[dict] = []

    appdir = str(Path(args.duck_bin).resolve().parents[1])
    env = os.environ.copy()
    env.update(
        {
            "APPDIR": appdir,
            "LD_LIBRARY_PATH": f"{appdir}/lib",
            "QT_PLUGIN_PATH": f"{appdir}/plugins",
            "QML2_IMPORT_PATH": f"{appdir}/qml",
            "QT_QPA_PLATFORM": "xcb",
            "XDG_CONFIG_HOME": "/workspace/work/duck_cfg",
            "XDG_DATA_HOME": "/workspace/work/duck_data",
            "HOME": "/workspace/work/duck_home",
            "DISPLAY": args.display,
        }
    )

    for st in states:
        xvfb = subprocess.Popen(
            ["Xvfb", args.display, "-screen", "0", "1024x768x24"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.8)
        duck = subprocess.Popen(
            [args.duck_bin, "-nogui", "-batch", "-statefile", str(st), args.iso],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            if not wait_port(args.host, args.port, 6.0):
                print(f"[warn] gdb server not up for {st.name}")
                continue

            cli = GDBRemote(args.host, args.port, timeout=1.0)
            try:
                cli.request("?")
                cli.request("Z0,8001d198,4")
                for stop_idx in range(1, args.max_stops + 1):
                    cli.continue_run()
                    stop = cli.recv_until_packet(8.0)

                    regs = parse_regs_g(cli.request("g", deadline_s=2.0))
                    pc = regs.get("pc", 0)

                    db90c = bytes.fromhex(cli.request("m800db90c,80", deadline_s=2.0))
                    dba1c = bytes.fromhex(cli.request("m800dba1c,80", deadline_s=2.0))
                    db90c_dw = [struct.unpack_from("<I", db90c, i)[0] for i in range(0, 0x20, 4)]
                    dba1c_dw = [struct.unpack_from("<I", dba1c, i)[0] for i in range(0, 0x20, 4)]
                    base = db90c_dw[0]
                    cur = dba1c_dw[0]

                    block = read_mem_chunked(cli, base, args.dump_size, chunk=0x800)
                    offsets = parse_offsets_dword(block, len(block))
                    cur_off = cur - base if base <= cur < (base + len(block)) else -1

                    for ridx, (a, b) in enumerate(zip(offsets, offsets[1:]), start=1):
                        if b <= a or b > len(block):
                            continue
                        rec = block[a:b]
                        words = chunk_words(rec)
                        out_rows.append(
                            {
                                "state_file": st.name,
                                "stop_reason": stop,
                                "pc": f"{pc:08X}",
                                "base_ptr": f"{base:08X}",
                                "cur_ptr": f"{cur:08X}",
                                "cur_off": "" if cur_off < 0 else f"0x{cur_off:04X}",
                                "record_index": ridx,
                                "offset": f"0x{a:04X}",
                                "size": len(rec),
                                "contains_current_ptr": "yes" if (cur_off >= a and cur_off < b) else "",
                                "decoded_manual": decode_words(words, mp),
                                "words_hex": " ".join(f"{w:04X}" for w in words),
                                "stop_index": stop_idx,
                            }
                        )

                    # Also capture a raw token window around the live script pointer.
                    if cur >= 0x200:
                        waddr = cur - 0x200
                        wsize = 0x600
                        wblock = read_mem_chunked(cli, waddr, wsize, chunk=0x400)
                        wwords = chunk_words(wblock)
                        seg_start = 0
                        seg_idx = 0
                        for i, w in enumerate(wwords):
                            if w == 0xFFFF:
                                seg = wwords[seg_start : i + 1]
                                byte_a = seg_start * 2
                                byte_b = (i + 1) * 2
                                cur_rel = 0x200
                                seg_idx += 1
                                win_rows.append(
                                    {
                                        "state_file": st.name,
                                        "pc": f"{pc:08X}",
                                        "cur_ptr": f"{cur:08X}",
                                        "win_addr": f"{waddr:08X}",
                                        "segment_index": seg_idx,
                                        "start_rel": f"0x{byte_a:04X}",
                                        "end_rel": f"0x{byte_b:04X}",
                                        "contains_current_ptr": "yes" if (cur_rel >= byte_a and cur_rel < byte_b) else "",
                                        "decoded_manual": decode_words(seg, mp),
                                        "words_hex": " ".join(f"{x:04X}" for x in seg),
                                        "stop_index": stop_idx,
                                    }
                                )
                                seg_start = i + 1
            finally:
                try:
                    cli.interrupt()
                except Exception:
                    pass
                cli.close()
        finally:
            duck.terminate()
            xvfb.terminate()
            time.sleep(0.2)

    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "state_file",
                "stop_reason",
                "pc",
                "base_ptr",
                "cur_ptr",
                "cur_off",
                "record_index",
                "offset",
                "size",
                "contains_current_ptr",
                "decoded_manual",
                "words_hex",
                "stop_index",
            ],
        )
        w.writeheader()
        w.writerows(out_rows)

    print(f"wrote {out} ({len(out_rows)} rows)")

    win_out = out.with_name(out.stem + "_windows.csv")
    with win_out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "state_file",
                "pc",
                "cur_ptr",
                "win_addr",
                "segment_index",
                "start_rel",
                "end_rel",
                "contains_current_ptr",
                "decoded_manual",
                "words_hex",
                "stop_index",
            ],
        )
        w.writeheader()
        w.writerows(win_rows)

    print(f"wrote {win_out} ({len(win_rows)} rows)")


if __name__ == "__main__":
    main()
