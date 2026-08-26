"""Hot Box monitoring data pipeline.

Parses the raw DS18B20 sensor logs in ../data/Test */*.csv, cleans up the
known data-quality issues (see below), and produces:

  - output/combined_readings_long.csv   tidy long-format table of every
                                         reading across all tests/devices
  - output/data_quality_report.txt      human-readable summary of what was
                                         dropped/corrected and why
  - output/test{N}_<device>_sensors.png per-device sensor grid plot
  - output/test{N}_interior_vs_exterior_ambient.png
  - output/test{N}_delta_t.png          exterior-minus-interior delta per
                                         matched sensor position
  - output/test{N}_heat_flux.png        estimated conductive heat flux
                                         (W/m2) per sensor position
  - output/all_tests_heat_flux_comparison.png
  - output/heat_flux_estimates.csv      heat flux numbers behind the plots
  - output/test{N}_<device>_grid_aggregate.png
                                         9-point 6in grid collapsed into one
                                         area-representative series
  - output/test{N}_thermal_inertia.png  exterior vs interior grid_mean, RC
                                         time-constant fit, decrement factor
                                         and time lag (with reliability flags)
  - output/all_tests_thermal_inertia_summary.png
  - output/grid_aggregate.csv, output/thermal_inertia_summary.csv

Known data-quality issues this script accounts for (see hot-box/data review):

  1. Timestamps use the Pico's un-synced default RTC epoch
     (2021-01-01T00:00:00) rather than real calendar time, because NTP sync
     fails in the field. We treat the *elapsed* time within a file as
     trustworthy and anchor it to the docx-reported test start time only as
     an approximation (clearly labeled as such).
  2. Every file caps out at ~14.5-15h of logged elapsed time despite tests
     running for 1.3-4.5 days per the docx notes -- almost certainly a
     battery/power limit, not a full multi-day capture. Analysis here is
     necessarily scoped to whatever window each device happened to capture.
  3. At least one file (Test 4 Xander) contains a mid-file RTC reset (a
     quick reboot -- temperatures are continuous across the boundary, only
     the clock jumps back to the epoch). We detect these and stitch the
     segments into one continuous elapsed-time axis.
  4. Test 3's Kyle (exterior) file ends with a truncated/corrupted final
     row. We drop unparseable rows rather than fail.
  5. Device role (interior/exterior) is not reliably encoded in filenames:
     Test 1 has interior only; Test 2 has kyle=interior/xander=exterior;
     Test 3 has kyle=exterior/xander=interior (flipped, and "exterior" is
     even misspelled "Exerior" in the filename); Test 4's filenames carry no
     role label at all. Roles for Test 4 are *inferred* from the ambient
     sensor's swing (the wide-swinging sensor is exterior) and are flagged
     as such everywhere they're used.

Run with:
    uv run hotbox_monitoring.py          # from hot-box/termodyn
or:
    python3 hotbox_monitoring.py
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = SCRIPT_DIR.parent / "data"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "output"

SENSOR_ORDER = [
    "ambient",
    "b1-1",
    "b1-2",
    "b1-3",
    "b2-1",
    "b2-2",
    "b2-3",
    "b3-1",
    "b3-2",
    "b3-3",
]

# The 9 non-ambient sensors sit on a uniform 6in x 6in grid on the wall face
# (a 12in x 12in instrumented patch). Averaging them gives a single
# area-representative reading for that face instead of 9 point samples.
GRID_SENSOR_COLS = [c for c in SENSOR_ORDER if c != "ambient"]
GRID_SPACING_IN = 6.0

# Sampling interval used when resampling the two (interior/exterior) grid
# averages onto a common uniform time axis for lag/inertia analysis.
INERTIA_RESAMPLE_S = 60.0

# One sample tick's worth of seconds, used to keep stitched segments from
# overlapping at the exact same elapsed second when a reset is detected.
NOMINAL_SAMPLE_INTERVAL_S = 11.0

# Tolerance used when time-aligning interior/exterior devices that don't
# sample at exactly the same instants.
ASOF_TOLERANCE_S = 30.0

# --- Heat flux assumptions -------------------------------------------------
# Estimated whole-assembly (air-to-air) thermal resistance, R_total, for each
# wall type. These are NOT measured -- the docx notes explicitly flag several
# unknowns (perlite fill, furring insulation, IGU seal condition), so these
# are reference/typical values from ASHRAE Fundamentals-style tables, used to
# convert the measured ambient-to-ambient delta-T into an estimated heat flux.
# See the module docstring / conversation write-up for full derivation and
# citations. Values are R_imperial in hr.ft2.degF/Btu; converted to SI below.
R_IMPERIAL_TO_SI = 0.1761

# Test 1 & 2 wall assembly: exterior air film + 8in CMU (hollow, normal
# weight, no perlite assumed since "unknown") + 1.5in furring air space
# (assumed UNinsulated, since "unknown if insulated") + 1/2in gyp + interior
# air film.
WALL_MASONRY_LAYERS_R_IMPERIAL = {
    "exterior_air_film": 0.17,
    "cmu_8in_hollow": 1.11,
    "furring_air_space_1_5in": 1.01,
    "gyp_0_5in": 0.45,
    "interior_air_film": 0.68,
}

# Test 3 & 4 wall assembly: 1in IGU window, assumed compromised/failed seal.
# Modeled as behaving like a single clear pane (lost insulating gas gap /
# convecting cavity), whole-unit air-to-air R-value from typical NFRC
# single-glazing U-factor (~1.1 Btu/hr.ft2.degF).
WALL_IGU_COMPROMISED_R_IMPERIAL = {
    "whole_unit_air_to_air": 0.91,
}

R_TOTAL_IMPERIAL = {
    1: sum(WALL_MASONRY_LAYERS_R_IMPERIAL.values()),
    2: sum(WALL_MASONRY_LAYERS_R_IMPERIAL.values()),
    3: sum(WALL_IGU_COMPROMISED_R_IMPERIAL.values()),
    4: sum(WALL_IGU_COMPROMISED_R_IMPERIAL.values()),
}

R_TOTAL_SI = {test: r * R_IMPERIAL_TO_SI for test, r in R_TOTAL_IMPERIAL.items()}


@dataclass
class DeviceConfig:
    device: str  # "kyle" | "xander"
    role: str  # "interior" | "exterior"
    filename: str
    role_inferred: bool = False


@dataclass
class TestConfig:
    number: int
    elevation: str
    overhang: str
    wall_assembly: str
    start: datetime
    end: datetime
    notes: str
    devices: list[DeviceConfig] = field(default_factory=list)

    @property
    def folder_name(self) -> str:
        return f"Test {self.number}"


TEST_CONFIGS: list[TestConfig] = [
    TestConfig(
        number=1,
        elevation="West, 2' overhang",
        overhang="2 ft",
        wall_assembly="Exposed 4x8x16 masonry, 1.5in furring, 1/2in gyp",
        start=datetime(2026, 2, 23, 21, 30),
        end=datetime(2026, 2, 28, 9, 40),
        notes="No exterior data collected (faulty power). Foil applied to "
        "exterior wall surface for direct-sun protection.",
        devices=[
            DeviceConfig("kyle", "interior", "1-Kyle-Interior-Test 1.csv"),
        ],
    ),
    TestConfig(
        number=2,
        elevation="South, large overhang, no direct sun",
        overhang="Large",
        wall_assembly="Exposed 4x8x16 masonry, 1.5in furring, 1/2in gyp",
        start=datetime(2026, 2, 28, 14, 21),
        end=datetime(2026, 3, 2, 17, 39),
        notes="Exterior device fell off the wall partway through (time unknown).",
        devices=[
            DeviceConfig("kyle", "interior", "2-Kyle-Interior-Test 2.csv"),
            DeviceConfig("xander", "exterior", "2-Xander-Exterior-Test 2.csv"),
        ],
    ),
    TestConfig(
        number=3,
        elevation="West, 4' overhang",
        overhang="4 ft",
        wall_assembly="1in IGU window, assumed compromised/failed seal (~7yr old)",
        start=datetime(2026, 3, 2, 22, 0),
        end=datetime(2026, 3, 4, 9, 14),
        notes="Received direct sun at 5:28pm. Exterior device covered with "
        "foil to protect from sun.",
        devices=[
            DeviceConfig("kyle", "exterior", "3-Kyle-Exerior-Test 3.csv"),
            DeviceConfig("xander", "interior", "3-Xander-Interior-Test 3.csv"),
        ],
    ),
    TestConfig(
        number=4,
        elevation="West, 4' overhang",
        overhang="4 ft",
        wall_assembly="1in IGU window, assumed compromised/failed seal (~7yr old)",
        start=datetime(2026, 3, 4, 9, 21),
        end=datetime(2026, 3, 5, 20, 16),
        notes="Received direct sun at 5:28pm. Exterior device covered with "
        "foil to protect from sun. NOTE: filenames carry no interior/"
        "exterior label -- roles below are INFERRED from Test 3's pattern "
        "and confirmed by ambient-sensor swing (exterior swings much wider).",
        devices=[
            DeviceConfig("kyle", "exterior", "4-Kyle-Test 4.csv", role_inferred=True),
            DeviceConfig("xander", "interior", "4-Xander-Test 4.csv", role_inferred=True),
        ],
    ),
]


@dataclass
class LoadResult:
    df: pd.DataFrame
    raw_rows: int
    dropped_rows: int
    num_resets: int
    max_elapsed_hours: float


def load_device_csv(path: Path) -> LoadResult:
    """Load one raw sensor CSV, clean it, and compute a stitched,
    monotonically increasing elapsed-seconds column."""
    raw = pd.read_csv(
        path,
        dtype=str,
        on_bad_lines="skip",  # drops the truncated/corrupted trailing row(s)
        engine="python",
    )
    raw_rows = len(raw)

    df = raw.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["temperature_c"] = pd.to_numeric(df["temperature_c"], errors="coerce")
    before = len(df)
    df = df.dropna(subset=["timestamp", "temperature_c", "sensor_name", "sensor_id"])
    dropped_rows = (raw_rows - len(df))

    df = df.sort_index()  # preserve original file order

    elapsed, num_resets = _build_elapsed_seconds(df["timestamp"])
    df["elapsed_s"] = elapsed
    df["elapsed_h"] = df["elapsed_s"] / 3600.0

    max_elapsed_hours = float(df["elapsed_h"].max()) if len(df) else 0.0

    return LoadResult(
        df=df,
        raw_rows=raw_rows,
        dropped_rows=dropped_rows,
        num_resets=num_resets,
        max_elapsed_hours=max_elapsed_hours,
    )


def _build_elapsed_seconds(ts: pd.Series) -> tuple[pd.Series, int]:
    """Turn a raw (possibly reset mid-stream) timestamp column into a
    monotonically increasing elapsed-seconds column, stitching segments
    back-to-back wherever the clock jumps backwards (a reboot / RTC reset).

    This walks rows in their original file order and compares each row only
    to the row immediately before it -- NOT via a value lookup. A reset
    segment restarts counting from the same epoch (2021-01-01T00:00:xx), so
    its timestamp values collide with values already seen in the first
    segment; a dict keyed by timestamp value would silently merge the two
    segments together instead of stitching them end-to-end.
    """
    values = ts.to_numpy()
    n = len(values)
    elapsed = np.empty(n, dtype="float64")
    num_resets = 0

    if n == 0:
        return pd.Series(elapsed, index=ts.index), num_resets

    segment_start = values[0]
    cumulative_offset = 0.0
    prev = values[0]

    for i in range(n):
        t = values[i]
        if t < prev:
            # Clock jumped backwards -> reboot/RTC reset -> new segment,
            # stitched right after where the previous segment left off.
            prev_elapsed = (prev - segment_start) / np.timedelta64(1, "s") + cumulative_offset
            cumulative_offset = prev_elapsed + NOMINAL_SAMPLE_INTERVAL_S
            segment_start = t
            num_resets += 1
        elapsed[i] = (t - segment_start) / np.timedelta64(1, "s") + cumulative_offset
        prev = t

    return pd.Series(elapsed, index=ts.index), num_resets


def load_all_tests(data_dir: Path) -> tuple[pd.DataFrame, list[str]]:
    """Load and clean every configured test/device CSV.

    Returns the combined long-format dataframe plus a list of report lines
    describing what was found/fixed along the way.
    """
    frames = []
    report_lines = []

    for test in TEST_CONFIGS:
        report_lines.append(f"\n=== Test {test.number}: {test.elevation} ===")
        report_lines.append(f"  Wall assembly : {test.wall_assembly}")
        report_lines.append(
            f"  Docx window   : {test.start} -> {test.end} "
            f"({(test.end - test.start).total_seconds() / 3600:.1f}h stated)"
        )
        report_lines.append(f"  Docx notes    : {test.notes}")
        report_lines.append(
            f"  R_total (est) : {R_TOTAL_IMPERIAL[test.number]:.2f} hr.ft2.degF/Btu "
            f"= {R_TOTAL_SI[test.number]:.3f} m2K/W "
            f"(U={1.0 / R_TOTAL_SI[test.number]:.2f} W/m2K)"
        )

        for dev in test.devices:
            path = data_dir / test.folder_name / dev.filename
            if not path.exists():
                report_lines.append(f"  [MISSING] {path}")
                continue

            result = load_device_csv(path)
            df = result.df
            df["test"] = test.number
            df["device"] = dev.device
            df["role"] = dev.role
            df["role_inferred"] = dev.role_inferred
            df["elevation"] = test.elevation
            df["wall_assembly"] = test.wall_assembly
            df["approx_timestamp"] = test.start + pd.to_timedelta(df["elapsed_s"], unit="s")
            frames.append(df)

            coverage_pct = (
                100.0 * result.max_elapsed_hours
                / max((test.end - test.start).total_seconds() / 3600, 1e-9)
            )
            role_note = " (INFERRED)" if dev.role_inferred else ""
            report_lines.append(
                f"  {dev.device:8s} role={dev.role}{role_note:<11s} "
                f"raw_rows={result.raw_rows:6d} dropped={result.dropped_rows:4d} "
                f"resets_detected={result.num_resets} "
                f"logged={result.max_elapsed_hours:5.2f}h "
                f"({coverage_pct:4.1f}% of the {(test.end - test.start).total_seconds() / 3600:.1f}h stated window)"
            )

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return combined, report_lines


def build_wide_frame(df: pd.DataFrame, test: int, device: str) -> pd.DataFrame:
    """Pivot one test/device's long data into a wide frame: index=elapsed_s,
    columns=sensor_name, values=temperature_c."""
    sub = df[(df["test"] == test) & (df["device"] == device)]
    wide = sub.pivot_table(
        index="elapsed_s", columns="sensor_name", values="temperature_c", aggfunc="mean"
    ).sort_index()
    cols = [c for c in SENSOR_ORDER if c in wide.columns]
    return wide[cols]


def compute_grid_aggregate(df: pd.DataFrame, test: int, device: str) -> pd.DataFrame:
    """Collapse the 9-point, 6in-spaced sensor grid on one wall face into a
    single area-representative series: grid_mean (the combined reading) plus
    grid_min/grid_max/grid_std describing how much the 9 points disagree at
    each instant (spatial non-uniformity, e.g. thermal bridging).

    grid_mean(t) = (1/9) * sum(b1-1(t) ... b3-3(t))

    Because the 9 points are laid out on a uniform grid, the plain arithmetic
    mean is already a good estimate of the spatial average temperature over
    the instrumented 12in x 12in patch (each point represents an equal-area
    neighborhood), so no area-weighting is needed.
    """
    wide = build_wide_frame(df, test, device)
    grid_cols = [c for c in GRID_SENSOR_COLS if c in wide.columns]
    if not grid_cols:
        return pd.DataFrame()

    agg = pd.DataFrame(index=wide.index)
    agg["grid_mean"] = wide[grid_cols].mean(axis=1)
    agg["grid_std"] = wide[grid_cols].std(axis=1)
    agg["grid_min"] = wide[grid_cols].min(axis=1)
    agg["grid_max"] = wide[grid_cols].max(axis=1)
    if "ambient" in wide.columns:
        agg["ambient"] = wide["ambient"]

    agg = agg.reset_index().rename(columns={"index": "elapsed_s"})
    agg["elapsed_h"] = agg["elapsed_s"] / 3600.0
    return agg


def compute_delta_t(df: pd.DataFrame, test: int) -> pd.DataFrame | None:
    """For a test with both an interior and exterior device, time-align them
    (nearest match within ASOF_TOLERANCE_S) and compute exterior-minus-
    interior delta per matched sensor position."""
    test_cfg = next(t for t in TEST_CONFIGS if t.number == test)
    roles = {d.role: d.device for d in test_cfg.devices}
    if "interior" not in roles or "exterior" not in roles:
        return None

    interior_wide = build_wide_frame(df, test, roles["interior"]).reset_index()
    exterior_wide = build_wide_frame(df, test, roles["exterior"]).reset_index()

    merged = pd.merge_asof(
        exterior_wide.sort_values("elapsed_s"),
        interior_wide.sort_values("elapsed_s"),
        on="elapsed_s",
        direction="nearest",
        tolerance=ASOF_TOLERANCE_S,
        suffixes=("_ext", "_int"),
    ).dropna(how="any")

    sensor_cols = [c for c in SENSOR_ORDER if f"{c}_ext" in merged.columns and f"{c}_int" in merged.columns]
    delta = pd.DataFrame({"elapsed_s": merged["elapsed_s"]})
    for c in sensor_cols:
        delta[c] = merged[f"{c}_ext"] - merged[f"{c}_int"]
    delta["elapsed_h"] = delta["elapsed_s"] / 3600.0
    return delta


def compute_heat_flux(delta: pd.DataFrame | None, test: int) -> pd.DataFrame | None:
    """Convert a delta-T frame (exterior minus interior, degC) into an
    estimated steady-state conductive heat flux (W/m2) using the whole-
    assembly R_total for that test's wall type.

    q = delta_T / R_total

    Positive q means heat flowing from exterior to interior (a heat GAIN
    for the interior); negative means the interior is losing heat outward.
    This is a 1D steady-state approximation -- see the write-up for caveats
    (it ignores thermal mass / transient storage, which matters most for
    the masonry wall in Tests 1-2).
    """
    if delta is None or delta.empty:
        return None

    r_total = R_TOTAL_SI[test]
    flux = pd.DataFrame({"elapsed_s": delta["elapsed_s"], "elapsed_h": delta["elapsed_h"]})
    sensor_cols = [c for c in delta.columns if c not in ("elapsed_s", "elapsed_h")]
    for c in sensor_cols:
        flux[c] = delta[c] / r_total
    return flux


def _resample_uniform(elapsed_s: np.ndarray, values: np.ndarray, start: float, end: float, step: float) -> tuple[np.ndarray, np.ndarray]:
    """Linearly interpolate an irregular (elapsed_s, values) series onto a
    uniform time grid, needed before cross-correlation / ODE fitting."""
    grid = np.arange(start, end, step)
    interp = np.interp(grid, elapsed_s, values)
    return grid, interp


def _best_lag_hours(
    ext_u: np.ndarray,
    int_u: np.ndarray,
    dt_s: float,
    min_lag_hours: float = -1.0,
    max_lag_hours: float = 8.0,
) -> tuple[float, float]:
    """Find the time shift (hours) that best aligns the interior grid-mean
    series with the exterior grid-mean series, i.e. how far behind the
    exterior signal the interior signal trails.

    Implemented as a bounded, normalized cross-correlation search rather
    than a full FFT correlation: with only ~14h of data covering roughly
    one rise/fall cycle, an unbounded search can lock onto a spurious lag
    at the edges where only a handful of points overlap. Restricting the
    search to a physically plausible window (-1h to +8h) keeps the result
    interpretable: positive lag = interior peaks/troughs after exterior.
    """
    n = len(ext_u)
    step_min = int(round(min_lag_hours * 3600.0 / dt_s))
    step_max = int(round(max_lag_hours * 3600.0 / dt_s))

    best_lag_h = 0.0
    best_score = -np.inf
    for lag_steps in range(step_min, step_max + 1):
        if lag_steps >= 0:
            a = int_u[lag_steps:]
            b = ext_u[: n - lag_steps]
        else:
            a = int_u[: n + lag_steps]
            b = ext_u[-lag_steps:]
        if len(a) < 0.3 * n:
            continue
        a_d = a - a.mean()
        b_d = b - b.mean()
        denom = a_d.std() * b_d.std()
        if denom < 1e-9:
            continue
        score = float(np.mean(a_d * b_d) / denom)
        if score > best_score:
            best_score = score
            best_lag_h = lag_steps * dt_s / 3600.0
    return best_lag_h, best_score


def compute_thermal_inertia(df: pd.DataFrame, test: int) -> dict | None:
    """Characterize the wall assembly's dynamic (thermal-mass) response
    using only the two combined grid-mean series (exterior vs interior) --
    no material-property assumptions required.

    Three metrics, all purely empirical:
      1. decrement_factor: interior swing amplitude / exterior swing
         amplitude over the overlapping window. Smaller = more damping.
      2. time_lag_hours: how many hours the interior grid-mean trails the
         exterior grid-mean (via a bounded cross-correlation search).
      3. tau_hours: the time constant of a first-order RC model fit to the
         exterior-to-interior transfer (see the write-up for the ODE and
         fitting approach). Bigger tau = slower to respond = more inertia.
    """
    test_cfg = next(t for t in TEST_CONFIGS if t.number == test)
    roles = {d.role: d.device for d in test_cfg.devices}
    if "interior" not in roles or "exterior" not in roles:
        return None

    ext_agg = compute_grid_aggregate(df, test, roles["exterior"])
    int_agg = compute_grid_aggregate(df, test, roles["interior"])
    if ext_agg.empty or int_agg.empty:
        return None

    start = max(ext_agg["elapsed_s"].min(), int_agg["elapsed_s"].min())
    end = min(ext_agg["elapsed_s"].max(), int_agg["elapsed_s"].max())
    if end - start < 3600.0:
        return None

    grid, ext_u = _resample_uniform(
        ext_agg["elapsed_s"].to_numpy(), ext_agg["grid_mean"].to_numpy(), start, end, INERTIA_RESAMPLE_S
    )
    _, int_u = _resample_uniform(
        int_agg["elapsed_s"].to_numpy(), int_agg["grid_mean"].to_numpy(), start, end, INERTIA_RESAMPLE_S
    )

    ext_amp = ext_u.max() - ext_u.min()
    int_amp = int_u.max() - int_u.min()
    decrement_factor = float(int_amp / ext_amp) if ext_amp > 1e-6 else float("nan")

    time_lag_hours, lag_score = _best_lag_hours(ext_u, int_u, INERTIA_RESAMPLE_S)

    def simulate(tau_hours: float) -> np.ndarray:
        tau_s = max(tau_hours, 1e-3) * 3600.0
        alpha = min(INERTIA_RESAMPLE_S / tau_s, 1.0)
        pred = np.empty_like(int_u)
        pred[0] = int_u[0]
        for i in range(1, len(int_u)):
            pred[i] = pred[i - 1] + alpha * (ext_u[i - 1] - pred[i - 1])
        return pred

    def loss(tau_hours: float) -> float:
        pred = simulate(tau_hours)
        return float(np.mean((pred - int_u) ** 2))

    tau_bounds = (0.05, 72.0)
    fit = minimize_scalar(loss, bounds=tau_bounds, method="bounded")
    tau_hours = float(fit.x)
    int_pred = simulate(tau_hours)

    int_var = float(np.var(int_u))
    r_squared = float(1.0 - fit.fun / int_var) if int_var > 1e-9 else float("nan")

    # Flag fits that aren't trustworthy: pinned against the search bound
    # (no genuine interior minimum, see write-up) or explaining very little
    # of the interior signal's variance.
    near_bound = tau_hours >= tau_bounds[1] - 1.0 or tau_hours <= tau_bounds[0] + 0.05
    tau_reliable = bool((not near_bound) and r_squared > 0.1)

    lag_min, lag_max = -1.0, 8.0
    lag_step_h = INERTIA_RESAMPLE_S / 3600.0
    lag_reliable = bool(
        (time_lag_hours > lag_min + lag_step_h) and (time_lag_hours < lag_max - lag_step_h)
    )

    r_total = R_TOTAL_SI[test]
    c_area_j_per_m2k = tau_hours * 3600.0 / r_total

    return {
        "test": test,
        "elapsed_h": grid / 3600.0,
        "ext_grid_mean": ext_u,
        "int_grid_mean": int_u,
        "int_grid_pred": int_pred,
        "decrement_factor": decrement_factor,
        "r_squared": r_squared,
        "tau_reliable": tau_reliable,
        "lag_reliable": lag_reliable,
        "time_lag_hours": time_lag_hours,
        "lag_score": lag_score,
        "tau_hours": tau_hours,
        "r_total_si": r_total,
        "c_area_j_per_m2k": c_area_j_per_m2k,
    }


def plot_device_sensors(df: pd.DataFrame, test: int, device: str, role: str, output_dir: Path) -> None:
    wide = build_wide_frame(df, test, device)
    if wide.empty:
        return

    fig, ax = plt.subplots(figsize=(10, 5))
    hours = wide.index.to_numpy() / 3600.0
    for col in wide.columns:
        style = dict(linewidth=2, linestyle="--", color="black") if col == "ambient" else dict(linewidth=1)
        ax.plot(hours, wide[col], label=col, **style)

    ax.set_xlabel("Elapsed time since first sample (hours)")
    ax.set_ylabel("Temperature (C)")
    ax.set_title(f"Test {test} - {device} ({role}) - sensor grid")
    ax.legend(ncol=2, fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / f"test{test}_{device}_sensors.png", dpi=150)
    plt.close(fig)


def plot_interior_vs_exterior_ambient(df: pd.DataFrame, test: int, output_dir: Path) -> None:
    test_cfg = next(t for t in TEST_CONFIGS if t.number == test)
    roles = {d.role: d.device for d in test_cfg.devices}
    if "interior" not in roles or "exterior" not in roles:
        return

    fig, ax = plt.subplots(figsize=(10, 5))
    for role, device in roles.items():
        sub = df[(df["test"] == test) & (df["device"] == device) & (df["sensor_name"] == "ambient")]
        sub = sub.sort_values("elapsed_s")
        ax.plot(sub["elapsed_h"], sub["temperature_c"], label=f"{role} ({device}) ambient")

    ax.set_xlabel("Elapsed time since first sample (hours)")
    ax.set_ylabel("Temperature (C)")
    ax.set_title(f"Test {test} - interior vs exterior ambient")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / f"test{test}_interior_vs_exterior_ambient.png", dpi=150)
    plt.close(fig)


def plot_delta_t(delta: pd.DataFrame, test: int, output_dir: Path) -> None:
    if delta is None or delta.empty:
        return

    fig, ax = plt.subplots(figsize=(10, 5))
    for col in delta.columns:
        if col in ("elapsed_s", "elapsed_h"):
            continue
        style = dict(linewidth=2, linestyle="--", color="black") if col == "ambient" else dict(linewidth=1)
        ax.plot(delta["elapsed_h"], delta[col], label=col, **style)

    ax.axhline(0, color="gray", linewidth=1)
    ax.set_xlabel("Elapsed time since first sample (hours)")
    ax.set_ylabel("Exterior minus interior (C)")
    ax.set_title(f"Test {test} - delta-T across wall assembly (exterior - interior)")
    ax.legend(ncol=2, fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / f"test{test}_delta_t.png", dpi=150)
    plt.close(fig)


def plot_heat_flux(flux: pd.DataFrame | None, test: int, output_dir: Path) -> None:
    if flux is None or flux.empty:
        return

    r_total = R_TOTAL_SI[test]
    u_total = 1.0 / r_total

    fig, ax = plt.subplots(figsize=(10, 5))
    for col in flux.columns:
        if col in ("elapsed_s", "elapsed_h"):
            continue
        style = dict(linewidth=2, linestyle="--", color="black") if col == "ambient" else dict(linewidth=1)
        ax.plot(flux["elapsed_h"], flux[col], label=col, **style)

    ax.axhline(0, color="gray", linewidth=1)
    ax.set_xlabel("Elapsed time since first sample (hours)")
    ax.set_ylabel("Estimated heat flux (W/m2)")
    ax.set_title(
        f"Test {test} - estimated heat flux (R_total={r_total:.3f} m2K/W, "
        f"U={u_total:.2f} W/m2K)"
    )
    ax.legend(ncol=2, fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / f"test{test}_heat_flux.png", dpi=150)
    plt.close(fig)


def plot_heat_flux_comparison(flux_by_test: dict[int, pd.DataFrame], output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    for test, flux in sorted(flux_by_test.items()):
        if flux is None or flux.empty or "ambient" not in flux.columns:
            continue
        ax.plot(flux["elapsed_h"], flux["ambient"], label=f"Test {test}", linewidth=1.5)

    ax.axhline(0, color="gray", linewidth=1)
    ax.set_xlabel("Elapsed time since first sample (hours)")
    ax.set_ylabel("Estimated heat flux, ambient-driven (W/m2)")
    ax.set_title("Heat flux comparison across tests (positive = exterior warming interior)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / "all_tests_heat_flux_comparison.png", dpi=150)
    plt.close(fig)


def plot_grid_aggregate(agg: pd.DataFrame, test: int, device: str, role: str, output_dir: Path) -> None:
    """Show the combined (9-point average) grid reading for one wall face,
    with a min-max band showing how much the 9 individual points disagree."""
    if agg is None or agg.empty:
        return

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.fill_between(
        agg["elapsed_h"], agg["grid_min"], agg["grid_max"], alpha=0.2, color="tab:blue",
        label="grid min-max spread",
    )
    ax.plot(agg["elapsed_h"], agg["grid_mean"], color="tab:blue", linewidth=2, label="grid_mean (9-pt avg)")
    if "ambient" in agg.columns:
        ax.plot(agg["elapsed_h"], agg["ambient"], color="black", linewidth=1.5, linestyle="--", label="ambient")

    ax.set_xlabel("Elapsed time since first sample (hours)")
    ax.set_ylabel("Temperature (C)")
    ax.set_title(f"Test {test} - {device} ({role}) - combined 6in grid (9 points -> 1 series)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / f"test{test}_{device}_grid_aggregate.png", dpi=150)
    plt.close(fig)


def plot_thermal_inertia(inertia: dict | None, test: int, output_dir: Path) -> None:
    if inertia is None:
        return

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(inertia["elapsed_h"], inertia["ext_grid_mean"], label="exterior grid_mean", linewidth=1.5)
    ax.plot(inertia["elapsed_h"], inertia["int_grid_mean"], label="interior grid_mean (actual)", linewidth=1.5)
    ax.plot(
        inertia["elapsed_h"], inertia["int_grid_pred"], label="interior grid_mean (RC model fit)",
        linewidth=1.5, linestyle=":", color="black",
    )

    lag_flag = "" if inertia["lag_reliable"] else "  [AT SEARCH BOUND - low confidence]"
    tau_flag = "" if inertia["tau_reliable"] else "  [POOR FIT - low confidence]"
    text = (
        f"decrement factor: {inertia['decrement_factor']:.2f}\n"
        f"time lag: {inertia['time_lag_hours']:.2f} h{lag_flag}\n"
        f"RC time constant (tau): {inertia['tau_hours']:.2f} h{tau_flag}\n"
        f"RC fit R2: {inertia['r_squared']:.2f}\n"
        f"implied areal capacitance: {inertia['c_area_j_per_m2k'] / 1000:.0f} kJ/(m2.K)"
    )
    ax.text(
        0.02, 0.98, text, transform=ax.transAxes, va="top", ha="left", fontsize=9,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.85),
    )

    ax.set_xlabel("Elapsed time since first sample (hours)")
    ax.set_ylabel("Temperature (C)")
    ax.set_title(f"Test {test} - thermal inertia (exterior grid vs interior grid)")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_dir / f"test{test}_thermal_inertia.png", dpi=150)
    plt.close(fig)


def plot_thermal_inertia_summary(inertia_by_test: dict[int, dict], output_dir: Path) -> None:
    if not inertia_by_test:
        return

    tests = sorted(inertia_by_test.keys())
    decrements = [inertia_by_test[t]["decrement_factor"] for t in tests]
    lags = [inertia_by_test[t]["time_lag_hours"] for t in tests]
    taus = [inertia_by_test[t]["tau_hours"] for t in tests]
    lag_hatches = ["" if inertia_by_test[t]["lag_reliable"] else "//" for t in tests]
    tau_hatches = ["" if inertia_by_test[t]["tau_reliable"] else "//" for t in tests]

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))
    labels = [f"Test {t}" for t in tests]

    axes[0].bar(labels, decrements, color="tab:blue")
    axes[0].set_title("Decrement factor\n(interior swing / exterior swing)")
    axes[0].set_ylabel("ratio (lower = more damping)")
    axes[0].grid(alpha=0.3, axis="y")

    bars1 = axes[1].bar(labels, lags, color="tab:orange")
    for bar, hatch in zip(bars1, lag_hatches):
        bar.set_hatch(hatch)
    axes[1].set_title("Time lag\n(interior trails exterior; hatched = at search bound)")
    axes[1].set_ylabel("hours")
    axes[1].grid(alpha=0.3, axis="y")

    bars2 = axes[2].bar(labels, taus, color="tab:green")
    for bar, hatch in zip(bars2, tau_hatches):
        bar.set_hatch(hatch)
    axes[2].set_title("RC time constant (tau)\n(higher = more inertia; hatched = poor fit)")
    axes[2].set_ylabel("hours")
    axes[2].grid(alpha=0.3, axis="y")

    fig.suptitle("Thermal inertia comparison across tests")
    fig.tight_layout()
    fig.savefig(output_dir / "all_tests_thermal_inertia_summary.png", dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    combined, report_lines = load_all_tests(args.data_dir)

    combined_out = combined[
        [
            "test",
            "device",
            "role",
            "role_inferred",
            "elevation",
            "wall_assembly",
            "elapsed_s",
            "elapsed_h",
            "approx_timestamp",
            "sensor_name",
            "sensor_id",
            "temperature_c",
        ]
    ].sort_values(["test", "device", "elapsed_s"])
    combined_out.to_csv(args.output_dir / "combined_readings_long.csv", index=False)

    report_path = args.output_dir / "data_quality_report.txt"
    report_path.write_text("\n".join(report_lines) + "\n")
    print("\n".join(report_lines))

    flux_by_test: dict[int, pd.DataFrame] = {}
    flux_frames = []

    inertia_by_test: dict[int, dict] = {}
    grid_agg_frames = []

    for test_cfg in TEST_CONFIGS:
        test = test_cfg.number
        for dev in test_cfg.devices:
            plot_device_sensors(combined, test, dev.device, dev.role, args.output_dir)

            grid_agg = compute_grid_aggregate(combined, test, dev.device)
            plot_grid_aggregate(grid_agg, test, dev.device, dev.role, args.output_dir)
            if not grid_agg.empty:
                tagged = grid_agg.copy()
                tagged["test"] = test
                tagged["device"] = dev.device
                tagged["role"] = dev.role
                grid_agg_frames.append(tagged)

        plot_interior_vs_exterior_ambient(combined, test, args.output_dir)

        delta = compute_delta_t(combined, test)
        plot_delta_t(delta, test, args.output_dir)

        flux = compute_heat_flux(delta, test)
        plot_heat_flux(flux, test, args.output_dir)
        if flux is not None:
            flux_by_test[test] = flux
            tagged = flux.copy()
            tagged["test"] = test
            flux_frames.append(tagged)

        inertia = compute_thermal_inertia(combined, test)
        plot_thermal_inertia(inertia, test, args.output_dir)
        if inertia is not None:
            inertia_by_test[test] = inertia
            lag_note = "" if inertia["lag_reliable"] else " (AT SEARCH BOUND, low confidence)"
            tau_note = "" if inertia["tau_reliable"] else " (POOR FIT, low confidence)"
            report_lines.append(
                f"\nTest {test} thermal inertia: decrement_factor={inertia['decrement_factor']:.2f} "
                f"time_lag={inertia['time_lag_hours']:.2f}h{lag_note} "
                f"tau={inertia['tau_hours']:.2f}h R2={inertia['r_squared']:.2f}{tau_note} "
                f"implied_C_area={inertia['c_area_j_per_m2k'] / 1000:.0f} kJ/(m2.K)"
            )

    plot_heat_flux_comparison(flux_by_test, args.output_dir)
    plot_thermal_inertia_summary(inertia_by_test, args.output_dir)

    if flux_frames:
        flux_out = pd.concat(flux_frames, ignore_index=True)
        flux_out.insert(0, "test", flux_out.pop("test"))
        flux_out.to_csv(args.output_dir / "heat_flux_estimates.csv", index=False)

    if grid_agg_frames:
        grid_agg_out = pd.concat(grid_agg_frames, ignore_index=True)
        grid_agg_out.to_csv(args.output_dir / "grid_aggregate.csv", index=False)

    if inertia_by_test:
        inertia_rows = [
            {
                "test": t,
                "decrement_factor": v["decrement_factor"],
                "time_lag_hours": v["time_lag_hours"],
                "lag_correlation_score": v["lag_score"],
                "lag_reliable": v["lag_reliable"],
                "tau_hours": v["tau_hours"],
                "tau_r_squared": v["r_squared"],
                "tau_reliable": v["tau_reliable"],
                "r_total_si_m2k_per_w": v["r_total_si"],
                "implied_c_area_j_per_m2k": v["c_area_j_per_m2k"],
            }
            for t, v in sorted(inertia_by_test.items())
        ]
        pd.DataFrame(inertia_rows).to_csv(args.output_dir / "thermal_inertia_summary.csv", index=False)

    report_path.write_text("\n".join(report_lines) + "\n")

    print(f"\nWrote combined data + plots to {args.output_dir}")


if __name__ == "__main__":
    main()
