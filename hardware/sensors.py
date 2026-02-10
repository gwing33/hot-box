import binascii

import ds18x20
import machine
import onewire

# Sensor Mapping
sensor_mapping = {
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
