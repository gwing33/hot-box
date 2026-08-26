"""
Minimal Nopal Vault client for pushing HotBox sensor readings into a
`sync-api` ANALYSIS (see nopal's vault skill's "Sync types" section, and
`nopal_core::sync_api` for the same design on the CLI side).

Unlike the CLI/GUI, this device never walks the vault tree itself —
`/api/vault/folders/:folderId/children` (what the CLI uses, several calls
deep) only accepts a FULL bearer token, never the long-lived, revocable,
sync-scoped token a device like this should hold. Instead this calls the
single `POST /api/vault/sync-api/ensure` primitive once per test (it
resolves/creates the Syncs folder and the analysis server-side and hands
back a folder id), then every wake after that is just one more POST to
append that wake's readings as rows.

Every network call here is best-effort: a failure logs and returns without
raising, so a Nopal outage or a bad token never stops the box from taking
readings, writing its own local CSV, or publishing over MQTT.
"""

try:
    from secrets import NOPAL_HOST
except ImportError:
    NOPAL_HOST = "https://nopal.build"

# The analysis's own name inside Syncs — fixed, since a single HotBox
# project only ever needs one (any number of test RUNS live inside it).
ANALYSIS_NAME = "hot-box-data"

# Mirrors the local CSV's own header (see main.py's CSV_FILENAME) with
# plain identifier column names.
SCHEMA = {
    "columns": [
        {"name": "timestamp", "type": "timestamp"},
        {"name": "device_name", "type": "string"},
        {"name": "sensor_id", "type": "string"},
        {"name": "sensor_name", "type": "string"},
        {"name": "temperature_c", "type": "number"},
    ]
}


def _post(path, token, body):
    """POST JSON with a bearer token, raising on any non-2xx response.
    Every call this module makes is a POST — see the module doc for why a
    device never needs GET/PUT (the `/ensure` endpoint does all reading)."""
    import urequests

    url = f"{NOPAL_HOST}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    resp = urequests.post(url, json=body, headers=headers)
    try:
        if resp.status_code >= 400:
            raise Exception(f"POST {path} -> {resp.status_code}: {resp.text}")
        return resp.json() if resp.text else {}
    finally:
        resp.close()


def _run_description(readings):
    """
    Markdown body for the run's `.md` file: which HotBox unit this test is
    running on and every sensor it saw on its first wake (id + position
    name), so anyone opening the run later knows what produced the data
    without cross-referencing sensors.py.

    ASCII-only, deliberately: the frozen `urequests` module on this
    firmware mishandles multi-byte UTF-8 (confirmed: an em dash/degree
    sign in this body reproducibly turns the run-creation POST into a
    500 from the server, while the identical ASCII-only payload succeeds)
    — so no em dashes, degree signs, or other non-ASCII characters here.
    """
    device_name = readings[0][1] if readings else "unknown"
    lines = [f"**Device:** {device_name}", "", "**Sensors:**"]
    for _, _, sensor_id, sensor_name, temp_c in readings:
        lines.append(f"- `{sensor_name}` ({sensor_id}) - {temp_c} C at first wake")
    return device_name, "\n".join(lines)


def ensure_run(cfg, readings, rtc):
    """
    One-time (per test/configuration) setup: ensures the `hot-box-data`
    analysis exists (creating it, with our schema, if not) and creates a
    fresh run for this test. `readings` (this wake's sensor readings, same
    shape main.py builds for its local CSV) is used to fill in the run's
    title/description with the device name and full sensor list. Returns
    an UPDATED config dict (with `vault_analysis_folder_id`/`vault_run_name`
    filled in) on success, or None on failure — the caller should leave the
    existing config as-is and just retry on the next wake.
    """
    from log import log

    token = cfg.get("api_token")
    if not token:
        return None

    try:
        ensure_resp = _post(
            "/api/vault/sync-api/ensure",
            token,
            {"project": cfg.get("project"), "name": ANALYSIS_NAME, "schema": SCHEMA},
        )
        folder_id = ensure_resp["folder"]["_id"]

        device_name, body = _run_description(readings)
        run_resp = _post(
            f"/api/vault/sync-api/{folder_id}/runs",
            token,
            {"prefix": "run", "title": f"{device_name} run", "body": body},
        )
        run_name = run_resp["run"]["name"]

        updated = dict(cfg)
        updated["vault_analysis_folder_id"] = folder_id
        updated["vault_run_name"] = run_name
        log(f"Vault: run '{run_name}' ready ({ANALYSIS_NAME})", rtc)
        return updated
    except Exception as e:
        log(f"Vault: setup failed: {type(e).__name__}: {e}", rtc)
        return None


def send_readings(cfg, readings, rtc):
    """
    Appends this wake's sensor readings as rows to the cached run.
    `readings`: list of (timestamp, device_name, sensor_id, sensor_name,
    temperature_c) — same shape main.py already builds for its local CSV.
    """
    from log import log

    token = cfg.get("api_token")
    folder_id = cfg.get("vault_analysis_folder_id")
    run_name = cfg.get("vault_run_name")
    if not (token and folder_id and run_name):
        return False

    rows = [
        {
            "timestamp": ts,
            "device_name": device_name,
            "sensor_id": sensor_id,
            "sensor_name": sensor_name,
            "temperature_c": temp_c,
        }
        for ts, device_name, sensor_id, sensor_name, temp_c in readings
    ]

    try:
        _post(
            f"/api/vault/sync-api/{folder_id}/runs/{run_name}/rows",
            token,
            {"rows": rows},
        )
        log(f"Vault: synced {len(rows)} reading(s)", rtc)
        return True
    except Exception as e:
        log(f"Vault: sync failed: {type(e).__name__}: {e}", rtc)
        return False
