"""South Wall Test monitoring.

Parses the raw DS18B20 sensor logs pulled directly off the two HotBox units
(xander, g2) for the "south wall test" run --
../tmp/south-wall-test/{device}-device-dump/temperature_data.csv -- cleans
up the run's known issues, and produces per-device sensor plots plus tidy
cleaned CSVs.

Known issues this script accounts for (see conversation write-up / nopal
sync-gap investigation for the full analysis):

  1. Un-synced-clock placeholder rows: whenever NTP sync failed on a given
     wake, that cycle's rows are timestamped 2021-01-01T00:00:xx instead of
     real calendar time. Real readings, garbage clock -- dropped rather
     than guessed at (unlike the older docx-based tests in
     hotbox_monitoring.py, this run's clock synced successfully on almost
     every wake, so there's no need for elapsed-time anchoring here).
  2. Both units' batteries died in the field around 2026-09-06 (a
     100-108h gap in the raw log -- nothing was recorded, not zero
     readings). They only came back to life today when plugged into USB
     for this data pull, producing 1-2 extra cycles of "field" data that's
     actually just the device sitting on a desk powered over USB -- not
     representative of test conditions. This script truncates each
     device's series at the start of the first >2h gap, which drops both
     the dead-battery void and that trailing USB-powered blip in one step.
  3. nopal.build's synced copy of this run (../tmp/south-wall-test/run-8.csv,
     run-9.csv) is INCOMPLETE -- a nopal-side hard database limit silently
     stopped persisting rows starting ~2026-09-03, with no client-visible
     error (the device's own debug.log shows every sync as successful).
     This script deliberately uses the device-local CSVs as source of
     truth instead of the nopal export.

Run with:
    uv run south_wall_monitoring.py       # from hot-box/termodyn
or:
    python3 south_wall_monitoring.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import numpy as np

from hotbox_monitoring import GRID_SENSOR_COLS, SENSOR_ORDER

# Step used when interpolating both devices onto a common time grid for
# delta-T (each device wakes on its own independent ~5min schedule, drifting
# up to a couple minutes out of phase with the other -- a hard match
# tolerance like hotbox_monitoring.py's ASOF_TOLERANCE_S drops most rows
# here, so we interpolate instead).
DELTA_GRID_STEP_S = 60.0

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "tmp" / "south-wall-test"
OUTPUT_DIR = DATA_DIR  # keep outputs alongside the raw pull, not termodyn/output

DEVICES = ["xander", "g2"]

# Physical placement, confirmed by the user: g2's sensor grid sits on the
# OUTSIDE wall face, xander's sits directly opposite on the INSIDE face.
DEVICE_ROLE = {"xander": "interior", "g2": "exterior"}

# A gap bigger than this is a real outage (dead battery), not a normal
# one-off missed wake. The largest "normal" gap seen across both devices
# was ~0.17h (a single missed 5-minute cycle); the real outage was 100h+.
DEAD_BATTERY_GAP_S = 3600 * 2  # 2 hours


def load_device_csv(device: str) -> pd.DataFrame:
    """Load one device's raw local CSV and clean it: parse types, drop
    un-synced-clock placeholder rows, dedupe, and truncate at the first
    real outage (dead battery / post-mortem USB revival)."""
    path = DATA_DIR / f"{device}-device-dump" / "temperature_data.csv"
    raw = pd.read_csv(path, dtype=str)

    df = raw.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["temperature_c"] = pd.to_numeric(df["temperature_c"], errors="coerce")
    df = df.dropna(subset=["timestamp", "temperature_c", "sensor_name", "sensor_id"])

    # Un-synced-clock placeholder rows all fall on the Pico's default RTC
    # epoch (2021-01-01) -- real reading, garbage clock. Drop them.
    df = df[df["timestamp"] >= pd.Timestamp("2022-01-01")]

    df = df.drop_duplicates(subset=["timestamp", "sensor_id"])
    df = df.sort_values("timestamp")

    unique_ts = df["timestamp"].drop_duplicates().sort_values().reset_index(drop=True)
    gaps_s = unique_ts.diff().dt.total_seconds()
    outage_idx = gaps_s[gaps_s > DEAD_BATTERY_GAP_S].index
    if len(outage_idx):
        cutoff = unique_ts.iloc[outage_idx[0] - 1]
        df = df[df["timestamp"] <= cutoff]

    return df.reset_index(drop=True)


def build_wide_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot one device's long data into a wide frame: index=timestamp,
    columns=sensor_name, values=temperature_c."""
    wide = df.pivot_table(
        index="timestamp", columns="sensor_name", values="temperature_c", aggfunc="mean"
    ).sort_index()
    cols = [c for c in SENSOR_ORDER if c in wide.columns]
    return wide[cols]


def plot_sensor_grid(wide: pd.DataFrame, device: str, output_dir: Path) -> None:
    """One subplot per sensor -- the literal 'each sensor over the
    duration' view."""
    cols = list(wide.columns)
    n = len(cols)
    ncols = 3
    nrows = -(-n // ncols)  # ceil division
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.2 * ncols, 3 * nrows), sharex=True)
    axes = axes.flatten()

    for ax, col in zip(axes, cols):
        color = "tab:red" if col == "ambient" else "tab:blue"
        ax.plot(wide.index, wide[col], linewidth=1, color=color)
        ax.set_title(col)
        ax.set_ylabel("C")
        ax.grid(alpha=0.3)
        ax.tick_params(axis="x", rotation=45)

    for ax in axes[n:]:
        ax.axis("off")

    fig.suptitle(f"South Wall Test - {device} - per-sensor temperature")
    fig.tight_layout()
    fig.savefig(output_dir / f"{device}_sensors_grid.png", dpi=150)
    plt.close(fig)


def plot_overlay(wide: pd.DataFrame, device: str, output_dir: Path) -> None:
    """All sensors on one axis, for a quick at-a-glance comparison."""
    fig, ax = plt.subplots(figsize=(11, 5))
    for col in wide.columns:
        style = (
            dict(linewidth=2, linestyle="--", color="black")
            if col == "ambient"
            else dict(linewidth=1)
        )
        ax.plot(wide.index, wide[col], label=col, **style)

    ax.set_xlabel("Time")
    ax.set_ylabel("Temperature (C)")
    ax.set_title(f"South Wall Test - {device} - all sensors")
    ax.legend(ncol=2, fontsize=8)
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / f"{device}_sensors_overlay.png", dpi=150)
    plt.close(fig)


def plot_wall_comparison(wide_by_device: dict[str, pd.DataFrame], output_dir: Path) -> None:
    """One figure, 4 lines: ambient + grid_mean (average of the 9 bx-x wall
    sensors) for each device, i.e. interior vs exterior wall-face temp and
    interior vs exterior ambient. High-resolution (large figure, 300 dpi)
    since this is the headline comparison plot for the run."""
    fig, ax = plt.subplots(figsize=(16, 8))

    styles = {
        ("exterior", "ambient"): dict(color="tab:red", linestyle="--", linewidth=1.5),
        ("exterior", "grid_mean"): dict(color="tab:red", linestyle="-", linewidth=2),
        ("interior", "ambient"): dict(color="tab:blue", linestyle="--", linewidth=1.5),
        ("interior", "grid_mean"): dict(color="tab:blue", linestyle="-", linewidth=2),
    }

    for device, wide in wide_by_device.items():
        role = DEVICE_ROLE[device]
        grid_cols = [c for c in GRID_SENSOR_COLS if c in wide.columns]
        grid_mean = wide[grid_cols].mean(axis=1)

        ax.plot(
            wide.index,
            wide["ambient"],
            label=f"{device} ambient ({role})",
            **styles[(role, "ambient")],
        )
        ax.plot(
            grid_mean.index,
            grid_mean,
            label=f"{device} wall grid avg ({role})",
            **styles[(role, "grid_mean")],
        )

    ax.set_xlabel("Time")
    ax.set_ylabel("Temperature (C)")
    ax.set_title("South Wall Test - interior vs exterior - ambient and wall-face averages")
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "wall_comparison.png", dpi=300)
    plt.close(fig)


def compute_wall_delta(wide_by_device: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Time-align xander (interior) and g2 (exterior) by linearly
    interpolating both onto a common uniform time grid (DELTA_GRID_STEP_S),
    restricted to their overlapping coverage window, then compute
    exterior-minus-interior delta for both ambient and the wall-face grid
    average."""
    interior = wide_by_device["xander"].copy()
    exterior = wide_by_device["g2"].copy()

    interior["grid_mean"] = interior[[c for c in GRID_SENSOR_COLS if c in interior.columns]].mean(axis=1)
    exterior["grid_mean"] = exterior[[c for c in GRID_SENSOR_COLS if c in exterior.columns]].mean(axis=1)

    t0 = min(interior.index.min(), exterior.index.min())
    interior_s = (interior.index - t0).total_seconds().to_numpy()
    exterior_s = (exterior.index - t0).total_seconds().to_numpy()

    start_s = max(interior_s.min(), exterior_s.min())
    end_s = min(interior_s.max(), exterior_s.max())
    grid = np.arange(start_s, end_s, DELTA_GRID_STEP_S)

    interior_ambient = np.interp(grid, interior_s, interior["ambient"].to_numpy())
    interior_grid_mean = np.interp(grid, interior_s, interior["grid_mean"].to_numpy())
    exterior_ambient = np.interp(grid, exterior_s, exterior["ambient"].to_numpy())
    exterior_grid_mean = np.interp(grid, exterior_s, exterior["grid_mean"].to_numpy())

    delta = pd.DataFrame(
        {
            "timestamp": t0 + pd.to_timedelta(grid, unit="s"),
            "ambient_delta": exterior_ambient - interior_ambient,
            "grid_mean_delta": exterior_grid_mean - interior_grid_mean,
        }
    )
    return delta.set_index("timestamp")


def plot_wall_delta(delta: pd.DataFrame, output_dir: Path) -> None:
    """Exterior-minus-interior delta for ambient and wall-face grid
    average, on one high-resolution figure."""
    fig, ax = plt.subplots(figsize=(16, 8))

    ax.plot(
        delta.index,
        delta["ambient_delta"],
        label="ambient delta (g2 exterior - xander interior)",
        color="tab:orange",
        linestyle="--",
        linewidth=1.5,
    )
    ax.plot(
        delta.index,
        delta["grid_mean_delta"],
        label="wall grid avg delta (g2 exterior - xander interior)",
        color="tab:purple",
        linestyle="-",
        linewidth=2,
    )
    ax.axhline(0, color="black", linewidth=1, alpha=0.5)

    ax.set_xlabel("Time")
    ax.set_ylabel("Delta T (C)")
    ax.set_title("South Wall Test - exterior minus interior delta (ambient vs wall grid avg)")
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "wall_delta_t.png", dpi=300)
    plt.close(fig)


def main() -> None:
    cleaned_dir = OUTPUT_DIR / "cleaned"
    plots_dir = OUTPUT_DIR / "plots"
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    wide_by_device: dict[str, pd.DataFrame] = {}
    for device in DEVICES:
        df = load_device_csv(device)
        df.to_csv(cleaned_dir / f"{device}_cleaned.csv", index=False)

        wide = build_wide_frame(df)
        wide_by_device[device] = wide
        plot_sensor_grid(wide, device, plots_dir)
        plot_overlay(wide, device, plots_dir)

        print(
            f"{device}: {len(df):5d} rows, "
            f"{df['timestamp'].min()} -> {df['timestamp'].max()}  "
            f"-> cleaned/{device}_cleaned.csv, "
            f"plots/{device}_sensors_grid.png, plots/{device}_sensors_overlay.png"
        )

    plot_wall_comparison(wide_by_device, plots_dir)
    print("-> plots/wall_comparison.png")

    delta = compute_wall_delta(wide_by_device)
    delta.to_csv(cleaned_dir / "wall_delta_t.csv")
    plot_wall_delta(delta, plots_dir)
    print("-> plots/wall_delta_t.png, cleaned/wall_delta_t.csv")


if __name__ == "__main__":
    main()
