# skills

Claude skills plus the tooling to run them locally.

| Skill | What it does |
|---|---|
| [`breadboard-circuit-design`](breadboard-circuit-design/SKILL.md) | Designs, simulates (ngspice), lays out (bblayout) and documents verified half-breadboard circuits — LED blinkers, faders, strobes, 555 timers — with straight wiring and as-built checks. |

## Setup

System packages (not installable with uv):

```bash
# Debian/Ubuntu
sudo apt-get install -y ngspice libcairo2
# macOS
brew install ngspice cairo
```

Python environment with [uv](https://docs.astral.sh/uv/):

```bash
uv sync            # creates .venv from pyproject.toml + uv.lock (Python 3.12)
uv run pytest -q   # smoke tests: ngspice, models, all example layouts, two as-built simulations
```

Run things inside the environment with `uv run`, e.g.

```bash
uv run python breadboard-circuit-design/scripts/sim_tools.py blink 14 2m
```

(`sim_tools.py` looks for `<key>_layout.json` in the current directory; copy one from `examples/` or pass `layout_path=` from Python.)

## Installing a skill into Claude

Upload the skill folder (e.g. `breadboard-circuit-design/`) as a custom skill in Claude, or copy it into your Claude Code skills directory (`~/.claude/skills/`). The `SKILL.md` frontmatter holds its name and trigger description.

## Layout

```
breadboard-circuit-design/
  SKILL.md            instructions Claude follows
  models/             SPICE models (Q2N3904, red LED, behavioural NE555)
  scripts/sim_tools.py  as-built simulation + flash detection helpers
  examples/           seven verified board layouts (bblayout JSON)
  tests/              smoke tests (uv run pytest)
pyproject.toml, uv.lock, .python-version
```
