import os
import time

import machine

# ── Safe mode: bridge GP15 to GND before powering on to force REPL ───────────
_safe_pin = machine.Pin(15, machine.Pin.IN, machine.Pin.PULL_UP)
if not _safe_pin.value():
    print("Safe mode: GP15 held low — dropping to REPL")
    raise SystemExit

# ── Stay-awake flag: pause the test and idle here instead of deep sleeping ───
# Deep sleep fully powers down USB for ~285 of every 300s, so catching the
# device for debugging means racing its ~10-15s awake window every cycle.
# Dropping a `stay_awake` marker file on the device (see tools/stay_awake.py)
# makes it loop here instead — awake, USB up, freely interruptible via
# mpremote/Thonny at any moment — until MAX_STAY_AWAKE_S elapses (checked
# via this loop's own timer, no external action needed — a safety net so a
# forgotten flag doesn't just silently drain the battery for days) or
# something clears the flag. Note that clearing it from outside (tools/
# stay_awake.py) always forces a reset to actually resume — connecting at
# all necessarily interrupts (Ctrl-C's) this loop first, so it can't just
# notice the file's gone and fall through gracefully on its own. The
# paused test resumes exactly where it left off either way
# (cfg/wakes_remaining untouched).
#
# (Deliberately an active loop, not `raise SystemExit` to idle at REPL like
# safe mode above — that pattern reliably crash-loops on this firmware for
# reasons we haven't root-caused; a running loop has always interrupted
# cleanly in testing.)
STAY_AWAKE_FILE = "stay_awake"
MAX_STAY_AWAKE_S = 1800  # 30 min safety cap — don't silently drain the battery
if STAY_AWAKE_FILE in os.listdir():
    print(f"'{STAY_AWAKE_FILE}' present — staying awake for debugging (test paused)")
    _waited = 0
    while STAY_AWAKE_FILE in os.listdir() and _waited < MAX_STAY_AWAKE_S:
        time.sleep(1)
        _waited += 1
    if _waited >= MAX_STAY_AWAKE_S:
        print("Stay-awake timed out after 30 min — resuming normal operation")
        try:
            os.remove(STAY_AWAKE_FILE)
        except Exception:
            pass
    else:
        print("Stay-awake flag removed — resuming normal operation")

from datetime import iso_timestamp

from config import build as build_config
from config import clear as clear_config
from config import load as load_config
from config import save as save_config
from log import log
from mqtt import publish_readings
import vault
from sensors import (
    convertTemp,
    getDeviceName,
    getSensorId,
    getSensorName,
    getSensors,
    readTemp,
)
from wifi import connectWifi, disconnectWifi

rtc = machine.RTC()

CSV_FILENAME = "temperature_data.csv"
SLEEP_MS = 300_000  # 5 minutes — must match config.py SLEEP_MS

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
                f.write("timestamp,device_name,sensor_id,sensor_name,temperature_c\n")
    except Exception as e:
        log(f"CSV init error: {e}", rtc)


def write_to_csv(timestamp, device_name, sensor_id, sensor_name, temperature):
    try:
        with open(CSV_FILENAME, "a") as f:
            f.write(
                f"{timestamp},{device_name},{sensor_id},{sensor_name},{temperature}\n"
            )
    except Exception as e:
        log(f"CSV write error: {e}", rtc)


# ── Boot ──────────────────────────────────────────────────────────────────────

# This build of MicroPython for the Pico W has no machine.DEEPSLEEP_RESET —
# machine.deepsleep() wakes via a watchdog-forced reset instead, which
# reset_cause() reports as WDT_RESET. Nothing else in this codebase arms a
# watchdog, so WDT_RESET is an unambiguous deep-sleep-wake signal here. We
# still check DEEPSLEEP_RESET too (via getattr) in case a future firmware
# build adds it.
_DEEPSLEEP_CAUSES = {
    cause
    for cause in (
        getattr(machine, "DEEPSLEEP_RESET", None),
        getattr(machine, "WDT_RESET", None),
    )
    if cause is not None
}

is_deepsleep_wake = False
try:
    is_deepsleep_wake = machine.reset_cause() in _DEEPSLEEP_CAUSES
except Exception:
    pass

if is_deepsleep_wake:
    log("Wake from deepsleep", rtc)
else:
    log("--- Boot ---", rtc)

init_csv_file()

# ── Config / Portal ───────────────────────────────────────────────────────────
# On cold boot: load saved config or run portal.
# On deepsleep wake: always use saved config (don't interrupt test for portal).

cfg = load_config()
portal_error = ""

if not is_deepsleep_wake:
    if cfg is None:
        # First run — no saved config, go straight to portal
        log("No config found, starting portal", rtc)
        from portal import run_portal

        raw = run_portal()
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
            f"Portal done — {'indefinite' if cfg['indefinite'] else str(cfg['duration_hours']) + 'h'}",
            rtc,
        )
        # WiFi is already connected from portal, skip reconnect below
    else:
        # Cold boot with saved config — try saved credentials
        log(f"Saved config found, connecting to {cfg['wifi_ssid']}", rtc)
        if not connectWifi(cfg["wifi_ssid"], cfg["wifi_password"]):
            # Credentials no longer work — re-run portal
            log("WiFi failed with saved config, restarting portal", rtc)
            from portal import run_portal

            raw = run_portal(
                error="Could not connect with saved credentials. Please reconfigure."
            )
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
                f"Portal done — {'indefinite' if cfg['indefinite'] else str(cfg['duration_hours']) + 'h'}",
                rtc,
            )

# ── Duration check ────────────────────────────────────────────────────────────

if cfg and not cfg.get("indefinite", True):
    wakes_remaining = cfg.get("wakes_remaining", 0)
    if wakes_remaining <= 0:
        log(
            "Test complete — not sleeping again. Bridge GP15→GND and reboot to reset.",
            rtc,
        )
        raise SystemExit

# ── WiFi + time sync (before readings, so THIS wake's timestamps are real) ────
# Cold boot already connected WiFi above (via the portal, or the "saved
# config" retry). Deep sleep drops WiFi on every sleep, so reconnect fresh
# here. Either way, sync real time over NTP now, on every wake — deep sleep
# is a full reset, so the RTC always comes back at its 2021-01-01 default
# and needs resyncing every time, not just once per test.

wifi_connected = False
if cfg:
    if is_deepsleep_wake:
        wifi_connected = connectWifi(cfg["wifi_ssid"], cfg["wifi_password"])
    else:
        import network

        wifi_connected = network.WLAN(network.STA_IF).isconnected()

    if wifi_connected:
        try:
            import ntptime

            ntptime.settime()
        except Exception as e:
            log(f"NTP sync failed: {type(e).__name__}: {e}", rtc)
    else:
        log("WiFi unavailable — timestamps this cycle will be wrong", rtc)

# ── Sensor read + CSV ─────────────────────────────────────────────────────────

readings = []
try:
    convertTemp()
    time.sleep_ms(750)

    now = rtc.datetime()
    for device in getSensors():
        id = getSensorId(device)
        name = getSensorName(device)
        device_name = getDeviceName(device)
        c_raw = readTemp(device)
        timestamp = iso_timestamp(now)
        readings.append((timestamp, device_name, id, name, c_raw))
        log(f"{device_name} {id} {name} {c_raw}", rtc)
        write_to_csv(timestamp, device_name, id, name, c_raw)
        blink_led()

except Exception as e:
    log(f"Sensor error: {type(e).__name__}: {e}", rtc)

# ── MQTT + Vault sync (WiFi already connected/synced above) ──────────────────

if readings and cfg:
    try:
        if wifi_connected:
            publish_readings(readings)

            # Nopal Vault sync (sync-api "hot-box-data" analysis) — no-op
            # entirely if no api_token was set in the portal. First wake of
            # a new test resolves/creates the analysis + a fresh run and
            # caches both in cfg; every wake after that just appends rows.
            if cfg.get("api_token"):
                if not cfg.get("vault_run_name"):
                    updated_cfg = vault.ensure_run(cfg, readings, rtc)
                    if updated_cfg:
                        cfg = updated_cfg
                        save_config(cfg)
                if cfg.get("vault_run_name"):
                    vault.send_readings(cfg, readings, rtc)
        else:
            log("WiFi unavailable, skipping MQTT this cycle", rtc)
    except Exception as e:
        log(f"WiFi/MQTT error: {type(e).__name__}: {e}", rtc)
    finally:
        disconnectWifi()

# ── Battery voltage ───────────────────────────────────────────────────────────

try:
    wl_pin = machine.Pin("WL_GPIO2", machine.Pin.OUT, value=1)
    battery_v = machine.ADC(29).read_u16() * 3 * 3.3 / 65535
    wl_pin.init(machine.Pin.IN)
except Exception as e:
    battery_v = -1
    log(f"Battery read error: {e}", rtc)
log(f"Battery: {battery_v:.2f}V", rtc)

# ── Decrement duration counter ────────────────────────────────────────────────

if cfg and not cfg.get("indefinite", True):
    cfg["wakes_remaining"] = max(0, cfg.get("wakes_remaining", 1) - 1)
    save_config(cfg)
    log(f"Wakes remaining: {cfg['wakes_remaining']}", rtc)

# ── Deep sleep ────────────────────────────────────────────────────────────────

log(f"Deep sleeping {SLEEP_MS // 1000}s", rtc)
machine.deepsleep(SLEEP_MS)
