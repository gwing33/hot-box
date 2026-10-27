import binascii

import ds18x20
import machine
import onewire

# BoxHardware is a single device (one Pico 2 W) monitoring BOTH sides of a
# wall at once. Each side gets its OWN OneWire bus/GPIO pin rather than
# merging all 20 sensors onto one bus:
#   - each side's wiring only ever has to reach its own junction box, never
#     cross through the wall to join the other side's chain
#   - a sensor wired to the wrong side's bus shows up immediately as a
#     mismatch (see checkWiring()) instead of needing to trace wires
#   - keeps each bus's sensor count/pull-up sizing independent
# See README.md's "Electrical wiring" section for the full diagram.
# NOTE: inside is wired to GP27 and outside to GP26 on this physical unit -
# flipped from the "obvious" GP26/GP27 ordering purely because that's how it
# ended up wired during setup. The pin numbers themselves carry no meaning
# (26/27 are electrically identical as OneWire buses), so the code just
# matches the physical wiring rather than the other way around.
SIDE_PINS = {
    "inside": 27,
    "outside": 26,
}

# Sensor Mapping - Grouped by Device (physical BoxHardware unit), then by
# side, then by grid position. Each side is a 3x3 grid (6" spacing) named
# b<row>-<col> plus one "ambient" sensor off the grid - 10 sensors a side,
# 20 total per box.
box_devices = {
    "box1": {
        "inside": {  # grid reused from the old "first_prototype" unit
            "b1-1": "28feb3230d000096",
            "b1-2": "28b046240d000002",
            "b1-3": "281c40240d0000bf",
            "b2-1": "28d2b8230d00002d",
            "b2-2": "282c19240d000034",
            "b2-3": "280b0b240d0000f8",
            "b3-1": "285dcb230d0000c0",
            "b3-2": "284e0a240d0000ab",
            "b3-3": "287e30230d0000f9",
            # Old "first_prototype" ambient sensor was retired; its old spare
            # "board" sensor is reused as ambient here instead.
            "ambient": "28f475b80e000076",
        },
        "outside": {  # grid reused from the old "xander" unit
            "b1-1": "2809f0b70e0000cd",
            "b1-2": "2822edb80e000089",
            "b1-3": "28b270b80e000063",
            "b2-1": "285efbb80e00008c",
            "b2-2": "281927b80e000003",
            "b2-3": "28be51b80e00002b",
            "b3-1": "280e10b80e000008",
            "b3-2": "288b06b80e0000e9",
            "b3-3": "284ddfb80e000069",
            # Old "xander" ambient sensor was retired; this is a newly added one.
            "ambient": "28d722b90e0000d2",
        },
    },
}

# Flattened lookup dictionaries, keyed by raw sensor ID (unique per physical
# DS18B20 regardless of which bus it ends up on).
sensor_mapping = {}  # ID -> "<side>-<position>" display name, e.g. "inside-b1-1"
sensor_device_mapping = {}  # ID -> device (box unit) name
sensor_side_mapping = {}  # ID -> configured side ("inside"/"outside")
for device, sides in box_devices.items():
    for side, positions in sides.items():
        for position, sensor_id in positions.items():
            sensor_mapping[sensor_id] = f"{side}-{position}"
            sensor_device_mapping[sensor_id] = device
            sensor_side_mapping[sensor_id] = side

# Init Sensors - one OneWire/DS18X20 bus per side
_buses = {
    side: ds18x20.DS18X20(onewire.OneWire(machine.Pin(pin)))
    for side, pin in SIDE_PINS.items()
}

# Each discovered sensor is kept as a small dict rather than a bare ROM id,
# so we always know which physical bus (side) it was actually found on -
# this is what readTemp()/convertTemp() use to talk to the right bus, and
# what checkWiring() compares against sensor_side_mapping.
sensors = []
for _side, _bus in _buses.items():
    for _raw in _bus.scan():
        sensors.append({"raw": _raw, "found_side": _side})

number_devices = len(sensors)
print("Number of sensors: ", number_devices)
for _side, _pin in SIDE_PINS.items():
    _count = sum(1 for s in sensors if s["found_side"] == _side)
    print(f"  {_side} (GP{_pin}): {_count} sensor(s)")


def getSensorId(sensor):
    return binascii.hexlify(sensor["raw"]).decode("ascii")


def getSensorName(sensor):
    id = getSensorId(sensor)
    if id in sensor_mapping:
        return sensor_mapping[id]
    else:
        print("Sensor Not Mapped", id, "on", sensor["found_side"])
        return f'{sensor["found_side"]}-{id}'


def getDeviceName(sensor):
    id = getSensorId(sensor)
    if id in sensor_device_mapping:
        return sensor_device_mapping[id]
    else:
        return "unknown"


def getSensorSide(sensor):
    """The side ("inside"/"outside") this sensor was physically found wired
    to, from the bus it was scanned on - independent of sensor_mapping, so
    this works even for a not-yet-identified sensor."""
    return sensor["found_side"]


def getBoxDeviceName():
    """Best-effort single device name for this physical box, inferred from
    whichever sensors are currently wired up (see "Adding a new device" in
    README.md). Used by the WiFi setup portal so you can tell which unit
    you're configuring.

    Returns "unmapped" if none of the connected sensors match a known
    device, or a "/"-joined list if sensors from more than one device are
    seen at once (shouldn't normally happen).
    """
    names = set()
    for sensor in sensors:
        name = getDeviceName(sensor)
        if name != "unknown":
            names.add(name)
    if not names:
        return "unmapped"
    return "/".join(sorted(names))


def getSensors():
    return sensors


def getAllSensorNames():
    return list(map(getSensorName, sensors))


def convertTemp():
    """Trigger a temperature conversion on every side's bus."""
    for bus in _buses.values():
        bus.convert_temp()


def readTemp(sensor):
    return _buses[sensor["found_side"]].read_temp(sensor["raw"])


def checkWiring():
    """Returns a list of (sensor_id, configured_side, found_side) for any
    MAPPED sensor whose configured side (per box_devices) doesn't match the
    side it was actually found wired to this boot - catches an
    inside/outside bus swap at install/reset time. Empty list means
    everything mapped matches where it was found (unmapped sensors are
    skipped - nothing to compare against yet)."""
    mismatches = []
    for sensor in sensors:
        id = getSensorId(sensor)
        configured_side = sensor_side_mapping.get(id)
        if configured_side and configured_side != sensor["found_side"]:
            mismatches.append((id, configured_side, sensor["found_side"]))
    return mismatches
