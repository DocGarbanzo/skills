# skills

Claude skills plus the tooling to run them locally.

| Skill | What it does |
|---|---|
| [`breadboard-circuit-design`](breadboard-circuit-design/SKILL.md) | Designs, simulates (ngspice), lays out (bblayout) and documents verified half-breadboard circuits — LED blinkers, faders, strobes, 555 timers — with straight wiring and as-built checks. |

## Prerequisites

You need three things **before** `uv sync` will give you a working setup. uv installs the Python packages, but it cannot install the first two, which are system programs and libraries.

| Prerequisite | Why | Check it is installed |
|---|---|---|
| **ngspice** (circuit simulator) | All simulations run through it | `ngspice -v` prints a version |
| **cairo** (graphics library) | `cairosvg` needs it to render board drawings to PNG | see "Check cairo" below |
| **uv** (Python package manager) | Creates the Python environment from `pyproject.toml` + `uv.lock` | `uv --version` prints a version |

### macOS (Homebrew)

```bash
brew install ngspice cairo uv
```

On Apple Silicon, Python sometimes cannot find Homebrew's cairo. If the cairo check below fails with `no library called "cairo-2" was found`, add this to your shell profile (`~/.zshrc`) and open a new terminal:

```bash
export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_FALLBACK_LIBRARY_PATH"
```

### Ubuntu / Debian

```bash
sudo apt-get install -y ngspice libcairo2
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Windows

Use WSL (Ubuntu) and follow the Ubuntu steps; native Windows builds of ngspice and cairo are possible but not tested here.

### Check cairo

After `uv sync` (next section):

```bash
uv run python -c "import cairosvg; print('cairo OK')"
```

## Setup

```bash
git clone https://github.com/DocGarbanzo/skills.git
cd skills
uv sync            # creates .venv (Python 3.12) from pyproject.toml + uv.lock
uv run pytest -q   # 11 smoke tests
```

The smoke tests check every prerequisite, so a failure tells you what is missing:

| Test | Fails when |
|---|---|
| `test_ngspice_installed` | ngspice is not installed or not on `PATH` |
| `test_svg_renders_to_png` | the cairo library is missing (see the macOS note above) |
| `test_example_layouts_verify` | the Python environment is broken; rerun `uv sync` |
| `test_as_built_period` | ngspice runs but gives wrong results; report it |

## Running things

Always run Python through `uv run` so it uses the project environment:

```bash
cd breadboard-circuit-design/examples
uv run python ../scripts/sim_tools.py blink 14 2m     # simulate the as-built blinker board
```

(`sim_tools.py` looks for `<name>_layout.json` in the current directory; from Python you can pass `layout_path=` instead.)

## Installing a skill into Claude

- **Claude app:** upload the skill folder (e.g. `breadboard-circuit-design/`, zipped) as a custom skill.
- **Claude Code:** copy or symlink the folder into `~/.claude/skills/`.

The `SKILL.md` frontmatter holds the skill's name and the description that decides when Claude uses it. When the repo is checked out locally, the skill uses this uv environment; in a cloud sandbox it falls back to `pip` and `apt`.

## Repository layout

```
breadboard-circuit-design/
  SKILL.md              instructions Claude follows
  models/               SPICE models (Q2N3904, red LED, behavioural NE555)
  scripts/sim_tools.py  as-built simulation + flash detection helpers
  examples/             seven verified board layouts (bblayout JSON)
  tests/                smoke tests (uv run pytest)
pyproject.toml          Python dependencies (bblayout, numpy, cairosvg, matplotlib, pillow)
uv.lock                 exact versions
.python-version         3.12
```
