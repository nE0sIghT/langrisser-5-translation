#!/usr/bin/env python3
import argparse
import csv
import json
import os
import struct
import subprocess
import time
from pathlib import Path
from typing import Dict, List

from lang5_gdb_remote import GDBRemote, parse_regs_g


def load_token_map(path: Path) -> Dict[int, str]:
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


def req_data(cli: GDBRemote, payload: str, deadline_s: float = 3.0) -> str:
    r = cli.request(payload, deadline_s=deadline_s)
    while r.startswith("S") or r == "OK":
        r = cli.recv_until_packet(deadline_s)
    return r


def read_mem_chunked(cli: GDBRemote, addr: int, size: int, chunk: int = 0x800) -> bytes:
    out = bytearray()
    off = 0
    while off < size:
        take = min(chunk, size - off)
        data = bytes.fromhex(req_data(cli, f"m{addr + off:08x},{take:x}", deadline_s=3.0))
        if len(data) != take:
            raise RuntimeError(f"short read at 0x{addr+off:08X}: got {len(data)} expected {take}")
        out.extend(data)
        off += take
    return bytes(out)


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


def chunk_words(data: bytes) -> List[int]:
    n = len(data) & ~1
    return [struct.unpack_from("<H", data, i)[0] for i in range(0, n, 2)]


def run_input_script(seq: List[str], env: dict) -> None:
    cmd = ["python3", "scripts/lang5_duck_x11_input.py", "--activate"]
    for s in seq:
        cmd.extend(["--seq", s])
    subprocess.run(cmd, env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> None:
    ap = argparse.ArgumentParser(description="Autoplay from state5 and extract live script records at interpreter stops.")
    ap.add_argument("--state", default="work/sstates/SLPS-01819_5.sav")
    ap.add_argument("--iso", default="iso/SLPS-01818-9-B.cue")
    ap.add_argument("--duck-bin", default="external/squashfs-root/usr/bin/duckstation-qt")
    ap.add_argument("--display", default=":171")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9012)
    ap.add_argument("--dump-size", type=lambda x: int(x, 0), default=0x18000)
    ap.add_argument("--max-stops", type=int, default=24)
    ap.add_argument("--token-map", default="scripts/lang5_token_map_manual.json")
    ap.add_argument("--out-csv", default="work/scen_analysis/state5_autoplay_extract.csv")
    args = ap.parse_args()

    mp = load_token_map(Path(args.token_map))

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

    rows: List[dict] = []
    xvfb = subprocess.Popen(["Xvfb", args.display, "-screen", "0", "1024x768x24"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    openbox = subprocess.Popen(["openbox"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    duck = subprocess.Popen([args.duck_bin, "-statefile", args.state, args.iso], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        # Start game from New, then fast-forward early dialog.
        time.sleep(2.5)
        run_input_script(["Return:12:0.09"], env)
        time.sleep(8.0)
        run_input_script(["k:64:0.08"], env)

        if not wait_port(args.host, args.port, 8.0):
            raise RuntimeError("duck gdb server not reachable")
        cli = GDBRemote(args.host, args.port, timeout=1.0)
        try:
            cli.request("?")
            for bp in (0x8001D198, 0x8001D19C, 0x8001D1FC, 0x8001D208, 0x8001D280, 0x8001D29C):
                cli.request(f"Z0,{bp:08x},4")

            for stop_idx in range(1, args.max_stops + 1):
                cli.continue_run()
                stop = cli.recv_until_packet(12.0)

                regs = parse_regs_g(req_data(cli, "g", deadline_s=2.0))
                pc = regs.get("pc", 0)

                db90c = bytes.fromhex(req_data(cli, "m800db90c,80", deadline_s=2.0))
                dba1c = bytes.fromhex(req_data(cli, "m800dba1c,80", deadline_s=2.0))
                db90c_dw = [struct.unpack_from("<I", db90c, i)[0] for i in range(0, 0x20, 4)]
                dba1c_dw = [struct.unpack_from("<I", dba1c, i)[0] for i in range(0, 0x20, 4)]
                base = db90c_dw[0]
                cur = dba1c_dw[0]

                block = read_mem_chunked(cli, base, args.dump_size)
                offsets = parse_offsets_dword(block, len(block))
                cur_off = cur - base if base <= cur < (base + len(block)) else -1

                found = False
                for ridx, (a, b) in enumerate(zip(offsets, offsets[1:]), start=1):
                    if b <= a or b > len(block):
                        continue
                    if not (cur_off >= a and cur_off < b):
                        continue
                    rec = block[a:b]
                    words = chunk_words(rec)
                    rows.append(
                        {
                            "stop_index": stop_idx,
                            "stop_reason": stop,
                            "pc": f"{pc:08X}",
                            "base_ptr": f"{base:08X}",
                            "cur_ptr": f"{cur:08X}",
                            "record_index": ridx,
                            "record_off": f"0x{a:04X}",
                            "record_size": len(rec),
                            "decoded_manual": decode_words(words, mp),
                            "words_hex": " ".join(f"{w:04X}" for w in words),
                        }
                    )
                    found = True
                    break
                if not found:
                    rows.append(
                        {
                            "stop_index": stop_idx,
                            "stop_reason": stop,
                            "pc": f"{pc:08X}",
                            "base_ptr": f"{base:08X}",
                            "cur_ptr": f"{cur:08X}",
                            "record_index": "",
                            "record_off": "",
                            "record_size": "",
                            "decoded_manual": "",
                            "words_hex": "",
                        }
                    )
        finally:
            try:
                cli.interrupt()
            except Exception:
                pass
            cli.close()
    finally:
        duck.terminate()
        openbox.terminate()
        xvfb.terminate()

    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "stop_index",
                "stop_reason",
                "pc",
                "base_ptr",
                "cur_ptr",
                "record_index",
                "record_off",
                "record_size",
                "decoded_manual",
                "words_hex",
            ],
        )
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
