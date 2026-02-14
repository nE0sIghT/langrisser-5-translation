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


def req_regs(cli: GDBRemote) -> Dict[str, int]:
    r = cli.request("g", deadline_s=2.0)
    while r.startswith("S") or r == "OK":
        r = cli.recv_until_packet(2.0)
    return parse_regs_g(r)


def read_u32(cli: GDBRemote, addr: int) -> int:
    b = bytes.fromhex(cli.request(f"m{addr:08x},4", deadline_s=2.0))
    return struct.unpack_from("<I", b, 0)[0]


def read_words(cli: GDBRemote, addr: int, n: int) -> List[int]:
    b = bytes.fromhex(cli.request(f"m{addr:08x},{n*2:x}", deadline_s=2.0))
    return [struct.unpack_from("<H", b, i * 2)[0] for i in range(n)]


def main() -> None:
    ap = argparse.ArgumentParser(description="Watch Langrisser V runtime pointer writes from savestate.")
    ap.add_argument("--state", default="work/sstates/SLPS-01819_2.sav")
    ap.add_argument("--iso", default="iso/SLPS-01818-9-B.cue")
    ap.add_argument("--duck-bin", default="external/squashfs-root/usr/bin/duckstation-qt")
    ap.add_argument("--display", default=":131")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9012)
    ap.add_argument("--max-stops", type=int, default=120)
    ap.add_argument("--out-csv", default="work/scen_analysis/runtime_watch.csv")
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

    xvfb = subprocess.Popen(["Xvfb", args.display, "-screen", "0", "1024x768x24"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.8)
    duck = subprocess.Popen([args.duck_bin, "-nogui", "-batch", "-statefile", args.state, args.iso], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    rows: List[dict] = []
    try:
        if not wait_port(args.host, args.port, 8.0):
            raise RuntimeError("duck gdb server not reachable")
        cli = GDBRemote(args.host, args.port, timeout=1.0)
        try:
            cli.request("?")
            # Watch writes to script base/current pointers.
            for t, a in ((2, 0x800DBA1C), (2, 0x800DB90C), (2, 0x800DB8D4)):
                try:
                    cli.request(f"z{t},{a:08x},4")
                except Exception:
                    pass
                cli.request(f"Z{t},{a:08x},4")

            for i in range(1, args.max_stops + 1):
                cli.continue_run()
                try:
                    stop = cli.recv_until_packet(8.0)
                except TimeoutError:
                    break
                regs = req_regs(cli)
                pc = regs.get("pc", 0)
                gp = regs.get("r28", 0)
                base = read_u32(cli, 0x800DB90C)
                cur = read_u32(cli, 0x800DBA1C)
                flag = read_u32(cli, 0x800DB8D4)
                cur_words = ""
                if cur >= 0x80000000:
                    try:
                        cur_words = " ".join(f"{w:04X}" for w in read_words(cli, cur, 8))
                    except Exception:
                        pass

                rows.append(
                    {
                        "hit_index": i,
                        "stop_pkt": stop,
                        "pc": f"{pc:08X}",
                        "ra": f"{regs.get('r31',0):08X}",
                        "a0": f"{regs.get('r4',0):08X}",
                        "a1": f"{regs.get('r5',0):08X}",
                        "a2": f"{regs.get('r6',0):08X}",
                        "gp": f"{gp:08X}",
                        "script_base": f"{base:08X}",
                        "script_cur": f"{cur:08X}",
                        "interp_flag": f"{flag:08X}",
                        "cur_words": cur_words,
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
                "hit_index",
                "stop_pkt",
                "pc",
                "ra",
                "a0",
                "a1",
                "a2",
                "gp",
                "script_base",
                "script_cur",
                "interp_flag",
                "cur_words",
            ],
        )
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
