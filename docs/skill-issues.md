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
