import os
import time

import machine

from datetime import iso_timestamp

from config import build as build_config
from config import clear as clear_config
from config import load as load_config
from config import save as save_config
from log import log
import vault
from sensors import (
    checkWiring,
    convertTemp,
    getDeviceName,
    getSensorId,
    getSensorName,
    getSensorSide,
    getSensors,
    readTemp,
)
from wifi import connectWifi, disconnectWifi

rtc = machine.RTC()

CSV_FILENAME = "temperature_data.csv"
CYCLE_S = 300  # 5 minutes between readings — must match config.py's CYCLE_S.
# This box is hard-wired (no battery), so it just loops with a plain
# time.sleep() between readings instead of deep sleeping — keeps USB/REPL
# available at all times for debugging, with no power-saving need to justify
# the deep-sleep complexity the original battery-powered hardware needed.

try:
    _led = machine.Pin("LED", machine.Pin.OUT)
except Exception:
    _led = None


def blink_led(times=1, on_ms=80, off_ms=80):
    """Blink the onboard LED as a visible heartbeat — used to confirm a
    reading was recorded without needing to watch the logs."""
    if _led is None:
        return
    try:
        for i in range(times):
            _led.on()
            time.sleep_ms(on_ms)
            _led.off()
            if i < times - 1:
                time.sleep_ms(off_ms)
    except Exception:
        pass


# ── CSV helpers ───────────────────────────────────────────────────────────────


def init_csv_file():
    try:
        if CSV_FILENAME not in os.listdir():
            with open(CSV_FILENAME, "w") as f:
                f.write(
                    "timestamp,device_name,side,sensor_id,sensor_name,temperature_c\n"
                )
    except Exception as e:
        log(f"CSV init error: {e}", rtc)


def write_to_csv(timestamp, device_name, side, sensor_id, sensor_name, temperature):
    try:
        with open(CSV_FILENAME, "a") as f:
            f.write(
                f"{timestamp},{device_name},{side},{sensor_id},{sensor_name},{temperature}\n"
            )
    except Exception as e:
        log(f"CSV write error: {e}", rtc)


def take_reading():
    """Reads every sensor once, logging/CSV-writing each as it goes.
    Returns the list of (timestamp, device_name, side, sensor_id,
    sensor_name, temperature_c) readings (empty on error)."""
    readings = []
    try:
        convertTemp()
        time.sleep_ms(750)

        now = rtc.datetime()
        for device in getSensors():
            id = getSensorId(device)
            name = getSensorName(device)
            device_name = getDeviceName(device)
            side = getSensorSide(device)
            c_raw = readTemp(device)
            timestamp = iso_timestamp(now)
            readings.append((timestamp, device_name, side, id, name, c_raw))
            log(f"{device_name} {side} {id} {name} {c_raw}", rtc)
            write_to_csv(timestamp, device_name, side, id, name, c_raw)
            blink_led()
    except Exception as e:
        log(f"Sensor error: {type(e).__name__}: {e}", rtc)
    return readings


def sync_vault(cfg, readings):
    """Pushes this cycle's readings to the Nopal Vault sync-api analysis, if
    an api_token was set in the portal. Returns the (possibly updated) cfg —
    callers should save it if it's a new object."""
    if not (readings and cfg.get("api_token")):
        return cfg
    try:
        if not cfg.get("vault_run_name"):
            updated_cfg = vault.ensure_run(cfg, readings, rtc)
            if updated_cfg:
                cfg = updated_cfg
                save_config(cfg)
        if cfg.get("vault_run_name"):
            vault.send_readings(cfg, readings, rtc)
    except Exception as e:
        log(f"Vault error: {type(e).__name__}: {e}", rtc)
    return cfg


def run_portal_flow(error=""):
    """Runs the setup portal (blocking until WiFi connects) and returns a
    freshly built, saved config."""
    from portal import run_portal

    raw = run_portal(error=error)
    cfg = build_config(
        wifi_ssid=raw["wifi_ssid"],
        wifi_password=raw["wifi_password"],
        api_token=raw["api_token"],
        project=raw["project"],
        indefinite=raw["indefinite"],
        duration_hours=raw["duration_hours"],
    )
    save_config(cfg)
    log(
        f"Portal done — {'indefinite' if cfg['indefinite'] else str(cfg['duration_hours']) + 'h'} test starting",
        rtc,
    )
    return cfg


# ── Boot ──────────────────────────────────────────────────────────────────────

log("--- Boot ---", rtc)
init_csv_file()

for sensor_id, configured_side, found_side in checkWiring():
    log(
        f"WIRING MISMATCH: {sensor_id} configured as '{configured_side}' but found on '{found_side}' bus",
        rtc,
    )

cfg = load_config()

if cfg is None:
    log("No config found, starting portal", rtc)
    cfg = run_portal_flow()
    # WiFi is already connected from the portal, no need to reconnect below.
else:
    log(f"Saved config found, connecting to {cfg['wifi_ssid']}", rtc)
    if not connectWifi(cfg["wifi_ssid"], cfg["wifi_password"]):
        log("WiFi failed with saved config, restarting portal", rtc)
        cfg = run_portal_flow(
            error="Could not connect with saved credentials. Please reconfigure."
        )

# ── Main loop ─────────────────────────────────────────────────────────────────
# Runs forever: takes a reading every CYCLE_S, and automatically drops back
# into the setup portal (instead of halting) once a fixed-duration test's
# cycle budget runs out, so the device is discoverable again with no manual
# reset needed.

while True:
    if not cfg.get("indefinite", True) and cfg.get("cycles_remaining", 0) <= 0:
        log("Test complete — returning to setup portal", rtc)
        clear_config()
        disconnectWifi()
        cfg = run_portal_flow()
        continue

    if not connectWifi(cfg["wifi_ssid"], cfg["wifi_password"]):
        log("WiFi unavailable this cycle — will retry next cycle", rtc)
        time.sleep(CYCLE_S)
        continue

    try:
        import ntptime

        ntptime.settime()
    except Exception as e:
        log(f"NTP sync failed: {type(e).__name__}: {e}", rtc)

    readings = take_reading()
    cfg = sync_vault(cfg, readings)

    if not cfg.get("indefinite", True):
        cfg["cycles_remaining"] = max(0, cfg.get("cycles_remaining", 1) - 1)
        save_config(cfg)
        log(f"Cycles remaining: {cfg['cycles_remaining']}", rtc)

    time.sleep(CYCLE_S)
