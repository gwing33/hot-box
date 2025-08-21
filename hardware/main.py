from machine import Pin
import onewire
import ds18x20
import time
import binascii
import os

# Set RTC
rtc = machine.RTC()

def iso_timestamp(t):
    timestamp = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(
        t[0], t[1], t[2], t[4], t[5], t[6]
    )
    return timestamp

def set_time_from_iso(iso_string):
    try:
        # Split date and time parts (separated by 'T' or space)
        if 'T' in iso_string:
            date_part, time_part = iso_string.split('T')
        else:
            date_part, time_part = iso_string.split(' ')
            
        # Parse date components
        year, month, day = [int(x) for x in date_part.split('-')]
        
        # Parse time components
        time_components = time_part.split(':')
        hour = int(time_components[0])
        minute = int(time_components[1])
        second = int(time_components[2])
        
        # weekday=0 (Monday), subseconds=0
        rtc.datetime((year, month, day, 0, hour, minute, second, 0))
        return True
        
    except Exception as e:
        print("Error setting time:", str(e))
        return False

# TEMP Hack to adjust the starting time when the device is fully offline
set_time_from_iso("2025-09-10T10:00:00")
default_now = rtc.datetime()
print(iso_timestamp(default_now))

# TODO: Need to move this function out of this file, but more work is needed once we bring in wifi
async def setTime(loop=0):
    #ntptime.settime() failure: [Errno 110] ETIMEDOUT
    #ntptime.settime() failure: overflow converting long int to machine word
    print('Attempt to set time:',1+loop)
    try:
        if loop<5:
            d=time.time()-debug.poweron.time
            ntptime.settime()
            debug.poweron.time=time.time()-d
            logging.clock.method="accurate"
        else:
            # if it did not work the second time it is not going to in my testing
            print("Failed to set time; Waiting 15 seconds")
            await sleep(15000)
            if logging.clock.time_delta:
                # If I do not have this by now something is very wrong
                # WiFi is working, therefore my server is up and has configured settings
                print("Setting clock using low precision method")
                from machine import RTC
                d=time.time()-debug.poweron.time
                t=time.gmtime(time.time()+logging.clock.time_delta)
                RTC().datetime((t[0], t[1], t[2], t[6], t[3], t[4], t[5], 0))
                debug.poweron.time=time.time()-d
                print("Result:",debugData(time.time()))
                logging.clock.method="low precision"
            else:
                # So lets get this strait:
                # The server's Guest OS (pfsense) has asigned a IP to us over WiFi
                # The server host is unrechable
                # How is that even possible
                print("Rebooting in 15 seconds, failed to set clock")
                await sleep(15000)
                from machine import reset
                reset()
        logging.clock.sync=time.time()
    except OverflowError:
        # it is not going to work
        print("overflow error; settime is borked")
        await setTime(9001)
    except OSError:
        print("ntptime.settime() failure")
        if loop>0:
            # Not expecting more than 1 failure, maybe waiting will help?
            await sleep(10000)
        await setTime(loop+1)

setTime()

def file_exists(file_path):
    directory = '/' if '/' not in file_path else file_path.rsplit('/', 1)[0]
    files = os.listdir(directory)
    file_name = file_path.split('/')[-1]
    return file_name in files

# Example usage
def openFile(count=1):
    file_path = f"test-{count}.csv"
    if file_exists(file_path):
        return openFile(count+1)
    else:
        return open(file_path, "w")

test_file = openFile()

def cToF(c):
    return (c*(9/5)) + 32

gp_pin = Pin(26)

ds18b20_sensor = ds18x20.DS18X20(onewire.OneWire(gp_pin))
sensor_mapping = {
    '280943230d0000c7': 'A Side',
    '28f475b80e000076': 'B Side'
}

def getSensorId(device):
    s = binascii.hexlify(device)
    return s.decode('ascii')

def getSensorName(device):
    id = getSensorId(device)
    if (id in sensor_mapping) :
        return sensor_mapping[id]
    else :
        return id

sensors = ds18b20_sensor.scan()

number_devices = len(sensors)

names = list(map(getSensorName, sensors))
test_file.write('Time,'+','.join(names)+'\n')
test_file.flush()

print('Number of sensors: ', number_devices)

while True:
    ds18b20_sensor.convert_temp()
    time.sleep_ms(750)
    now = rtc.datetime()
    newLine = [iso_timestamp(now)]
    for device in sensors:
        name = getSensorName(device)
        c_raw = ds18b20_sensor.read_temp(device)
        newLine.append(str(c_raw))
        f_raw = cToF(c_raw)
        c = round(c_raw,1)
        f = round(f_raw,1)
        print(f'{name}: {c} C, {f} F')

    test_file.write(','.join(newLine)+'\n')
    test_file.flush()
    time.sleep(60*15)

