"""
Sensor identification helper for setting up a NEW HotBox device (or
re-checking an existing one). Figures out which physical DS18B20 sensor is
which, so you can build/update its entry in `sensor_devices` (sensors.py)
without guessing.

Run this directly on the device — via Thonny's Run button, or:
    mpremote connect <port> run tools/identify_sensors.py
(Ctrl-C in Thonny, or unplug/re-run, to stop — it loops forever.)

Workflow:
  1. Wire up all of this device's DS18B20 sensors to GP26 (same pin
     sensors.py uses) before running this script.
  2. Run it. Every ~1.5s it reprints every sensor it can see: its unique
     64-bit ID and current temperature. A sensor whose reading jumped since
     the last print gets a "<-- warming up" marker.
  3. One at a time, pinch/hold a single physical sensor between two fingers
     for a few seconds and watch which ID gets the marker — that's the one
     you're touching. Write down `id -> position` (e.g. b1-1, b1-2, b1-3,
     b2-1, ..., ambient) as you go. Let it cool back down between sensors
     so the next one is unambiguous.
  4. Once every sensor is identified, add a new entry to `sensor_devices`
     in sensors.py:

         "your-device-name": {
             "b1-1": "<id>",
             "b1-2": "<id>",
             ...
             "ambient": "<id>",
         },

     `your-device-name` is what shows up as `device_name` in every log
     line, local CSV row, MQTT topic, and Nopal Vault run this box
     produces from then on (see getDeviceName() in sensors.py) — pick
     something short and unique across your fleet (e.g. "g3", not
     "hotbox" or "test"). It is NOT set via the WiFi portal; it's
     inferred purely from which sensor IDs this device has, so it MUST
     be added here before deploying.
  5. Push the updated sensors.py to the device (see hardware/README.md)
     and you're done — getSensors()/getDeviceName()/getSensorName() will
     now recognize this device's sensors automatically.
"""

import binascii
import time

import ds18x20
import machine
import onewire

GP_PIN = 26

pin = machine.Pin(GP_PIN)
sensor = ds18x20.DS18X20(onewire.OneWire(pin))

print(f"Scanning for DS18B20 sensors on GP{GP_PIN}...")
print("Pinch one sensor at a time and watch for '<-- warming up'.")
print("Ctrl-C to stop.\n")

previous = {}

while True:
    devices = sensor.scan()
    if not devices:
        print("No sensors found — check wiring on GP{}.".format(GP_PIN))
        time.sleep(2)
        continue

    sensor.convert_temp()
    time.sleep_ms(750)

    print("-" * 44)
    for device in devices:
        sensor_id = binascii.hexlify(device).decode("ascii")
        temp_c = sensor.read_temp(device)
        prev_temp = previous.get(sensor_id, temp_c)
        delta = temp_c - prev_temp
        marker = "  <-- warming up" if delta > 0.25 else ""
        print(f"{sensor_id}  {temp_c:6.3f} C{marker}")
        previous[sensor_id] = temp_c

    time.sleep(1)
