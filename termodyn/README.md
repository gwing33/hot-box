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
