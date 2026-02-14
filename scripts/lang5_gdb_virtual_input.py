#!/usr/bin/env python3
import argparse
import os
import struct
import subprocess
import time
from pathlib import Path

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


def req_ack(cli: GDBRemote, payload: str, timeout: float = 2.0) -> str:
    return cli.request(payload, deadline_s=timeout)


def req_data(cli: GDBRemote, payload: str, timeout: float = 2.0) -> str:
    r = cli.request(payload, deadline_s=timeout)
    while r.startswith("S") or r == "OK":
        r = cli.recv_until_packet(timeout)
    return r


def write_u32(cli: GDBRemote, addr: int, value: int) -> None:
    data = struct.pack("<I", value & 0xFFFFFFFF).hex()
    req_ack(cli, f"M{addr:08x},4:{data}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Inject pad bits via GDB each frame (no X11 input).")
    ap.add_argument("--state", default="work/sstates/SLPS-01819_5.sav")
    ap.add_argument("--iso", default="iso/SLPS-01818-9-B.cue")
    ap.add_argument("--duck-bin", default="external/squashfs-root/usr/bin/duckstation-qt")
    ap.add_argument("--display", default=":179")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9012)
    ap.add_argument("--frame-bp", type=lambda x: int(x, 0), default=0x80030124)
    ap.add_argument("--hit-bp", type=lambda x: int(x, 0), action="append", default=[0x8001D7B4, 0x8001DB54])
    ap.add_argument("--press-mask", type=lambda x: int(x, 0), default=0x0008)  # START by default
    ap.add_argument("--frames", type=int, default=180)
    ap.add_argument("--hold-frames", type=int, default=2)
    ap.add_argument("--out-log", default="work/scen_analysis/gdb_virtual_input.log")
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

    lines = []
    xvfb = subprocess.Popen(["Xvfb", args.display, "-screen", "0", "1024x768x24"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    duck = subprocess.Popen([args.duck_bin, "-nogui", "-batch", "-statefile", args.state, args.iso], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_port(args.host, args.port, 8.0):
            raise RuntimeError("duck gdb server not reachable")
        cli = GDBRemote(args.host, args.port, timeout=1.0)
        try:
            req_ack(cli, "?")
            req_ack(cli, f"Z0,{args.frame_bp:08x},4")
            for hb in args.hit_bp:
                req_ack(cli, f"Z0,{hb:08x},4")

            for i in range(1, args.frames + 1):
                cli.continue_run()
                stop = cli.recv_until_packet(6.0)
                regs = parse_regs_g(req_data(cli, "g", timeout=2.0))
                pc = regs.get("pc", 0)
                lines.append(f"frame {i:03d} stop={stop} pc={pc:08X}")
                if pc in args.hit_bp:
                    lines.append(f"HIT target breakpoint at {pc:08X}")
                    break
                if pc != args.frame_bp:
                    continue
                press = (i % max(args.hold_frames, 1)) == 1
                val = args.press_mask if press else 0
                write_u32(cli, 0x800EB900, val)
                write_u32(cli, 0x800EB8F8, val)
                lines.append(f"inject val={val:04X}")
        finally:
            try:
                cli.interrupt()
            except Exception:
                pass
            cli.close()
    finally:
        duck.terminate()
        xvfb.terminate()

    out = Path(args.out_log)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
