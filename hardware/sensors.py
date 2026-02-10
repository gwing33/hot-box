import binascii

import ds18x20
import machine
import onewire

# Sensor Mapping - Grouped by Device
sensor_devices = {
    "first_prototype": {
        "board": "28f475b80e000076",
        "b1-1": "28feb3230d000096",
        "b1-2": "28b046240d000002",
        "b1-3": "281c40240d0000bf",
        "b2-1": "28d2b8230d00002d",
        "b2-2": "282c19240d000034",
        "b2-3": "280b0b240d0000f8",
        "b3-1": "285dcb230d0000c0",
        "b3-2": "284e0a240d0000ab",
        "b3-3": "287e30230d0000f9",
        "ambient": "285c63230d0000fa",
    },
    "kyle": {
        "b1-1": "28b32ab90e0000f3",
        "b1-2": "2828dc230d00009e",
        "b1-3": "2842f8b70e00007e",
        "b2-1": "281950b90e0000b0",
        "b2-2": "287b50b90e00001d",
        "b2-3": "285cfcb70e000029",
        "b3-1": "282d4eb90e00005f",
        "b3-2": "2862bab80e000038",
        "b3-3": "2880f8230d000084",
        "ambient": "283343b80e000074",
    },
    "xander": {
        "b1-1": "2809f0b70e0000cd",
        "b1-2": "2822edb80e000089",
        "b1-3": "28b270b80e000063",
        "b2-1": "285efbb80e00008c",
        "b2-2": "281927b80e000003",
        "b2-3": "28be51b80e00002b",
        "b3-1": "280e10b80e000008",
        "b3-2": "288b06b80e0000e9",
        "b3-3": "284ddfb80e000069",
        "ambient": "2873fe230d000033",
    },
}

# Flattened lookup dictionaries
sensor_mapping = {}  # ID -> sensor name
sensor_device_mapping = {}  # ID -> device name
for device, sensors in sensor_devices.items():
    for name, sensor_id in sensors.items():
        sensor_mapping[sensor_id] = name
        sensor_device_mapping[sensor_id] = device

# Init Sensors
gp_pin = machine.Pin(26)
ds18b20_sensor = ds18x20.DS18X20(onewire.OneWire(gp_pin))
sensors = ds18b20_sensor.scan()

number_devices = len(sensors)
print("Number of sensors: ", number_devices)


def getSensorId(device):
    s = binascii.hexlify(device)
    return s.decode("ascii")


def getSensorName(device):
    id = getSensorId(device)
    if id in sensor_mapping:
        return sensor_mapping[id]
    else:
        print("Sensor Not Mapped", id)
        return id


def getDeviceName(device):
    id = getSensorId(device)
    if id in sensor_device_mapping:
        return sensor_device_mapping[id]
    else:
        return "unknown"


def getSensors():
    return sensors


def getAllSensorNames():
    return list(map(getSensorName, sensors))


def convertTemp():
    ds18b20_sensor.convert_temp()


def readTemp(device):
    return ds18b20_sensor.read_temp(device)
