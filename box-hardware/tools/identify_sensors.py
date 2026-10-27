"""
Sensor identification helper for setting up a NEW BoxHardware unit (or
re-checking an existing one). Figures out which physical DS18B20 sensor is
which, on EACH side's bus, so you can build/update its entry in
`box_devices` (sensors.py) without guessing.

Run this directly on the device — via Thonny's Run button, or:
    mpremote connect <port> run tools/identify_sensors.py
(Ctrl-C in Thonny, or unplug/re-run, to stop — it loops forever.)

Workflow:
  1. Wire up one side's 10 DS18B20 sensors (9-sensor grid + ambient) to its
     bus pin, and the other side's 10 to its bus pin (GP26 = inside,
     GP27 = outside — same pins sensors.py uses; see SIDE_PINS below).
  2. Run it. Every ~1.5s it reprints every sensor it can see on BOTH buses,
     grouped by side: its unique 64-bit ID and current temperature. A
     sensor whose reading jumped since the last print gets a
     "<-- warming up" marker.
  3. One at a time, pinch/hold a single physical sensor between two fingers
     for a few seconds and watch which ID (and which side's group) gets the
     marker — that confirms both which physical sensor it is AND that it's
     wired to the side you intended. Write down `side -> position -> id`
     (e.g. inside/b1-1, inside/b1-2, ..., inside/ambient, outside/b1-1,
     ...) as you go. Let it cool back down between sensors so the next one
     is unambiguous.
  4. Once every sensor is identified, add a new entry to `box_devices` in
     sensors.py:

         "your-box-name": {
             "inside": {
                 "b1-1": "<id>",
                 ...
                 "ambient": "<id>",
             },
             "outside": {
                 "b1-1": "<id>",
                 ...
                 "ambient": "<id>",
             },
         },

     `your-box-name` is what shows up as `device_name` in every log line,
     local CSV row, MQTT topic, and Nopal Vault run this box produces from
     then on (see getDeviceName() in sensors.py) — pick something short and
     unique across your fleet (e.g. "box1", not "box" or "test"). It is NOT
     set via the WiFi portal; it's inferred purely from which sensor IDs
     this device has, so it MUST be added here before deploying.
  5. Push the updated sensors.py to the device (see hardware/README.md)
     and you're done — getSensors()/getDeviceName()/getSensorName()/
     getSensorSide() will now recognize this device's sensors
     automatically, and checkWiring() will flag it if a sensor ever ends up
     on the wrong side's bus later.
"""

import binascii
import time

import ds18x20
import machine
import onewire

SIDE_PINS = {
    "inside": 26,
    "outside": 27,
}

buses = {side: ds18x20.DS18X20(onewire.OneWire(machine.Pin(pin))) for side, pin in SIDE_PINS.items()}

print("Scanning for DS18B20 sensors on:")
for side, pin in SIDE_PINS.items():
    print(f"  {side}: GP{pin}")
print("Pinch one sensor at a time and watch for '<-- warming up'.")
print("Ctrl-C to stop.\n")

previous = {}

while True:
    any_found = False
    print("-" * 52)
    for side, bus in buses.items():
        devices = bus.scan()
        if not devices:
            print(f"{side} (GP{SIDE_PINS[side]}): no sensors found — check wiring.")
            continue
        any_found = True

        bus.convert_temp()
        time.sleep_ms(750)

        print(f"{side} (GP{SIDE_PINS[side]}):")
        for device in devices:
            sensor_id = binascii.hexlify(device).decode("ascii")
            temp_c = bus.read_temp(device)
            prev_temp = previous.get(sensor_id, temp_c)
            delta = temp_c - prev_temp
            marker = "  <-- warming up" if delta > 0.25 else ""
            print(f"  {sensor_id}  {temp_c:6.3f} C{marker}")
            previous[sensor_id] = temp_c

    if not any_found:
        time.sleep(2)
        continue

    time.sleep(1)
