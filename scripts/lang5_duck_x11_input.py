#!/usr/bin/env python3
import argparse
import subprocess
import time
from typing import List


def run(cmd: List[str], check: bool = True) -> str:
    p = subprocess.run(cmd, check=check, capture_output=True, text=True)
    return p.stdout


def find_main_window() -> str:
    out = run(["xdotool", "search", "--onlyvisible", "--class", "duckstation-qt"], check=False).strip()
    if not out:
        raise RuntimeError("No visible duckstation-qt windows found")

    # Prefer the top-level game window (usually has game title, not literal 'duckstation-qt').
    candidates = [w.strip() for w in out.splitlines() if w.strip()]
    scored = []
    for wid in candidates:
        name = run(["xdotool", "getwindowname", wid], check=False).strip()
        score = 0
        if name and name.lower() != "duckstation-qt":
            score += 10
        score += len(name)
        scored.append((score, wid, name))
    scored.sort(reverse=True)
    return scored[0][1]


def send_key(window_id: str, key: str, count: int, interval: float) -> None:
    for _ in range(count):
        subprocess.run(["xdotool", "key", "--window", window_id, key], check=False)
        time.sleep(interval)


def main() -> None:
    ap = argparse.ArgumentParser(description="Send automated keys to visible DuckStation game window.")
    ap.add_argument("--activate", action="store_true", help="Activate window before sending keys")
    ap.add_argument("--pre-delay", type=float, default=0.2, help="Delay after activation")
    ap.add_argument(
        "--seq",
        action="append",
        default=[],
        help="Sequence item '<Key>:<Count>:<IntervalSec>' (e.g. 'Return:12:0.09'). Can repeat.",
    )
    args = ap.parse_args()

    if not args.seq:
        raise SystemExit("No --seq provided")

    wid = find_main_window()
    name = run(["xdotool", "getwindowname", wid], check=False).strip()
    print(f"window={wid} name={name}")

    if args.activate:
        subprocess.run(["xdotool", "windowactivate", "--sync", wid], check=False)
        time.sleep(args.pre_delay)

    for item in args.seq:
        try:
            key, count_s, int_s = item.split(":", 2)
            count = int(count_s)
            interval = float(int_s)
        except Exception as e:
            raise SystemExit(f"Bad --seq format '{item}': {e}")
        print(f"send key={key} count={count} interval={interval}")
        send_key(wid, key, count, interval)


if __name__ == "__main__":
    main()
