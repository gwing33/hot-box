import os
import time
from datetime import iso_timestamp
from secrets import HOT_BOX_ID

import machine
from log import log
from sensors import (
    convertTemp,
    getDeviceName,
    getSensorId,
    getSensorName,
    getSensors,
    readTemp,
)

# Safe mode: hold GP15 low at boot (e.g. bridge GP15 to GND with a jumper)
# to skip deepsleep and stay in REPL. Falls back to a 15s Ctrl+C window.
_safe = machine.Pin(15, machine.Pin.IN, machine.Pin.PULL_UP)
if not _safe.value():
    print("Safe mode: GP15 held low, skipping deepsleep")
    raise SystemExit

print("Booting... Ctrl+C within 15s to interrupt")
time.sleep(15)

rtc = machine.RTC()

CSV_FILENAME = "temperature_data.csv"
SLEEP_MS = 60_000  # 1 minute — balances resolution vs battery life


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


# Log boot reason so we can distinguish cold starts from deepsleep wakes
try:
    cause = machine.reset_cause()
    if cause == machine.DEEPSLEEP_RESET:
        log("Wake from deepsleep", rtc)
    else:
        log(f"--- Boot --- (cause={cause})", rtc)
except Exception:
    log("--- Boot ---", rtc)

init_csv_file()

# Read sensors
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
        log(f"{device_name} {id} {name} {c_raw}", rtc)
        write_to_csv(timestamp, device_name, id, name, c_raw)

except Exception as e:
    log(f"Sensor error: {type(e).__name__}: {e}", rtc)

# Battery voltage
try:
    wl_pin = machine.Pin("WL_GPIO2", machine.Pin.OUT, value=1)
    battery_v = machine.ADC(29).read_u16() * 3 * 3.3 / 65535
    wl_pin.init(machine.Pin.IN)
except Exception as e:
    battery_v = -1
    log(f"Battery read error: {e}", rtc)
log(f"Battery: {battery_v:.2f}V", rtc)

# Deep sleep — near-zero current draw during sleep (~50µA vs ~30mA active)
# On wake, execution restarts from the top of main.py
log(f"Deep sleeping {SLEEP_MS // 1000}s", rtc)
machine.deepsleep(SLEEP_MS)
