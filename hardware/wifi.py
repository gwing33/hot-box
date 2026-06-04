import time

import network


# Connect to WiFi
def connectWifi():
    try:
        from secrets import WIFI_PASSWORD, WIFI_SSID
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


def disconnectWifi():
    # Disable WiFi — not needed until API calls are re-enabled
    wlan = network.WLAN(network.STA_IF)
    wlan.disconnect()
    wlan.active(False)


def initChip():
    """Initialize the CYW43439 firmware and immediately shut it down.
    Must be called even when WiFi networking is not needed — leaving the
    chip uninitialized causes it to reset the RP2350 after a few seconds.
    """
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.active(False)
    except Exception as e:
        print(f"WiFi chip init failed: {e}")
