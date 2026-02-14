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


BP_ADDRS = [
    0x8001D198,  # dispatcher entry
    0x8001D354,  # parse u16 rel -> entry
    0x8001D3D4,  # op 0
    0x8001D3F0,  # op 1 (arg checks)
    0x8001D478,  # op 2
    0x8001D488,  # op 3
    0x8001D498,  # op 4
    0x8001D4A8,  # op 5
    0x8001D4B8,  # op 6
    0x8001D4C8,  # op 7
    0x8001D4D8,  # op 8
    0x80022C04,  # called handlers
    0x80022E2C,
    0x80023340,
    0x80023938,
    0x80023BA4,
    0x80023FAC,
    0x800241CC,
]


def build_bp_list(include_dispatch: bool) -> List[int]:
    if include_dispatch:
        return list(BP_ADDRS)
    return [a for a in BP_ADDRS if a != 0x8001D198]


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


def recv_step_stop(cli: GDBRemote, timeout_s: float = 2.0) -> str:
    # DuckStation sends "OK" first, then stop packet.
    p1 = cli.recv_until_packet(timeout_s)
    if p1.startswith("S"):
        return p1
    return cli.recv_until_packet(timeout_s)


def single_step(cli: GDBRemote, timeout_s: float = 2.0) -> str:
    p = cli.request("s", deadline_s=timeout_s)
    if p.startswith("S"):
        return p
    return cli.recv_until_packet(timeout_s)


def req_regs(cli: GDBRemote) -> Dict[str, int]:
    r = cli.request("g", deadline_s=2.0)
    while r.startswith("S") or r == "OK":
        r = cli.recv_until_packet(2.0)
    return parse_regs_g(r)


def read_u16(cli: GDBRemote, addr: int) -> int:
    b = bytes.fromhex(cli.request(f"m{addr:08x},2", deadline_s=2.0))
    return struct.unpack_from("<H", b, 0)[0]


def read_u32(cli: GDBRemote, addr: int) -> int:
    b = bytes.fromhex(cli.request(f"m{addr:08x},4", deadline_s=2.0))
    return struct.unpack_from("<I", b, 0)[0]


def read_words(cli: GDBRemote, addr: int, n: int) -> List[int]:
    b = bytes.fromhex(cli.request(f"m{addr:08x},{n*2:x}", deadline_s=2.0))
    return [struct.unpack_from("<H", b, i * 2)[0] for i in range(n)]


def op_name(pc: int) -> str:
    mp = {
        0x8001D3D4: "op0",
        0x8001D3F0: "op1_cond",
        0x8001D478: "op2_call_22c04",
        0x8001D488: "op3_call_22e2c",
        0x8001D498: "op4_call_23340",
        0x8001D4A8: "op5_call_23938",
        0x8001D4B8: "op6_call_23ba4",
        0x8001D4C8: "op7_call_23fac",
        0x8001D4D8: "op8_call_241cc",
        0x80022C04: "fn_22c04",
        0x80022E2C: "fn_22e2c",
        0x80023340: "fn_23340",
        0x80023938: "fn_23938",
        0x80023BA4: "fn_23ba4",
        0x80023FAC: "fn_23fac",
        0x800241CC: "fn_241cc",
        0x8001D354: "parse_rel_entry",
        0x8001D198: "dispatch_entry",
    }
    return mp.get(pc, f"pc_{pc:08X}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Trace Langrisser V runtime decoder handlers from savestate.")
    ap.add_argument("--state", default="work/sstates/SLPS-01819_2.sav")
    ap.add_argument("--iso", default="iso/SLPS-01818-9-B.cue")
    ap.add_argument("--duck-bin", default="external/squashfs-root/usr/bin/duckstation-qt")
    ap.add_argument("--display", default=":130")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9012)
    ap.add_argument("--max-stops", type=int, default=600)
    ap.add_argument("--mode", choices=["breakpoints", "step-dispatch"], default="breakpoints")
    ap.add_argument("--step-count", type=int, default=1600)
    ap.add_argument("--step-over-breakpoint", action="store_true")
    ap.add_argument("--include-dispatch-bp", action="store_true")
    ap.add_argument("--out-csv", default="work/scen_analysis/runtime_decode_trace.csv")
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

    xvfb = subprocess.Popen(
        ["Xvfb", args.display, "-screen", "0", "1024x768x24"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(0.8)
    duck = subprocess.Popen(
        [args.duck_bin, "-nogui", "-batch", "-statefile", args.state, args.iso],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    rows: List[dict] = []
    try:
        if not wait_port(args.host, args.port, 8.0):
            raise RuntimeError("duck gdb server not reachable")
        cli = GDBRemote(args.host, args.port, timeout=1.0)
        try:
            cli.request("?")
            bp_addrs = build_bp_list(args.include_dispatch_bp)
            for a in bp_addrs:
                try:
                    cli.request(f"z0,{a:08x},4")
                except Exception:
                    pass
                cli.request(f"Z0,{a:08x},4")

            # Run and capture stops.
            idx = 0
            if args.mode == "step-dispatch":
                # Land on dispatcher once, then step instructions through decode path.
                cli.continue_run()
                _ = cli.recv_until_packet(8.0)
                try:
                    cli.request("z0,8001d198,4")
                except Exception:
                    pass
                for _ in range(args.step_count):
                    idx += 1
                    stop = single_step(cli, 4.0)
                    regs = req_regs(cli)
                    pc = regs.get("pc", 0)
                    if pc == 0:
                        continue
                    gp = regs.get("r28", 0)
                    a0 = regs.get("r4", 0)
                    a1 = regs.get("r5", 0)
                    v0 = regs.get("r2", 0)
                    ra = regs.get("r31", 0)

                    row = {
                        "hit_index": idx,
                        "stop_pkt": stop,
                        "pc": f"{pc:08X}",
                        "pc_name": op_name(pc),
                        "a0": f"{a0:08X}",
                        "a1": f"{a1:08X}",
                        "v0": f"{v0:08X}",
                        "ra": f"{ra:08X}",
                        "gp": f"{gp:08X}",
                        "script_base": "",
                        "script_cur": "",
                        "gp_30c": "",
                        "rel_u16": "",
                        "entry_ptr": "",
                        "entry_head": "",
                        "entry_op_u8": "",
                        "entry_arg_u16": "",
                        "entry_words": "",
                        "cur_words": "",
                    }

                    try:
                        script_base = read_u32(cli, 0x800DB90C)
                        script_cur = read_u32(cli, 0x800DBA1C)
                        row["script_base"] = f"{script_base:08X}"
                        row["script_cur"] = f"{script_cur:08X}"
                        gp_30c = read_u32(cli, gp + 0x30C)
                        row["gp_30c"] = f"{gp_30c:08X}"
                        if pc == 0x8001D354:
                            rel = read_u16(cli, a1)
                            entry = (script_base + rel) & 0xFFFFFFFF
                            row["rel_u16"] = f"{rel:04X}"
                            row["entry_ptr"] = f"{entry:08X}"
                            ewords = read_words(cli, entry, 8)
                            row["entry_head"] = f"{ewords[0]:04X}"
                            row["entry_op_u8"] = f"{(ewords[1] & 0x00FF):02X}"
                            row["entry_arg_u16"] = f"{ewords[2]:04X}"
                            row["entry_words"] = " ".join(f"{x:04X}" for x in ewords)
                        if gp_30c >= 0x80000000:
                            cwords = read_words(cli, gp_30c, 8)
                            row["cur_words"] = " ".join(f"{x:04X}" for x in cwords)
                    except Exception:
                        pass

                    rows.append(row)
            else:
                for idx in range(1, args.max_stops + 1):
                    cli.continue_run()
                    try:
                        stop = cli.recv_until_packet(8.0)
                    except TimeoutError:
                        break
                    regs = req_regs(cli)
                    pc = regs.get("pc", 0)
                    gp = regs.get("r28", 0)
                    a0 = regs.get("r4", 0)
                    a1 = regs.get("r5", 0)
                    v0 = regs.get("r2", 0)
                    ra = regs.get("r31", 0)

                    row = {
                        "hit_index": idx,
                        "stop_pkt": stop,
                        "pc": f"{pc:08X}",
                        "pc_name": op_name(pc),
                        "a0": f"{a0:08X}",
                        "a1": f"{a1:08X}",
                        "v0": f"{v0:08X}",
                        "ra": f"{ra:08X}",
                        "gp": f"{gp:08X}",
                        "script_base": "",
                        "script_cur": "",
                        "gp_30c": "",
                        "rel_u16": "",
                        "entry_ptr": "",
                        "entry_head": "",
                        "entry_op_u8": "",
                        "entry_arg_u16": "",
                        "entry_words": "",
                        "cur_words": "",
                    }

                    try:
                        script_base = read_u32(cli, 0x800DB90C)
                        script_cur = read_u32(cli, 0x800DBA1C)
                        row["script_base"] = f"{script_base:08X}"
                        row["script_cur"] = f"{script_cur:08X}"
                        gp_30c = read_u32(cli, gp + 0x30C)
                        row["gp_30c"] = f"{gp_30c:08X}"
                        if pc == 0x8001D354:
                            rel = read_u16(cli, a1)
                            entry = (script_base + rel) & 0xFFFFFFFF
                            row["rel_u16"] = f"{rel:04X}"
                            row["entry_ptr"] = f"{entry:08X}"
                            ewords = read_words(cli, entry, 8)
                            row["entry_head"] = f"{ewords[0]:04X}"
                            row["entry_op_u8"] = f"{(ewords[1] & 0x00FF):02X}"
                            row["entry_arg_u16"] = f"{ewords[2]:04X}"
                            row["entry_words"] = " ".join(f"{x:04X}" for x in ewords)
                        if gp_30c >= 0x80000000:
                            cwords = read_words(cli, gp_30c, 8)
                            row["cur_words"] = " ".join(f"{x:04X}" for x in cwords)
                    except Exception:
                        pass

                    rows.append(row)
                    if args.step_over_breakpoint and pc in bp_addrs:
                        try:
                            cli.request(f"z0,{pc:08x},4")
                            single_step(cli, 4.0)
                            cli.request(f"Z0,{pc:08x},4")
                        except Exception:
                            pass
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
                "pc_name",
                "a0",
                "a1",
                "v0",
                "ra",
                "gp",
                "script_base",
                "script_cur",
                "gp_30c",
                "rel_u16",
                "entry_ptr",
                "entry_head",
                "entry_op_u8",
                "entry_arg_u16",
                "entry_words",
                "cur_words",
            ],
        )
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
