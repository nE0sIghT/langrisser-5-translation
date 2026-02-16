#!/usr/bin/env python3
import argparse
import time

from evdev import UInput, ecodes as e


def pulse(ui: UInput, code: int, delay: float = 0.06) -> None:
    ui.write(e.EV_KEY, code, 1)
    ui.syn()
    time.sleep(delay)
    ui.write(e.EV_KEY, code, 0)
    ui.syn()


def main() -> None:
    ap = argparse.ArgumentParser(description='Send virtual gamepad Start/Cross pulses via uinput.')
    ap.add_argument('--start-count', type=int, default=20)
    ap.add_argument('--cross-count', type=int, default=40)
    ap.add_argument('--interval', type=float, default=0.12)
    ap.add_argument('--initial-wait', type=float, default=1.2)
    args = ap.parse_args()

    caps = {
        e.EV_KEY: [
            e.BTN_SOUTH, e.BTN_EAST, e.BTN_NORTH, e.BTN_WEST,
            e.BTN_TL, e.BTN_TR, e.BTN_SELECT, e.BTN_START,
            e.BTN_THUMBL, e.BTN_THUMBR,
            e.BTN_DPAD_UP, e.BTN_DPAD_DOWN, e.BTN_DPAD_LEFT, e.BTN_DPAD_RIGHT,
        ]
    }

    with UInput(caps, name='Lang5 Virtual Pad', bustype=0x03, vendor=0x1234, product=0x5678, version=0x0001) as ui:
        print('uinput_device_created')
        time.sleep(args.initial_wait)

        for _ in range(args.start_count):
            pulse(ui, e.BTN_START)
            time.sleep(args.interval)

        for _ in range(args.cross_count):
            pulse(ui, e.BTN_SOUTH)
            time.sleep(args.interval)

        # Small directional nudge in case menu focus requires it
        for code in (e.BTN_DPAD_DOWN, e.BTN_DPAD_UP):
            for _ in range(3):
                pulse(ui, code)
                time.sleep(args.interval)


if __name__ == '__main__':
    main()
