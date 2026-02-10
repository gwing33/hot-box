import os
import time
from datetime import initTime, iso_timestamp
from secrets import HOT_BOX_ID

import machine
from api import send_api_request
from sensors import (
    convertTemp,
    getDeviceName,
    getSensorId,
    getSensorName,
    getSensors,
    readTemp,
)
from wifi import connectWifi

rtc = machine.RTC()

# CSV file setup
CSV_FILENAME = "temperature_data.csv"


def init_csv_file():
    """Initialize CSV file with headers if it doesn't exist"""
    try:
        # Check if file exists
        if CSV_FILENAME not in os.listdir():
            with open(CSV_FILENAME, "w") as f:
                f.write("timestamp,device_name,sensor_id,sensor_name,temperature_c\n")
            print(f"Created new CSV file: {CSV_FILENAME}")
        else:
            print(f"Using existing CSV file: {CSV_FILENAME}")
    except Exception as e:
        print(f"Error initializing CSV file: {e}")


def write_to_csv(timestamp, device_name, sensor_id, sensor_name, temperature):
    """Append temperature data to CSV file"""
    try:
        with open(CSV_FILENAME, "a") as f:
            f.write(
                f"{timestamp},{device_name},{sensor_id},{sensor_name},{temperature}\n"
            )
    except Exception as e:
        print(f"Error writing to CSV: {e}")


# Connect to WiFi before starting
connectWifi()

# Set Proper Time
initTime(rtc)

# Initialize CSV file
init_csv_file()

# Register Sensors
registeredSensors = True
for device in getSensors():
    id = getSensorId(device)
    name = getSensorName(device)
    print("Registering Sensor", id, name)
    resp = send_api_request(
        f"/api/box/{HOT_BOX_ID}/sensors/",
        data={"id": id, "name": name, "type": "ds18b20"},
        method="POST",
    )
    if resp != None and (resp["status"] == 200 | resp["status"] == 201):
        print("Sensor registered successfully", id, name)
    else:
        registeredSensors = False

if registeredSensors:
    print("All sensors registered")
else:
    print("API Comms Down")


while True:
    convertTemp()
    time.sleep_ms(750)

    now = rtc.datetime()
    for device in getSensors():
        id = getSensorId(device)
        name = getSensorName(device)
        device_name = getDeviceName(device)
        c_raw = readTemp(device)
        timestamp = iso_timestamp(now)
        print(device_name, id, name, c_raw)

        # Write to CSV file
        write_to_csv(timestamp, device_name, id, name, c_raw)

        if registeredSensors:
            resp = send_api_request(
                f"/api/box/{HOT_BOX_ID}/measurements/",
                data={
                    "sensor_id": id,
                    "timestamp": timestamp,
                    "temperature": c_raw,
                },
                method="POST",
            )
            if resp != None and (resp["status"] == 200 | resp["status"] == 201):
                print(f"Measured {name} ({id}): {c_raw}")
            else:
                print("Failed to record measurement", id, name, c_raw)

    time.sleep(10)
