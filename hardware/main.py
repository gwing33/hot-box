import os
import time
from datetime import iso_timestamp
from secrets import HOT_BOX_ID

import machine
from api import send_api_request
from log import log
from sensors import (
    convertTemp,
    getDeviceName,
    getSensorId,
    getSensorName,
    getSensors,
    readTemp,
)

rtc = machine.RTC()

CSV_FILENAME = "temperature_data.csv"
SLEEP_MS = 10_000

# GPIO24 = VBUS sense on Pico W/2W: HIGH when USB is connected.
# Default to True (USB/safe mode). Only switch to battery mode after
# two stable LOW readings — guards against false reads right after reset.
on_usb = True
try:
    time.sleep_ms(200)  # let VBUS settle after boot
    if machine.Pin(24, machine.Pin.IN).value() == 0:
        time.sleep_ms(50)
        if machine.Pin(24, machine.Pin.IN).value() == 0:
            on_usb = False
except Exception:
    pass  # keep on_usb = True (safe default)

# On USB: pause so Thonny/REPL has time to connect and interrupt with Ctrl+C
if on_usb:
    time.sleep(3)


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


def read_battery():
    try:
        # WL_GPIO2 must be driven high to connect VSYS/3 to ADC29 on Pico W/2W
        wl_pin = machine.Pin("WL_GPIO2", machine.Pin.OUT, value=1)
        v = machine.ADC(29).read_u16() * 3 * 3.3 / 65535
        wl_pin.init(machine.Pin.IN)
        return v
    except Exception as e:
        log(f"Battery read error: {e}", rtc)
        return -1


def measure():
    """One round of sensor reads, CSV writes, and battery logging."""
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

    log(f"Battery: {read_battery():.2f}V", rtc)


# --- Boot message ---
try:
    cause = machine.reset_cause()
    if cause == machine.DEEPSLEEP_RESET:
        log("Wake from deepsleep", rtc)
    else:
        log(f"--- Boot --- ({'USB' if on_usb else 'battery'}, cause={cause})", rtc)
except Exception:
    log(f"--- Boot --- ({'USB' if on_usb else 'battery'})", rtc)

init_csv_file()

if on_usb:
    # USB / development mode: stay in a loop so REPL remains accessible
    while True:
        log("Loop start", rtc)
        measure()
        log(f"Sleeping {SLEEP_MS // 1000}s (USB mode)", rtc)
        time.sleep(SLEEP_MS // 1000)
else:
    # Battery mode: single pass then deep sleep.
    # The RP2350 and CYW43439 are properly powered down during sleep.
    # On wake, main.py restarts from the top.
    measure()
    log(f"Deep sleeping {SLEEP_MS // 1000}s", rtc)
    machine.deepsleep(SLEEP_MS)
