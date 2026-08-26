import time

import network


def connectWifi(ssid=None, password=None):
    """
    Connect to WiFi. Credentials can be passed directly (from config.json)
    or fall back to secrets.py if not provided.
    """
    if ssid is None:
        try:
            from secrets import WIFI_PASSWORD, WIFI_SSID

            ssid, password = WIFI_SSID, WIFI_PASSWORD
        except ImportError:
            print("WiFi: no credentials provided and secrets.py not found")
            return False

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        print(f"WiFi: already connected")
        return True

    print(f"WiFi: connecting to {ssid}")
    wlan.connect(ssid, password or "")

    for _ in range(20):
        if wlan.isconnected():
            print(f"WiFi: connected, IP={wlan.ifconfig()[0]}")
            return True
        time.sleep(0.5)

    print(f"WiFi: failed to connect to {ssid}")
    return False


def disconnectWifi():
    """Disconnect and deactivate WiFi — call before deep sleep."""
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.disconnect()
        wlan.active(False)
        print("WiFi: disconnected")
    except Exception as e:
        print(f"WiFi: disconnect error: {e}")
