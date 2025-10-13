import network
import time


# Connect to WiFi
def connectWifi():
    try:
        from secrets import WIFI_SSID, WIFI_PASSWORD
    except ImportError:
        print("Warning: secrets.py not found, skipping WiFi connection")
        return False

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print(f"Connecting to WiFi: {WIFI_SSID}")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        max_wait = 10
        while max_wait > 0:
            if wlan.isconnected():
                break
            max_wait -= 1
            print("Waiting for connection...")
            time.sleep(1)

    if wlan.isconnected():
        status = wlan.ifconfig()
        print(f"Connected! IP: {status[0]}")
        return True
    else:
        print("Failed to connect to WiFi")
        return False
