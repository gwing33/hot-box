import machine
import binascii
import onewire
import ds18x20

# Sensor Mapping
sensor_mapping = {
    '280943230d0000c7': 'A Side',
    '28f475b80e000076': 'B Side'
}

# Init Sensors
gp_pin = machine.Pin(26)
ds18b20_sensor = ds18x20.DS18X20(onewire.OneWire(gp_pin))
sensors = ds18b20_sensor.scan()

number_devices = len(sensors)
print('Number of sensors: ', number_devices)

def getSensorId(device):
    s = binascii.hexlify(device)
    return s.decode('ascii')

def getSensorName(device):
    id = getSensorId(device)
    if (id in sensor_mapping) :
        return sensor_mapping[id]
    else :
        return id

def getSensors():
    return sensors

def getAllSensorNames():
    return list(map(getSensorName, sensors))

def convertTemp():
    ds18b20_sensor.convert_temp()

def readTemp(device):
    return ds18b20_sensor.read_temp(device)
