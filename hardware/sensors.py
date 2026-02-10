import binascii

import ds18x20
import machine
import onewire

# Sensor Mapping
sensor_mapping = {
    # First Prototype IDs
    "28f475b80e000076": "board",
    "28feb3230d000096": "b1-1",
    "28b046240d000002": "b1-2",
    "281c40240d0000bf": "b1-3",
    "28d2b8230d00002d": "b2-1",
    "282c19240d000034": "b2-2",
    "280b0b240d0000f8": "b2-3",
    "285dcb230d0000c0": "b3-1",
    "284e0a240d0000ab": "b3-2",
    "287e30230d0000f9": "b3-3",
    "285c63230d0000fa": "ambient",
    
    # Kyle's Sensors
    "28b32ab90e0000f3": "b1-1",
    "2828dc230d00009e": "b1-2",
    "2842f8b70e00007e": "b1-3",
    "281950b90e0000b0": "b2-1",
    "287b50b90e00001d": "b2-2",
    "285cfcb70e000029": "b2-3",
    "282d4eb90e00005f": "b3-1",
    "2862bab80e000038": "b3-2",
    "2880f8230d000084": "b3-3",
    "283343b80e000074": "ambient",
    
    # Xander's Xmen
     "28f475b80e000076": "board",
    "2809f0b70e0000cd": "b1-1",
    "2822edb80e000089": "b1-2",
    "28b270b80e000063": "b1-3",
    "285efbb80e00008c": "b2-1",
    "281927b80e000003": "b2-2",
    "28be51b80e00002b": "b2-3",
    "280e10b80e000008": "b3-1",
    "288b06b80e0000e9": "b3-2",
    "284ddfb80e000069": "b3-3",
    "2873fe230d000033": "ambient",
}

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


def getSensors():
    return sensors


def getAllSensorNames():
    return list(map(getSensorName, sensors))


def convertTemp():
    ds18b20_sensor.convert_temp()


def readTemp(device):
    return ds18b20_sensor.read_temp(device)
