#!/usr/bin/env python3
import argparse
import csv
import os
import struct
import subprocess
import time
from pathlib import Path
from typing import Dict, List

from lang5_gdb_remote import GDBRemote, parse_regs_g


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


def req_data(cli: GDBRemote, payload: str, timeout: float = 2.0) -> str:
    r = cli.request(payload, deadline_s=timeout)
    while r.startswith("S") or r == "OK":
        r = cli.recv_until_packet(timeout)
    return r


def req_ack(cli: GDBRemote, payload: str, timeout: float = 2.0) -> str:
    return cli.request(payload, deadline_s=timeout)


def read_u32(cli: GDBRemote, addr: int) -> int:
    b = bytes.fromhex(req_data(cli, f"m{addr:08x},4"))
    return struct.unpack_from("<I", b, 0)[0]


def read_words(cli: GDBRemote, addr: int, count: int) -> List[int]:
    b = bytes.fromhex(req_data(cli, f"m{addr:08x},{count*2:x}"))
    return [struct.unpack_from("<H", b, i * 2)[0] for i in range(count)]


def main() -> None:
    ap = argparse.ArgumentParser(description="Trace writes into text grid buffer from savestate.")
    ap.add_argument("--state", default="work/sstates/SLPS-01819_6.sav")
    ap.add_argument("--iso", default="iso/SLPS-01818-9-B.cue")
    ap.add_argument("--duck-bin", default="external/squashfs-root/usr/bin/duckstation-qt")
    ap.add_argument("--display", default=":172")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9012)
    ap.add_argument("--max-stops", type=int, default=240)
    ap.add_argument("--out-csv", default="work/scen_analysis/state6_textgrid_watch.csv")
    args = ap.parse_args()

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

    rows: List[Dict[str, str]] = []
    xvfb = subprocess.Popen(
        ["Xvfb", args.display, "-screen", "0", "1024x768x24"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    duck = subprocess.Popen(
        [args.duck_bin, "-nogui", "-batch", "-statefile", args.state, args.iso],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        if not wait_port(args.host, args.port, 8.0):
            raise RuntimeError("duck gdb server not reachable")
        cli = GDBRemote(args.host, args.port, timeout=1.0)
        try:
            cli.request("?")
            # Watch first text-cell word (low probability noise, good starting anchor).
            req_ack(cli, "Z2,800eb3f8,2")

            for idx in range(1, args.max_stops + 1):
                cli.continue_run()
                stop = cli.recv_until_packet(8.0)
                regs = parse_regs_g(req_data(cli, "g"))
                pc = regs.get("pc", 0)
                gp = regs.get("r28", 0)
                sp = regs.get("r29", 0)
                a0 = regs.get("r4", 0)
                a1 = regs.get("r5", 0)
                a2 = regs.get("r6", 0)
                a3 = regs.get("r7", 0)
                v0 = regs.get("r2", 0)
                v1 = regs.get("r3", 0)

                script_cur = read_u32(cli, 0x800DBA1C)
                script_base = read_u32(cli, 0x800DB90C)
                grid_head = read_u32(cli, 0x800EB3F8)
                script_words = read_words(cli, script_cur, 10) if script_cur >= 0x80000000 else []
                pc_words = read_words(cli, pc, 4) if pc >= 0x80000000 else []
                around_grid = read_words(cli, 0x800EB3F8, 16)

                rows.append(
                    {
                        "idx": str(idx),
                        "stop": stop,
                        "pc": f"{pc:08X}",
                        "gp": f"{gp:08X}",
                        "sp": f"{sp:08X}",
                        "a0": f"{a0:08X}",
                        "a1": f"{a1:08X}",
                        "a2": f"{a2:08X}",
                        "a3": f"{a3:08X}",
                        "v0": f"{v0:08X}",
                        "v1": f"{v1:08X}",
                        "script_base": f"{script_base:08X}",
                        "script_cur": f"{script_cur:08X}",
                        "script_off": f"{(script_cur - script_base) & 0xFFFFFFFF:08X}",
                        "grid_head_u32": f"{grid_head:08X}",
                        "script_words": " ".join(f"{w:04X}" for w in script_words),
                        "pc_words": " ".join(f"{w:04X}" for w in pc_words),
                        "grid_words": " ".join(f"{w:04X}" for w in around_grid),
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
        xvfb.terminate()

    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "idx",
                "stop",
                "pc",
                "gp",
                "sp",
                "a0",
                "a1",
                "a2",
                "a3",
                "v0",
                "v1",
                "script_base",
                "script_cur",
                "script_off",
                "grid_head_u32",
                "script_words",
                "pc_words",
                "grid_words",
            ],
        )
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
