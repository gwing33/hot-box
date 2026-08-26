# Hardware

This project contains the source code for the hardware side of the project.

### Requirements:
- Raspberry Pi Pico W2
- DS18B20 Temp Sensors

## Hardware Setup

[Download](https://www.raspberrypi.com/documentation/microcontrollers/micropython.html) the UF2 file. While in BOOTSEL mode, copy the file onto the Pi.

Using Thonny or VSCode with the Raspberry Pi extension, connect and copy every file in
this directory (except `*.example`, `pico_sdk_import.cmake`, and `tools/`) onto the
device, including the `lib/` folder. `main.py` auto-runs on boot — there's no separate
file to launch.

Before deploying, copy `secrets.py.example` to `secrets.py` and fill in your WiFi/MQTT
credentials (`secrets.py` is gitignored — never commit real credentials). This is only
used as a fallback/for MQTT; WiFi itself is normally configured per-test through the
captive portal below, and the Nopal API token/project are entered there too, not baked
into `secrets.py`.

## Adding a new device (naming sensors)

Each physical HotBox unit's set of DS18B20 sensors is a hardcoded entry in
`sensor_devices` (`sensors.py`) — a `device_name -> {position: sensor_id}` mapping.
There's no auto-discovery at runtime: a sensor whose ID isn't in this dict shows up in
logs/CSVs as its raw ID with a "Sensor Not Mapped" warning, and `device_name` is inferred
entirely from which sensors are wired up (never set via the portal), so **this has to be
done once before deploying a new unit**:

1. Wire up all of the device's DS18B20 sensors to GP26.
2. Run `tools/identify_sensors.py` on the device (Thonny's Run button, or
   `mpremote connect <port> run tools/identify_sensors.py`). It loops, printing every
   connected sensor's unique ID and live temperature.
3. One at a time, pinch/hold a single sensor and watch which ID's reading jumps (flagged
   with `<-- warming up`) — that tells you which physical sensor is which. Let it cool
   between sensors to keep it unambiguous. Write down `id -> position` (e.g. `b1-1`,
   `b1-2`, `b1-3`, `b2-1`, ..., `ambient`) as you go.
4. Add a new entry to `sensor_devices` in `sensors.py` with a short, unique device name
   (e.g. `"g3"`) and the position->id mapping you just built.
5. Push the updated `sensors.py` to the device.

That device name is what appears as `device_name` in every log line, local CSV row, MQTT
topic, and Nopal Vault run this box produces from then on — see `getDeviceName()` in
`sensors.py`.

## Configuration (WiFi captive portal)

On first boot (or whenever saved WiFi credentials stop working), the box starts its own
AP named `HotBox-Setup`. Connect to it with your phone/laptop and a setup page opens
automatically (or visit `http://192.168.4.1`). It asks for:

- **WiFi network / password** — what the box joins for the rest of the test.
- **Nopal API Token** (optional) — a sync-scoped token (Profile page → Sync Tokens on
  nopal.build) letting the box push readings straight into your Vault. Leave blank to
  skip Nopal entirely — the box still logs locally and publishes over MQTT either way.
- **Nopal Project** (optional) — a project name to sync into (e.g. `sunny`). Leave blank
  to use your Personal space.
- **Test duration** — indefinite, or a fixed number of hours.

If an API token is set, the box ensures a `hot-box-data` sync-api analysis exists (inside
the chosen project's, or Personal's, `syncs/` folder in the Vault — created automatically
with the right column schema if it doesn't exist yet) and starts a new run for the test.
The run's `<run>.md` is seeded with the device name and the full list of sensors detected
on that first wake (id + position name), so it's identifiable later without cross-referencing
`sensors.py`. Every ~5-minute wake appends that cycle's sensor readings as rows to
`syncs/hot-box-data/<run>.csv`, alongside the box's own local CSV and its existing MQTT
publish. See `vault.py`.

**Note:** this run description is deliberately plain ASCII — the firmware's frozen
`urequests` module mishandles multi-byte UTF-8 in a POST body (reproducibly turns the
request into a server-side 500), so avoid em dashes, curly quotes, `°`, etc. if you touch
`vault.py`.

## Developer tools (`tools/`)

Not deployed to the device — run these from your machine against a device connected over
USB (requires `pip install mpremote`, and the device must not be open in Thonny/another
serial client at the same time):

- **`reset_device.py`** — backs up `debug.log`/`temperature_data.csv` into a timestamped
  folder under `hot-box/tmp/`, then deletes them plus `config.json` from the device and
  force-resets it, so it boots straight back into the portal instead of waiting out its
  current deep-sleep countdown. Useful between test runs.
  `python3 tools/reset_device.py [--keep-data] [--no-reset] [--port ...]`
- **`identify_sensors.py`** — see "Adding a new device" above. Run *on* the device, not
  from your machine.

## Known limitations

- **Timestamps default to 2021-01-01** unless something sets the RTC — nothing in the
  current code calls NTP or otherwise sets real time, so `debug.log`/CSV timestamps are
  only meaningful if Thonny happened to sync the clock on connect (it sometimes does).
  Treat log timestamps as relative/sequential, not absolute, unless this is fixed.
- **Safe mode (bridging GP15 to GND to force a drop to REPL) is currently broken** — it
  causes a fast crash-reset loop instead of idling at REPL. Don't rely on it; use a full
  power cycle + `tools/reset_device.py` instead if you need to recover a device stuck in
  the portal.
- **The captive portal (AP mode) blocks `mpremote`/serial tooling** — while the box is
  showing the `HotBox-Setup` AP, it won't respond to `mpremote` connection attempts at
  all. This is expected; it'll be reachable again once WiFi is configured and it's back
  in its normal wake/sleep loop.
