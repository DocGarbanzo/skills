# Skill issues log

Problems the `breadboarding` skill hit while in use, and their status.

## 2026-10-19: alternating blinker (2 LEDs, 4 NPN)

| # | Problem | Status |
|---|---|---|
| 1 | Skill not installed in the Claude session; SKILL.md had to be read from the repo checkout. | Open: upload the skill / symlink into `~/.claude/skills/`. |
| 2 | "Run all Python with `uv run`" breaks when working outside the repo (outputs land in the repo). | Fixed in SKILL.md: `uv run --project <repo>` from a separate work dir. |
| 3 | `LEDRED` model had `Tt=4.32u`. Its reverse-recovery charge was injected into slow-astable nodes at every fast edge: slow half period 3.7–5.3 s and dependent on the timestep. | Fixed: `Tt=50n` (realistic for red LEDs); library circuits re-checked by the smoke tests. |
| 4 | `as_built()` only sensed `D1`. | Fixed: senses every LED, returns a dict for several; `extra=` node voltages. |
| 5 | No design-simulation helper; `wrdata` writes (t, v) column pairs, an easy indexing trap. | Open: documented; a netlist runner returning named vectors would help. |
| 6 | `as_built()` carried its own copy of the models, so edits to `models.inc` were ignored. | Fixed: models read from `models/models.inc`. |
| 7 | `as_built()` ignored ngspice failures and could return a stale `.dat`. | Fixed: deletes old output, raises `SimError`; tested. |
| 8 | No page generator: the reference page was a baked HTML file with a single-LED player. | Fixed: `scripts/make_page.py`, `templates/page.css`, `templates/player.js` (any number of LEDs); tested. |
| 9 | Print CSS from the combined page misbehaved in single documents (grid block could not fragment; footer `break-before:avoid` gave a near-empty last page). | Fixed in `templates/page.css`; `scripts/print_check.py` added (`print` dependency group). |
| 10 | Print check needed Playwright, which was not a project dependency. | Fixed: `print` dependency group. |

## 2026-10-19: chaser, police strobe, touch flip-flop (built in parallel)

| # | Problem | Status |
|---|---|---|
| 11 | Player had two trace colours only; a third LED reused the first colour. | Fixed: four scope colours, `t3` chart class, `--led-3`. |
| 12 | Player Hz readout counted any LED (a chaser showed 3 Hz). | Fixed: `player_data(rate_led=k)`. |
| 13 | `chart_svg` clamped values at 0 (no base-voltage plots). | Fixed: `ymin`. |
| 14 | Symmetric rings can sit all-on forever in simulation. | Documented: add a 1 % mismatch run. |
| 15 | `as_built()` runs at 0.1 ms steps exceeded the 120 s tool timeout. | Fixed: `timeout=`; SKILL.md time-budget note. |
| 16 | `flashes()` handled one LED only; bursts needed hand-written grouping. | Fixed: `flash_groups()`. |
| 17 | Still no design-netlist runner (each circuit copied a wrapper). | Fixed: `run_netlist()` returning named vectors. |
| 18 | Injection locking (police strobe) undocumented. | Documented in section 5. |
| 19 | `as_built()` could not add a finger/button stimulus. | Fixed: `extra_netlist=`; `BB_MODELS` env override. |
| 20 | `1M` in a hand-written netlist is 1 mΩ; it silently shorted a base. | Fixed: `run_netlist()` refuses it; SKILL.md gotcha. |
| 21 | No event bands on charts (touch windows). | Fixed: `chart_svg(bands=...)`. |
| 22 | Hz readout meaningless for latches. | Fixed: `player_data(show_rate=False)`; player tolerates a missing readout. |
| 23 | Electrolytic note added even without electrolytics. | Fixed: notes detected from the build instructions. |
| 24 | Net names equal to part refs (`C1`) confused the build list. | Documented: name nets by function. |
| 25 | No knowledge on µA touch inputs. | Documented in section 5. |
| 26 | No parameter-sweep helper (grid search needed unique file names, multiprocessing). | Open: `run_netlist(name=...)` covers unique names; a `sweep()` helper is still to do. |
