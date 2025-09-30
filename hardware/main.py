import machine
import time

from wifi import connectWifi
from datetime import iso_timestamp, initTime
from file import openFile
from util import cToF
from sensors import getSensors, convertTemp, readTemp, getAllSensorNames, getSensorName

rtc = machine.RTC()

# Connect to WiFi before starting
connectWifi()

# Set Proper Time
initTime(rtc)

# Instead of writing to a file as such, here is where I want to add in the ability to send this data to a server

# Open File to write file header
test_file = openFile()
test_file.write('Time,'+','.join(getAllSensorNames())+'\n')
test_file.flush()

while True:
    convertTemp()
    time.sleep_ms(750)

    now = rtc.datetime()
    newLine = [iso_timestamp(now)]
    for device in getSensors():
        name = getSensorName(device)
        c_raw = readTemp(device)
        newLine.append(str(c_raw))
        f_raw = cToF(c_raw)
        c = round(c_raw,1)
        f = round(f_raw,1)
        print(f'{name}: {c} C, {f} F')

    test_file.write(','.join(newLine)+'\n')
    test_file.flush()
    time.sleep(60*15)
