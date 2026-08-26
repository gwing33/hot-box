# Hardware

This project contains the source code for the hardware side of the project.

### Requirements:
- Raspberry Pi Pico W2
- DS18B20 Temp Sensors

## Hardware Setup
[Download](https://www.raspberrypi.com/documentation/microcontrollers/micropython.html) the UF2 file. While in BOOTSEL mode, copy the file onto the Pi.

Using Thonny or VSCode with the Raspberry Pi extension, connect and run the `blink.py` file.

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