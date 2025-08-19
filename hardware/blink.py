import machine
import onewire
import ds18x20
import time
import binascii
import sys

def cToF(c):
    return (c*(9/5)) + 32

gp_pin = machine.Pin(26)

ds18b20_sensor = ds18x20.DS18X20(onewire.OneWire(gp_pin))
sensor_mapping = {
    '280943230d0000c7': 'A Side',
    '28f475b80e000076': 'B Side'
}

def getMissingMappedSensors(all_sensors):
    missing_mappings = []
    for device in all_sensors:
        s = binascii.hexlify(device)
        readable_string = s.decode('ascii')
        if not (readable_string in sensor_mapping) :
            missing_mappings.append(readable_string)
    return missing_mappings

sensors = ds18b20_sensor.scan()

missing_mappings = getMissingMappedSensors(sensors)
is_missing_mappings = len(missing_mappings) != 0;

if(is_missing_mappings) :
    print('Missing Mappings, please identify...')
    print(list(missing_mappings))

print ('All Sensors Found and Mapped. Starting')

while True:
    ds18b20_sensor.convert_temp()
    time.sleep_ms(750)
    for device in sensors:
        s = binascii.hexlify(device)
        readable_string = s.decode('ascii')
        
        name = readable_string
        if (readable_string in sensor_mapping) :
            name = sensor_mapping[readable_string]
        
        c_raw = ds18b20_sensor.read_temp(device)
        f_raw = cToF(c_raw)
        c = round(c_raw,1)
        f = round(f_raw,1)
        print(f'{name}: {c} C, {f} F')
    time.sleep(1)
