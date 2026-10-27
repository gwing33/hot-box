#!/usr/bin/env python3
"""
Toggles the HotBox's `stay_awake` debug flag over serial (via `mpremote`).

While this flag file exists on the device, it pauses its normal test cycle
on boot and just idles in an interruptible loop \u2014 WiFi off, USB fully up \u2014
instead of deep sleeping. That means instant, reliable `mpremote`/Thonny
access instead of racing its ~10-15s awake window every 5 minutes. The
paused test resumes exactly where it left off once the flag is cleared (see
the stay-awake check near the top of main.py).

You still have to catch one real awake window to set it the first time —
there's no way around that, the device genuinely can't hear you while truly
asleep. After that, though, it won't go back to sleep until you `clear` it
(or 30 minutes pass \u2014 a safety net in main.py in case you forget and walk
away, so it doesn't just silently drain the battery).

Usage:
    python3 stay_awake.py set   [--port ...] [--no-reset]
    python3 stay_awake.py clear [--port ...]
"""

import argparse
import glob
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
FLAG_FILE = "stay_awake"


def find_port():
    candidates = sorted(glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/ttyACM*"))
    if not candidates:
        sys.exit(
            "No device found on /dev/cu.usbmodem* or /dev/ttyACM*.\n"
            "Is it plugged in, awake, and disconnected from Thonny/another serial client?"
        )
    if len(candidates) > 1:
        print(f"Multiple ports found, using the first: {candidates}")
    return candidates[0]


def mpremote(port, *args, check=True):
    cmd = ["python3", "-m", "mpremote", "connect", port, *args]
    result = subprocess.run(cmd, cwd=SCRIPT_DIR, capture_output=True, text=True)
    if check and result.returncode != 0:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise RuntimeError(f"mpremote command failed: {' '.join(args)}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["set", "clear"])
    parser.add_argument("--port", help="Serial port (auto-detected if omitted)")
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help=(
            "Don't force a reset after changing the flag. For 'set', it'll take effect "
            "on its next natural wake instead of immediately. For 'clear', main.py will "
            "just sit idle at a dead REPL until something else resets it — interrupting "
            "the running while-loop to remove the file kills it rather than letting it "
            "notice and resume on its own."
        ),
    )
    args = parser.parse_args()

    port = args.port or find_port()
    print(f"Using port: {port}")

    if args.action == "set":
        mpremote(port, "fs", "touch", FLAG_FILE)
        print(f"'{FLAG_FILE}' set.")
        if not args.no_reset:
            print("Resetting now so it takes effect immediately...")
            mpremote(port, "reset", check=False)
        print("Device will idle awake until you run: python3 stay_awake.py clear")
    else:
        result = mpremote(port, "fs", "rm", FLAG_FILE, check=False)
        if result.returncode == 0:
            print(f"'{FLAG_FILE}' cleared.")
        else:
            print(f"'{FLAG_FILE}' wasn't present on the device (already clear?).")
        # Removing the flag doesn't let the running while-loop "notice" and
        # fall through on its own — connecting at all (even just to rm the
        # file) interrupts whatever's running via Ctrl-C first, which kills
        # the loop outright rather than letting it re-check gracefully. So
        # main.py needs an explicit reset here to actually restart and
        # resume the test, or it'd just sit idle at a dead REPL instead.
        if not args.no_reset:
            print("Resetting so it actually resumes...")
            mpremote(port, "reset", check=False)


if __name__ == "__main__":
    main()
