import machine
import onewire
import ds18x20
import time
import binascii

def cToF(c):
    return (c*(9/5)) + 32

gp_pin = machine.Pin(26)

ds18b20_sensor = ds18x20.DS18X20(onewire.OneWire(gp_pin))

sensors = ds18b20_sensor.scan()

print('Found devices: ', sensors)

while True:
    ds18b20_sensor.convert_temp()
    time.sleep_ms(750)
    for device in sensors:
        s = binascii.hexlify(device)
        readable_string = s.decode('ascii')
        print(readable_string)
        c_raw = ds18b20_sensor.read_temp(device)
        f_raw = cToF(c_raw)
        c = round(c_raw,1)
        f = round(f_raw,1)
        print(f'{c} C, {f} F')
    time.sleep(1)

