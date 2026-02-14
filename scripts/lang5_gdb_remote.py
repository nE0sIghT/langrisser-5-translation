#!/usr/bin/env python3
import argparse
import socket
import struct
import time
from typing import Optional, Tuple


def checksum(payload: str) -> int:
    return sum(payload.encode("ascii")) & 0xFF


def make_packet(payload: str) -> bytes:
    return f"${payload}#{checksum(payload):02x}".encode("ascii")


class GDBRemote:
    def __init__(self, host: str, port: int, timeout: float = 1.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.buf = b""

    def close(self) -> None:
        self.sock.close()

    def send_raw(self, data: bytes) -> None:
        self.sock.sendall(data)

    def send_packet(self, payload: str) -> None:
        self.send_raw(make_packet(payload))

    def _read_some(self) -> bool:
        try:
            data = self.sock.recv(4096)
        except socket.timeout:
            return False
        if not data:
            raise RuntimeError("remote closed connection")
        self.buf += data
        return True

    def _pop_packet(self) -> Optional[Tuple[str, str]]:
        # Returns tuple(kind, payload): kind is "ack", "pkt", or "int".
        if not self.buf:
            return None
        c0 = self.buf[:1]
        if c0 in (b"+", b"-"):
            self.buf = self.buf[1:]
            return ("ack", c0.decode("ascii"))
        if c0 == b"\x03":
            self.buf = self.buf[1:]
            return ("int", "\x03")
        if c0 != b"$":
            self.buf = self.buf[1:]
            return None
        idx = self.buf.find(b"#")
        if idx < 0 or idx + 3 > len(self.buf):
            return None
        payload_b = self.buf[1:idx]
        cks_b = self.buf[idx + 1 : idx + 3]
        self.buf = self.buf[idx + 3 :]
        try:
            payload = payload_b.decode("ascii")
            cks = int(cks_b.decode("ascii"), 16)
        except Exception:
            return None
        if (sum(payload_b) & 0xFF) != cks:
            raise RuntimeError(f"bad checksum for payload {payload!r}")
        return ("pkt", payload)

    def recv_until_packet(self, deadline_s: float) -> str:
        end = time.time() + deadline_s
        while time.time() < end:
            evt = self._pop_packet()
            if evt:
                kind, payload = evt
                if kind == "pkt":
                    # Ack server packet (duck ignores, but harmless and spec-compliant)
                    self.send_raw(b"+")
                    return payload
                continue
            self._read_some()
        raise TimeoutError("timeout waiting for packet")

    def request(self, payload: str, deadline_s: float = 2.0) -> str:
        self.send_packet(payload)
        return self.recv_until_packet(deadline_s)

    def continue_run(self) -> None:
        # Special-case continue packet for this server.
        self.send_raw(b"$c#63")

    def interrupt(self) -> None:
        self.send_raw(b"\x03")


def parse_regs_g(raw: str) -> dict:
    b = bytes.fromhex(raw)
    words = [struct.unpack_from("<I", b, i * 4)[0] for i in range(len(b) // 4)]
    names = [f"r{i}" for i in range(32)] + ["sr", "lo", "hi", "bad", "cause", "pc"]
    out = {}
    for i, n in enumerate(names):
        if i < len(words):
            out[n] = words[i]
    return out


def mem_words_le(data_hex: str) -> list[int]:
    b = bytes.fromhex(data_hex)
    out = []
    for i in range(0, len(b) - 1, 2):
        out.append(struct.unpack_from("<H", b, i)[0])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Minimal GDB remote client for DuckStation.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9012)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument(
        "--bp",
        action="append",
        default=[],
        help="Breakpoint spec '<type>:<addr_hex>' where type 0=exec, 2=write, 3=read, 4=rw.",
    )
    ap.add_argument("--dump-a1-len", type=int, default=0x40)
    ap.add_argument("--dump-addr", action="append", default=["800db90c,40", "800dba1c,40"])
    ap.add_argument("--max-stops", type=int, default=1)
    args = ap.parse_args()

    cli = GDBRemote(args.host, args.port, timeout=1.0)
    try:
        try:
            stop = cli.request("?")
            print(f"stop_reply={stop}")
        except Exception as e:
            print(f"stop_reply_error={e}")

        for bp in args.bp:
            if ":" in bp:
                tp_s, addr_s = bp.split(":", 1)
                bpt = int(tp_s, 10)
            else:
                bpt = 0
                addr_s = bp
            resp = cli.request(f"Z{bpt},{addr_s},4")
            print(f"set_bp type={bpt} addr={addr_s} -> {resp}")

        for i in range(args.max_stops):
            cli.continue_run()
            print(f"continued[{i + 1}]")
            stop = cli.recv_until_packet(args.timeout)
            print(f"stopped[{i + 1}]={stop}")

            regs_raw = cli.request("g", deadline_s=3.0)
            regs = parse_regs_g(regs_raw)
            pc = regs.get("pc", 0)
            a0 = regs.get("r4", 0)
            a1 = regs.get("r5", 0)
            gp = regs.get("r28", 0)
            print(f"regs[{i + 1}] pc={pc:08X} a0={a0:08X} a1={a1:08X} gp={gp:08X}")

            if a1:
                m = cli.request(f"m{a1:08x},{args.dump_a1_len:x}", deadline_s=3.0)
                ws = mem_words_le(m)
                print(f"a1_words[{i + 1}]=" + " ".join(f"{w:04X}" for w in ws))

            for da in args.dump_addr:
                addr_s, ln_s = da.split(",", 1)
                r = cli.request(f"m{int(addr_s,16):08x},{int(ln_s,16):x}", deadline_s=3.0)
                print(f"mem_{addr_s}[{i + 1}]={r}")

    finally:
        try:
            cli.interrupt()
        except Exception:
            pass
        cli.close()


if __name__ == "__main__":
    main()
