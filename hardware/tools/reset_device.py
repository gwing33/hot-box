#!/usr/bin/env python3
"""
Backs up and clears a HotBox device's runtime state over serial (via
`mpremote`), so you can start a fresh test without waiting out the current
deep-sleep countdown or losing the previous run's data.

For each run this:
  1. Backs up debug.log + temperature_data.csv (if present) into a
     timestamped folder under hot-box/tmp/.
  2. Deletes debug.log, temperature_data.csv, and config.json from the
     device.
  3. Forces an immediate hardware reset, so the device boots straight back
     into "No config found, starting portal" instead of waiting up to
     SLEEP_MS for its next scheduled wake.

Requires `mpremote` (pip install mpremote) and the device must NOT be
connected to Thonny or any other serial client at the same time.

Usage:
    python3 reset_device.py [--port /dev/cu.usbmodem2101] [--keep-data]
                             [--no-reset] [--backup-dir PATH]
"""

import argparse
import glob
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_BACKUP_ROOT = SCRIPT_DIR.parents[1] / "tmp"  # hot-box/tmp

BACKUP_FILES = ["debug.log", "temperature_data.csv"]
DELETE_FILES = ["debug.log", "temperature_data.csv", "config.json"]


def find_port():
    candidates = sorted(glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/ttyACM*"))
    if not candidates:
        sys.exit(
            "No device found on /dev/cu.usbmodem* or /dev/ttyACM*.\n"
            "Is it plugged in, and disconnected from Thonny/another serial client?"
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


def device_listing(port):
    return mpremote(port, "fs", "ls").stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="Serial port (auto-detected if omitted)")
    parser.add_argument(
        "--backup-dir",
        default=str(DEFAULT_BACKUP_ROOT),
        help=f"Root folder for backups (default: {DEFAULT_BACKUP_ROOT})",
    )
    parser.add_argument(
        "--keep-data",
        action="store_true",
        help="Only delete config.json (keep debug.log/temperature_data.csv on device)",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Don't force an immediate reset after clearing",
    )
    args = parser.parse_args()

    port = args.port or find_port()
    print(f"Using port: {port}")

    listing = device_listing(port)
    present = [f for f in BACKUP_FILES if f in listing]

    backup_dir = None
    if present:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = Path(args.backup_dir) / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)
        for fname in present:
            dest = backup_dir / fname
            print(f"Backing up {fname} -> {dest}")
            mpremote(port, "fs", "cp", f":{fname}", str(dest))
    else:
        print("No debug.log/temperature_data.csv found on device — nothing to back up.")

    to_delete = ["config.json"] if args.keep_data else DELETE_FILES
    for fname in to_delete:
        result = mpremote(port, "fs", "rm", fname, check=False)
        print(f"Deleted {fname}" if result.returncode == 0 else f"Skipped {fname} (not present)")

    if not args.no_reset:
        print("Resetting device...")
        mpremote(port, "reset", check=False)

    if backup_dir:
        print(f"\nBackup saved to: {backup_dir}")
    print("Done — device will boot fresh and start the portal.")


if __name__ == "__main__":
    main()
