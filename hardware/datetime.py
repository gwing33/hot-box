import time
import machine

def iso_timestamp(t):
    timestamp = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(
        t[0], t[1], t[2], t[4], t[5], t[6]
    )
    return timestamp

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

def initTime(rtc):
    default_now = rtc.datetime()
    print(iso_timestamp(default_now))
    setTime()
