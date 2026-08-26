import json
import os

_FILE = "config.json"

SLEEP_MS = 300_000  # 5 minutes — must match main.py


def load():
    """Return saved config dict, or None if not found/corrupt."""
    try:
        with open(_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None


def save(cfg):
    """Persist config dict to flash."""
    try:
        with open(_FILE, "w") as f:
            json.dump(cfg, f)
        return True
    except Exception as e:
        print(f"config: save failed: {e}")
        return False


def clear():
    """Delete saved config (forces portal on next boot)."""
    try:
        os.remove(_FILE)
    except Exception:
        pass


def build(wifi_ssid, wifi_password, api_token, project, indefinite, duration_hours):
    """
    Build a fresh config dict.
    wakes_remaining is pre-calculated from duration and sleep interval.

    api_token/project (both may be None) drive Nopal Vault sync (see
    vault.py): a None api_token disables it entirely; a None project means
    the human's Personal space. vault_analysis_folder_id/vault_run_name
    start unset — vault.ensure_run() fills them in once (per test), and
    every wake after that just reuses them.
    """
    if indefinite:
        wakes_remaining = -1  # sentinel: run forever
    else:
        ms_per_wake = SLEEP_MS + 2000  # rough active time per cycle
        wakes_remaining = max(1, int(duration_hours * 3600 * 1000 / ms_per_wake))
    return {
        "wifi_ssid": wifi_ssid,
        "wifi_password": wifi_password,
        "api_token": api_token,
        "project": project,
        "vault_analysis_folder_id": None,
        "vault_run_name": None,
        "indefinite": indefinite,
        "duration_hours": duration_hours,
        "wakes_remaining": wakes_remaining,
    }
