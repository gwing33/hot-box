# Termodyn
1. It's a set of tools for **predicting**, and **monitoring** thermal performance of buildings.

1. In current stage of development only **predicting** is available.

1. The **predicting** is based on ***F***inite ***E***lement ***M***ethods 
described in [FREEFEM](https://freefem.org).

1. FREEFEM allows for the solution of partial differential equations 
using the finite element method.

1. It has it's propriatory description language (C++ lookalike with a twist of LaTeX)  
but can also take markdown files (.md) with all the goodies that makedown brings for  
documentation and with the propriatory language as embedded code.

1. It also has python API to run code snippets from pythyon scripts.

1. As placeholder the python environment is extended with C/C++ and Rust bindings (see c and rs directories).

1. For more complex geometries [FREECAD](https://www.freecad.org) can be used to create the geometry and then exported to .stl format.

---

## Installation

1. FREEFEM installation is described in the [FREEFEM documentation](https://doc.freefem.org/introduction/installation.html).

1. Python environment is managed by [uv](https://github.com/astral-sh/uv)

1. Following command will install the required packages:

```python
uv sync
```

---
## Usage

1. FREEFEM [Learn by Examples](https://doc.freefem.org/tutorials/index.html)

```
FreeFem++ mycode.edp
```

or with markdown as source and documentation

```
FreeFem++ mycode.edp.md
```

1. Python scripts can be run (and built) using the `uv` command:

```python
uv run my_script.py
```
## Models

1. [Perfect Wall](https://www.patriquinarchitects.com/need-excellent-thermal-performance-try-these-wall-assemblies/)
1. [Perfect Wall R40](https://www.patriquinarchitects.com/wp-content/uploads/2021/04/UPDATED-SLATE-SCHOOL_.jpg)
1. [Larsen Truss Wall R47](https://www.patriquinarchitects.com/wp-content/uploads/2021/04/UPDATED-HIDDEN-BROOK_1.jpg)

## Monitoring

`hotbox_monitoring.py` is the start of the **monitoring** half of this
project. It parses the raw sensor logs in `../data/Test */*.csv`, cleans up
several known data-quality issues (RTC resets mid-file, a truncated row,
un-synced placeholder timestamps), and produces per-test plots plus a tidy
combined CSV.

```
uv run hotbox_monitoring.py
```

or, without `uv`:

```
python3 hotbox_monitoring.py
```

Outputs are written to `output/` (gitignored):

- `combined_readings_long.csv` -- every reading, tidy long format, with a
  stitched `elapsed_s`/`elapsed_h` column and an approximate anchored
  `approx_timestamp` (see caveats in the script's module docstring).
- `data_quality_report.txt` -- per-file row counts, dropped rows, detected
  RTC resets, and how much of each docx-stated test window was actually
  captured.
- `test{N}_<device>_sensors.png` -- the 3x3 sensor grid + ambient for one
  device/test.
- `test{N}_interior_vs_exterior_ambient.png` -- ambient comparison for
  tests with both an interior and exterior device.
- `test{N}_delta_t.png` -- exterior-minus-interior delta per matched
  sensor position, i.e. the thermal gradient across the wall assembly.
- `test{N}_heat_flux.png` -- estimated conductive heat flux (W/m2) per
  sensor position, derived from delta-T and an assumed whole-assembly
  R-value for that wall type (see `R_TOTAL_SI` / `R_TOTAL_IMPERIAL` near
  the top of the script for the assumptions and sources).
- `all_tests_heat_flux_comparison.png` -- ambient-driven heat flux overlaid
  across all tests that have both an interior and exterior device.
- `heat_flux_estimates.csv` -- the heat flux numbers behind the plots above.
- `test{N}_<device>_grid_aggregate.png` -- the 9-point, 6in-spaced sensor
  grid on one wall face collapsed into a single area-representative series
  (`grid_mean`), with a min-max band showing spatial spread.
- `test{N}_thermal_inertia.png` -- exterior vs interior grid_mean, with a
  fitted first-order RC time constant overlay and decrement
  factor/time-lag/tau annotated (see write-up for the full derivation).
  Low-confidence fits (pinned against a search bound, or explaining little
  variance) are explicitly flagged in the annotation.
- `all_tests_thermal_inertia_summary.png` -- decrement factor / time lag /
  tau compared across tests (hatched bars = low-confidence).
- `grid_aggregate.csv`, `thermal_inertia_summary.csv` -- the numbers
  behind the plots above.

See the docstring at the top of `hotbox_monitoring.py` for a full rundown
of the data-quality issues found in the raw logs and how each is handled.
