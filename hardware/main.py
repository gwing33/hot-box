import machine
import time

from wifi import connectWifi
from datetime import iso_timestamp, initTime
from sensors import (
    getSensorId,
    getSensors,
    convertTemp,
    readTemp,
    getSensorName,
)
from api import send_api_request
from secrets import HOT_BOX_ID

rtc = machine.RTC()

# Connect to WiFi before starting
connectWifi()

# Set Proper Time
initTime(rtc)

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
    print("Failed to register all sensors")
    exit()

while True:
    convertTemp()
    time.sleep_ms(750)

    now = rtc.datetime()
    for device in getSensors():
        id = getSensorId(device)
        name = getSensorName(device)
        c_raw = readTemp(device)
        print(id, name, c_raw)
        resp = send_api_request(
            f"/api/box/{HOT_BOX_ID}/measurements/",
            data={
                "sensor_id": id,
                "timestamp": iso_timestamp(now),
                "temperature": c_raw,
            },
            method="POST",
        )
        if resp != None and (resp["status"] == 200 | resp["status"] == 201):
            print(f"Measured {name} ({id}): {c_raw}")
        else:
            print("Failed to record measurement", id, name, c_raw)

    time.sleep(10)
