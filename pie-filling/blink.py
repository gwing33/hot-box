import bluetooth
from machine import Pin
import network
import time
from micropython import const
import ubinascii

# BLE IRQ Events
_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)

# Custom Service and Characteristic UUIDs
WIFI_CONFIG_UUID = 'A5A5A5A5-A5A5-A5A5-A5A5-A5A5A5A5A5A5'
WIFI_SSID_UUID = 'B5B5B5B5-B5B5-B5B5-B5B5-B5B5B5B5B5B5'
WIFI_PASS_UUID = 'C5C5C5C5-C5C5-C5C5-C5C5-C5C5C5C5C5C5'
WIFI_STATUS_UUID = 'D5D5D5D5-D5D5-C5C5-C5C5-C5C5C5C5C5C5'

# GATT Flags
_FLAG_READ = const(0x0002)
_FLAG_WRITE = const(0x0008)
_FLAG_NOTIFY = const(0x0010)

# BLE Advertising Types
_ADV_TYPE_FLAGS = const(0x01)
_ADV_TYPE_NAME = const(0x09)
_ADV_TYPE_UUID128_ALL = const(0x07)

# Status LED
led = Pin("LED", Pin.OUT)

def uuid_to_bytes(uuid_str):
    """Convert a UUID string to bytes (16 bytes, little-endian)"""
    uuid = uuid_str.replace('-', '')
    return ubinascii.unhexlify(uuid)

class BLEWiFiConfig:
    def __init__(self):
        # Initialize BLE
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self.ble_irq)

        # Initialize WiFi
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)

        # State
        self.connected = False
        self.current_ssid = ""
        self.current_password = ""
        self.credentials_complete = False

        # Register GATT server
        self._setup_gatt()

        # Start advertising
        self._advertise()

    def _setup_gatt(self):
        # Service definition
        wifi_service = (
            bluetooth.UUID(WIFI_CONFIG_UUID),
            (
                (bluetooth.UUID(WIFI_SSID_UUID), _FLAG_READ | _FLAG_WRITE),
                (bluetooth.UUID(WIFI_PASS_UUID), _FLAG_WRITE),
                (bluetooth.UUID(WIFI_STATUS_UUID), _FLAG_READ | _FLAG_NOTIFY),
            ),
        )

        # Register service
        services = self.ble.gatts_register_services((wifi_service,))

        # Get handles from first (and only) service
        handles = services[0]
        self.ssid_handle = handles[0]
        self.pass_handle = handles[1]
        self.status_handle = handles[2]

        # Set initial values
        self.ble.gatts_write(self.ssid_handle, b'\x00' * 32)  # Empty SSID
        self.ble.gatts_write(self.pass_handle, b'\x00' * 64)  # Empty password
        self.ble.gatts_write(self.status_handle, b'\x00')     # Initial status

    def _advertise(self):
        name = "Pico 2W WiFi"

        # Advertising payload
        payload = bytearray()

        # Add flags
        payload.extend(bytes([2, _ADV_TYPE_FLAGS, 0x06]))

        # Add name
        payload.extend(bytes([len(name) + 1, _ADV_TYPE_NAME]) + name.encode('utf-8'))

        # Add service UUID
        uuid_bytes = uuid_to_bytes(WIFI_CONFIG_UUID)
        payload.extend(bytes([17, _ADV_TYPE_UUID128_ALL]) + uuid_bytes)

        # Start advertising
        self.ble.gap_advertise(100000, payload)
        print("BLE Advertising started")

    def check_credentials_and_connect(self):
        """Check if we have both credentials and try to connect"""
        if self.current_ssid and self.current_password:
            self.credentials_complete = True
            self.connect_wifi()
        else:
            self.credentials_complete = False

    def ble_irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            self.connected = True
            print("BLE Central connected")
            led.on()

        elif event == _IRQ_CENTRAL_DISCONNECT:
            self.connected = False
            print("BLE Central disconnected")
            led.off()
            self._advertise()

        elif event == _IRQ_GATTS_WRITE:
            # Get the handle from data
            handle = data[1]
            value = self.ble.gatts_read(handle)

            if handle == self.ssid_handle:
                new_ssid = value.decode().strip('\x00')
                if new_ssid != self.current_ssid:
                    self.current_ssid = new_ssid
                    print("New SSID:", self.current_ssid)
                    self.check_credentials_and_connect()

            elif handle == self.pass_handle:
                new_password = value.decode().strip('\x00')
                if new_password != self.current_password:
                    self.current_password = new_password
                    print("New password (hidden)")
                    self.check_credentials_and_connect()

    def connect_wifi(self):
        """Attempt to connect to WiFi with current credentials"""
        # If already connected with these credentials, skip
        if self.wlan.isconnected():
            current_config = self.wlan.config('essid')
            if current_config == self.current_ssid:
                print("Already connected to this network")
                self.ble.gatts_write(self.status_handle, b'\x02')  # Connected
                return True

        print("Connecting to WiFi:", self.current_ssid)
        self.ble.gatts_write(self.status_handle, b'\x01')  # Connecting

        try:
            # Disconnect if currently connected
            if self.wlan.isconnected():
                self.wlan.disconnect()
                time.sleep(1)

            self.wlan.connect(self.current_ssid, self.current_password)

            # Wait for connection
            max_wait = 30
            while max_wait > 0:
                status = self.wlan.status()
                if status < 0 or status >= 3:
                    break
                max_wait -= 1
                print("Waiting for connection...", max_wait)
                time.sleep(1)

            wlan_status = self.wlan.status()

            if wlan_status != 3:
              if wlan_status == network.STAT_IDLE:
                print("WiFi: Idle")
              if wlan_status == network.STAT_WRONG_PASSWORD:
                print("WiFi: Wrong password")
              if wlan_status == network.STAT_NO_AP_FOUND:
                print("WiFi: No access point found")
              if wlan_status == network.STAT_CONNECT_FAIL:
                print("WiFi: Failed to connectfor other reasons")

              self.ble.gatts_write(self.status_handle, b'\x03')  # Error
              return False

            print("WiFi connected!")
            print("IP:", self.wlan.ifconfig()[0])
            self.ble.gatts_write(self.status_handle, b'\x02')  # Connected
            return True

        except Exception as e:
            print("Connection error:", e)
            self.ble.gatts_write(self.status_handle, b'\x03')  # Error
            return False

def main():
    wifi_config = BLEWiFiConfig()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Stopping...")
        wifi_config.ble.active(False)

if __name__ == "__main__":
    main()
