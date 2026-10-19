---
name: breadboarding
description: Design, simulate (ngspice), hand-lay-out (bblayout) and publish verified solderless-breadboard circuits, e.g. LED blinkers, faders and 555 timers, with straight wiring and a live viewer.
---

# Breadboarding

Goal: the user describes what a circuit should do; you pick a topology, size it by simulation, place it on a breadboard with straight wiring, verify the as-placed board electrically, and publish a page they can build from.

User context (adjust if told otherwise): half breadboard (400 points, 30 columns), 5 V supply, hobby-kit parts (E12 resistors, electrolytics up to ~1000 µF, small ceramics, inductors up to 680 µH, NPN kit transistors such as 2N2222A/2N3904/S8050 in E-B-C order, red LEDs, NE555 timers). No PNPs or diodes unless the user says so. Prefer the fewest transistors, but robustness comes first. The user is a physicist: give formulas and reasoning, keep prose short.

## Bundled files

- `models/models.inc`: Q2N3904 and LEDRED SPICE models (the single source of truth; `as_built()` reads them from here).
- `models/ne555.lib`: behavioural NE555 subcircuit (pins 1–8 in DIP order). It is debugged; see section 8.
- `scripts/sim_tools.py`: `as_built(key, T, step, beta=None, leds=None, extra=())` exports a saved layout to SPICE, swaps in the real models, adds a sense source to every LED and runs ngspice. It returns `(t, I)` for one LED or `(t, {"D1": I1, "D2": I2, "v(node)": ...})` for several LEDs or extra node voltages, and raises `SimError` when ngspice fails. `extra_netlist=` injects stimuli the board cannot show (a finger, a button: see section 7), `timeout=` bounds the run. `run_netlist(text, vectors)` runs a hand-written design netlist and returns named vectors (no `wrdata` column bookkeeping; refuses `1M`). `edges()` and `flashes()` do hysteretic onset detection with glitch filtering; `flash_groups()` groups flashes of several LEDs into bursts.
- `scripts/make_page.py`: builds the artifact page from a spec dict: `build_page()`, `chart_svg()` (`ymin` for negative values, `bands=` for event windows, classes `''`/`t2`/`t3`), `player_data()` (any number of LEDs; `rate_led=k`, `show_rate=False`), `steps_html()`, `bands()`. Styles and print rules are in `templates/page.css`, the player in `templates/player.js`.
- `examples/*_layout.json`: eleven proven, verified layouts (see section 9). Load them with `Layout.load()`, render with `.svg()`, or simulate with `as_built()`.

## 1. Setup (about 1 minute, once per session)

If the skills repo is checked out (it has `pyproject.toml` and `uv.lock` at its root):

```bash
sudo apt-get install -y ngspice libcairo2     # macOS: brew install ngspice cairo
uv sync && uv run pytest -q                   # env + smoke tests (21 should pass)
```

Then run all Python with `uv run python ...`. Work in a separate directory (not inside the repo) and point uv at the repo: `uv run --project <repo> python design.py`. Import the skill scripts with `sys.path.insert(0, "<repo>/breadboarding/scripts")`. Without the repo (e.g. in a cloud sandbox):

```bash
pip install --break-system-packages -q bblayout cairosvg matplotlib pillow
apt-get install -y -qq ngspice   # or: sudo apt-get ...
```

Copy `models/` into the working directory, and keep a pristine copy of `models.inc` for restoring after β sweeps.

## 2. Workflow

1. **Topology from physics.** State why it oscillates or switches, and the minimum active-part count (section 5). Give the timing formula before simulating.
2. **Design simulation (ngspice, batch).**
   - Use `.include models.inc`.
   - Start the supply with `VCC vcc 0 PWL(0 0 1m 5)`. A symmetric astable started at DC can latch.
   - Use `.options method=gear`.
   - Set the max timestep at or below about 1/20 of the fastest edge time: 2 ms produces garbage with ms-scale switching; use 0.1–0.2 ms for anything near 10–20 Hz.
   - **Write `1Meg`, never `1M`**: SPICE `M` is milli, so `1M` is 1 mΩ (bblayout's export gets this right; hand-written netlists don't). `run_netlist()` refuses `1M`.
   - Write data with `wrdata` and analyse in Python with hysteretic edge detection; drop events shorter than 1–2 ms (sub-ms spikes are model or diffusion-capacitance artefacts, invisible to the eye).
   - Sweep values with a small wrapper and print compact summaries.
   - **Robustness:** rerun with `Bf=100` or `Bf=120` (or `Bf=60` when claiming wide tolerance), and report the result.
   - **Symmetric circuits** (rings, astables) can sit forever in a symmetric all-on state in simulation; the supply ramp alone does not always break it. Also run with a 1 % mismatch in one resistor; if only the perfectly symmetric run hangs, the real circuit is fine.
   - **Time budget:** as-built runs at 0.1 ms steps take minutes per 10 s simulated; simulate a few slow cycles, run sweeps in the background, give each parallel run a unique name.
3. **Hand placement.** Fix every part with `auto_layout(..., fixed={...})`, replace the wire list with your own, rebuild with `Layout.from_dict`, run `verify()`, render to PNG with cairosvg, and look at the image. Iterate until it is clean (section 3). The auto-placer alone gives cramped, crossing layouts.
4. **As-built check.** Run `scripts/sim_tools.as_built(...)` and compare with the design run. They should agree within a few %.
5. **Publish** one artifact page per circuit (section 6). Re-verify and re-simulate any board you re-lay-out.

## 3. Layout rules (learned the hard way)

**Board facts (bblayout `half` template):**
- Rows a–e (top) and f–j (bottom) form 5-hole column strips; the centre channel separates them.
- Rails are T+, T− (top) and B−, B+ (bottom; B+ is outermost). Rails have **no holes at columns 7, 13, 19, 25**. Anything that must go straight into a rail has to sit on another column.
- Hole names: `e12`, `T+6`, `B-14`.

**Footprint spans** (holes between leads):
- Resistors: 3–8. They lie flat and cover the holes in between. A rail-to-row-a/j vertical lead counts: T+ to a (2) and B+ to j (2) are accepted, but j to B− (1) is too short.
- LEDs: 1–3.
- Electrolytics: 1–3, and may go into a rail hole adjacent to row a/j or i (for example `{"+":"j18","-":"B-18"}`).
- Ceramics behave like two-lead parts.

**Transistors** (inline-3, 0.1" pitch): put the pins in row c (top) or row h (bottom). The body is drawn toward the board edge (row b or row i). Keep those rows clear of resistors and wire ends near transistors; the real TO-92 body is there too.

**DIP-8:** give pin 1's hole in row f (normal: notch left, pins 1–4 along the bottom left→right, 5–8 along the top right→left). Giving pin 1 in row e rotates the chip 180° (notch right, pin 1 top right). Use rotation to bring a pin next to the part it connects to, and say so loudly in the caption and parts list.

**Straight wiring only** (the user's strong preference):
- Jumpers are either vertical (same column, often straight across the channel, e.g. `e6→f6`) or horizontal along one row.
- Resistors to rails go straight down or up their column.
- No diagonal leads or wires unless truly unavoidable; then say why.
- Plan columns so that every rail connection lands on a rail-hole column, and put the one node that needs no rail on the hole-less column.
- Cross-coupled nodes cross the channel with short vertical jumpers; put coupling caps flat along a row.

**Hygiene:**
- No part or wire endpoint on a hole another part covers.
- Keep two electrolytic bodies at least 3 holes apart.
- Don't run two rail bridges in the same column (bridge T+↔B+ and T−↔B− in adjacent columns, e.g. 29 and 30).
- Wire colours: red VCC, black GND, yellow/green for cross-coupling, blue/orange for signals. White is invisible on the board drawing.

**Proven two-transistor astable core** (straight wiring), Q1 top / Q2 bottom, columns 5–10:

```python
{"Q1":{"E":"c5","B":"c6","C":"c7"}, "Q2":{"C":"h8","B":"h9","E":"h10"},
 "RB1":{"1":"T+6","2":"a6"}, "Ccross_C1toB2":{"+":"a7","-":"a9"},
 "LED":{"A":"d10","K":"d7"}, "RLED":{"1":"T+10","2":"a10"},
 "Ccross_C2toB1":{"+":"g8","-":"g6"}, "RC2":{"1":"B+8","2":"j8"}, "RB2":{"1":"B+9","2":"j9"}}
# wires: a5→T−5, e6→f6 (B1), e9→f9 (B2), j10→B−10, plus rail bridges
```

Variant when the bottom row g is needed for a follow-on stage (see `examples/breathe_layout.json`, `res_layout.json`):
- Move the C2→B1 cap to the top: `{"+":"d8","-":"d6"}`, and bring the C2 net up with `e8→f8`.
- Q1's collector load becomes a flat resistor `e4→e7` with a VCC strip at column 4 (`a4→T+4`).
- Bottom row g from column 8 is then free (`g8→g12`).
- The same core shifted by +18 (columns 23–28; hole-less 25 = Q1 collector) works on the right half.

**Transistor orientation rule** (put it on the page): parts are E-B-C read left→right with the flat face toward you. bblayout's `instructions()` always lists pins in E, B, C order regardless of position, so compare columns: E in the lower-numbered column → flat face toward the bottom edge (toward the viewer); C in the lower column → flat face toward the top edge. For a BC547/BC548 (C-B-E), turn every transistor 180°.

## 4. bblayout API essentials

```python
from bblayout import Schematic, resistor, capacitor, led, transistor, ic, auto_layout, Layout
sch = Schematic("name", [resistor("R1","VCC","N1","10k"), capacitor("C1","N1","GND","10u",polarized=True),
    led("D1","A","K","red"), transistor("Q1","NPN",c="C1",b="B1",e="GND"),
    ic("U1","NE555",["GND","TH","OUT","VCC","CTL","TH","DIS","VCC"],labels=["GND","TRIG","OUT","RESET","CTRL","THR","DIS","VCC"])])
L = auto_layout(sch, "half", fixed=fixed, rail_nets={"T+":"VCC","T-":"GND","B+":"VCC","B-":"GND"})
d = L.to_dict(); d["wires"] = [{"from":a,"to":b,"net":n,"color":c} for a,b,n,c in wires]
L = Layout.from_dict(d); v = L.verify(); assert v.ok, v.issues
L.save("x_layout.json"); svg = L.svg(); steps = L.instructions()
```

- Fixed spec: a `{pin: hole}` dict (resistor pins "1"/"2", electrolytic "+"/"-", LED "A"/"K", transistor "E"/"B"/"C" in any order); a hole string is accepted for transistors and DIPs.
- Name LEDs `D1`, `D2`, …: `as_built()` puts a sense source in series with each.
- Name nets by function (`Q1C`, `Q1B`, `LEDA`, `F`), never like a part ref (`C1`), or the build list reads "[C1]" next to "Insert C1".
- Exported hole nodes are named `<NET>_<hole>` (e.g. `VCC_b2`, `Q1B_c5`); use them in `extra=` and `extra_netlist=`.
- The verifier checks shorts, open nets, hole conflicts, covered holes, footprints and rail mismatches. Always run it after editing wires.
- Gotchas: `print(...)` piped to `head` can raise BrokenPipe before `save()`, so redirect instead; use `if __name__=="__main__"` guards on modules you reuse.
- bblayout's own generic models (BF=200, LED RS=5) can fail with "timestep too small", so always use `as_built()` with the bundled models and Gear integration.

## 5. Electrical design knowledge

**Oscillator fundamentals:**
- A passive RLC network cannot sustain oscillation: dE/dt = −ΣRI² ≤ 0, and DC sources only shift the equilibrium (superposition).
- A capacitor to +5 V adds no energy: the average of V₀·C·dv/dt over a cycle is 0.
- You need an active element whose current is controlled by the oscillation.
- RC-only networks have real negative poles (no ringing); LC rings and decays with Q = √(L/C)/R.
- One energy store gives a first-order system, which can't oscillate unless the active device is hysteretic (e.g. NPN B–E avalanche snapback, which needs 9–12 V).
- Phase rule: one CE stage gives 180°, so an RC network needs at least 3 sections; two inverting stages already give 360°, so a two-transistor astable needs only 2 capacitors.
- LC is useless at visible rates with small inductors: f = 1/(2π√(LC)), so 680 µH needs ~37 F for 1 Hz, and with large C, Q < 1.

**Two-transistor astable:**
- Half period t = R_B·C·ln((2V_CC − V_BE)/(V_CC − V_BE)) ≈ 0.69·R_B·C, so T ≈ 1.386·R_B·C.
- Saturation needs R_B ≲ β·R_C.
- The cut-off base swings to about −(V_CC − V_sat) ≈ −4.2 V, within the 6 V V_EBO.
- The collector recharge R_C·C must be much shorter than the half period.

**Steering LEDs with collector wiring (no extra gates):**
- An LED from a pulled-up collector F (anode) to another transistor's collector S (cathode) lights only when F's transistor is off AND S's transistor is on. With two complementary collectors S3/S4 of a second astable, two LEDs share one resistor and take turns (see `alt_layout.json`).
- Put the LEDs' anodes on the *fast* oscillator's collector and the cathodes on the *slow* one: the slow collectors then only sink current while already low, so the slow timing is undisturbed. The fast collector is clamped at V_LED + V_sat ≈ 1.9 V; that consistently shrinks the step that collector couples: t = R·C·ln((V_CC − V_BE + ΔV)/(V_CC − V_BE)), ln(6.15/4.35) = 0.35 instead of 0.75. For 50 % duty make that side's R·C ≈ 2.2× the other.
- The idle LED is reverse-biased by up to ≈ V_CC − V_sat ≈ 4.8 V; fine for a 5 V supply (typical LED V_R,max = 5 V), not for higher supplies.

- **Injection locking:** when the slow transistor also sinks LED current, its V_CE,sat step at each flash couples through its timing cap and advances the swap, and the swap restarts the fast astable. The two lock: a constant flash count per burst (police strobe: always 4), at the price of a short cut-off flash at the swap. Unlocked value sets give 3–5 flashes with random partial ones.

**Ring oscillator (odd number of RC-coupled inverters):** an odd ring has no stable state. With the LED from collector to GND (lit while that transistor is off), the collector swing is clamped at V_LED ≈ 1.8 V, so each step is t = R_B·C·ln((V_CC − V_BE + ΔV)/(V_CC − V_BE)) with ΔV ≈ 1.75 V → 0.34·R_B·C; cycle = 3 steps. Too small a collector resistor latches all-on (330 Ω failed at β 120; 470 Ω works).

**Touch inputs (µA level):** a fingertip is 0.3–5 MΩ: from +5 V it injects 1–15 µA; sinking a base to GND through a finger moves < 2 µA. A latch that also drives an LED needs ~0.1 mA base current and cannot be flipped by a finger. Run the latch at µA level (R_C 33k/220k, cross-coupling 1 MΩ), touch from +5 V into the *off* base (works for R_finger ≲ 7·R_cross), and drive the LED with a third NPN. A ~100 nF cap on one base defines the power-up state. Simulate the finger as a voltage-controlled switch (section 7). Touch pads: short bare wire stubs in free holes, drawn as short jumpers.

**Fades:**
- An LED clamps an RC node: its brightness range spans only n·V_T·ln(I_max/I_min) ≈ 0.2–0.4 V, so a direct RC fade looks like a blink.
- Use an RC low-pass plus an NPN emitter follower: I_LED ≈ (V_F − V_BE − V_LED)/R_E.

**Voltage-controlled rate:**
- Returning the base resistors to V_c changes the rate only logarithmically (about 2:1), and it fails at low V_c unless the transistors still saturate (I_B·β ≫ I_C).
- For large ranges (20:1), use a fixed short flash and modulate the gap. Return Q2's collector resistor to V_c, so the swing A ≈ V_c and t_off = R·C·ln(1 + A/(V_CC − V_BE)), which goes to 0 linearly with A.
- A follower can only source and can't go above ~V_CC − 0.7.
- A CE stage's collector can't go below its emitter.
- To get fixed end points, use a saturating CE stage (emitter grounded, base through a resistor) with a series resistor into the load. The end points then depend only on resistor ratios, and β only shapes the ramp.

**Level-triggered refill:**
- It needs hysteresis (a Schmitt trigger); without it the circuit settles at refill = drain and the LED glows steadily.
- With NPN-only parts, the charger's ceiling and the Schmitt thresholds share a node, which limits the swing.
- A timer-driven refill is robust: an asymmetric astable plus an emitter-follower charger, whose B–E junction blocks back-flow (reverse bias < 6 V).

**Harmonic RC oscillator** (phase-shift, 3 low-pass sections):
- At ω = √6/(RC) the ladder attenuates by 1/29.
- CE gain is A ≈ V_RC/V_T.
- The ladder end must see an input impedance ≫ R ≫ R_C. With a Darlington (β²V_T/I_C) that needs β² ≳ 100·A, i.e. β ≥ 100. Add a third follower (β³) for tolerance down to β ≈ 25.
- The ladder also self-biases: V_C ≈ V_B(1 + 3R/R_bias).
- The amplitude is limited by clipping, so the collector is a trapezoid while the ladder output is a clean sine. Purity needs AGC.

**Wien bridge at 1 Hz** is impractical with NPN-only DC coupling: bypassing or coupling would need millifarad capacitors, and open-loop gain is about 10.

**NE555 (bipolar):**
- Internal divider 3 × 5 k; pin 5 Thévenin is 3.33 k to 2/3 V_CC.
- Astable: t_high = ln2·(R_A + R_B)·C, t_low = ln2·R_B·C.
- Output high ≈ V_CC − 1.7 V. In sink mode (LED from +5 V into pin 3), that leaves ~0.7 mA of glow, so put a bleed resistor (~1 k) across the LED.
- Needs 10–100 µF decoupling (and ideally 100 nF at pins 8/1); 10 nF on pin 5 when it isn't driven.
- Pin-5 control: thresholds become V_c and V_c/2, so t_high = (R_A + R_B)·C·ln((V_CC − V_c/2)/(V_CC − V_c)) while t_low stays fixed. Keep V_c ≥ ~0.6 V (discharge saturation), and drive it from a low impedance.
- CMOS (TLC555/LMC555): rail-to-rail output, picoamp inputs, small supply spikes, but weak source current (~10 mA).

## 6. Publishing (artifact page)

**One document per circuit by default.** Each circuit gets its own artifact page (title = circuit name, e.g. "Blinker"). Put several circuits on one tabbed page only when the user asks for a combined document. When a circuit is revised, republish its own page (same file path keeps the URL).

Build the page with `scripts/make_page.py` (`build_page(spec)`; the docstring lists the spec keys). It already implements everything below, including the print layout. Page contents, top to bottom:
- Eyebrow (board · supply · part count), title, spec chips, one-paragraph description.
- **Live player:** LED current resampled at 1 ms, quantised to uint8, base64-embedded. Loop over an integer number of periods, or one slow cycle from rate-minimum to rate-minimum. The LED glow opacity is (I/I_max)^0.6, with a scrolling 4 s scope on canvas and a rate readout from hysteretic onsets. It autoplays unless reduced motion is set.
- The bblayout board SVG (strip the title text, set `viewBox`, put it in an `overflow-x:auto` container with min-width ~560 px).
- Charts from the simulation data: LED current, internal node voltages, or rate vs time.
- A parts table with resistor colour bands.
- Build steps parsed from `instructions()`; handle `pin 1 (GND)` labels and the "notch facing left/right" text.
- "How it works" with formulas, and design notes covering what was ruled out and why.
- "Before you power up": orientation rule (only if the circuit has transistors), electrolytic polarity, troubleshooting.

**Print layout (required).** The page must print to A4 without splitting the board; `templates/page.css` does this (page 1 = board, chart, parts; then build order in two columns, how it works, notes; ~4 pages). Pitfalls already fixed there: a `display:grid` block with `break-inside:avoid` cannot fragment, and `break-before:avoid` on the footer can push a whole section to a new page. If the last page holds only the footer, shorten the text. Always check with `uv run --project <repo> --group print python scripts/print_check.py page.html` (headless Chromium, A4, `pdftoppm` PNGs; set `CHROMIUM_PATH` to use an existing Chromium, otherwise run `playwright install chromium` once), then look at every page and the page count.

State that the simulation is ngspice with which models, and give the as-built agreement. Keep the page script (the spec) next to the layout so the page can be regenerated.

## 7. Using the examples

```python
import sys; sys.path.insert(0, "<skill>/scripts")
from sim_tools import as_built, flashes
from bblayout import Layout
L = Layout.load("<skill>/examples/blink_layout.json")
print(L.instructions()); open("blink.svg","w").write(L.svg())
t, i = as_built("blink", T="14", step="2m", layout_path="<skill>/examples/blink_layout.json")
t, I = as_built("alt", T="30", step="1m", layout_path="<skill>/examples/alt_layout.json", extra=["S3_c25"])  # I["D1"], I["D2"], I["v(S3_c25)"]
# a finger (1 MΩ) touching SET at t = 1.0–1.3 s, modelled as a voltage-controlled switch between two hole nodes
finger = """SSET VCC_b2 Q1B_b3 cset 0 FINGER
VCSET cset 0 PWL(0 0 1 0 1.001 1 1.3 1 1.301 0)
.model FINGER SW(vt=0.5 vh=0.1 ron=1Meg roff=1e13)"""
t, i = as_built("ff", T="5", step="1m", layout_path="<skill>/examples/ff_layout.json", extra_netlist=finger)
```

Page skeleton (see the `build_page` docstring for all keys):

```python
from make_page import build_page, chart_svg, player_data
spec = dict(title="Alternating blinker", eyebrow="Half breadboard · 5 V · 4 transistors",
    lede="...", specs=[("Blink", "0.99 s")],
    player=player_data(t, {"D1": I["D1"], "D2": I["D2"]}, t0, t0 + T_loop),
    board_svg=open("alt.svg").read(), board_caption="...",
    charts=[("Simulated LED currents", chart_svg(t, [(I["D1"]*1e3, ""), (I["D2"]*1e3, "t2")], 12, (0, 5, 10), 24, 2), "caption")],
    parts=[("R1", "330", "note"), ("C1", "=22 µF", "note")], instructions=L.instructions(),
    how="<p>...</p>", notes=["<b>If it doesn't work.</b> ..."], footer="...")
open("page.html", "w").write(build_page(spec))
```

## 8. NE555 model notes

ngspice has no 555, so `models/ne555.lib` is behavioural:
- the 3 × 5 k divider;
- two comparators, 1 mV sharp;
- an SR latch on a 1 µF state node `s`, with a strongly bistable hold term;
- the discharge transistor and the output (high = V_CC − 1.7 V, 10 Ω), both switching exactly at s = ½;
- ~3 mA quiescent current.

An earlier, softer version stalled in half-switched states when thresholds moved slowly (pin 5 driven) or timing resistors were large (≥ 100 k). Keep the sharp, bistable form. B-source sign: `B n+ n- I=expr` drives current from n+ through the source into n−. The model omits propagation delays and the real supply-current spikes, so decoupling capacitors have no effect in simulation.

## 8b. LED model note

`LEDRED` uses `Tt=50n`. The value `4.32u` found in common LED models is unrealistic for red LEDs; its reverse-recovery charge (Tt·I ≈ 40 nC) was dumped into timing nodes at every fast edge and made a slow astable's timing erratic and dependent on the timestep. If a result changes with the timestep, suspect stored-charge effects first.

## 9. Proven circuit library (5 V, half board; layouts in `examples/`)

| Circuit | Layout file | Actives | Key values | Result |
|---|---|---|---|---|
| Astable blinker | `blink_layout.json` | 2 NPN | R_LED 330, R_C2 1k, R_B 47k, C 22 µF | 1.33 s period, ~10 mA |
| Breathing fader | `breathe_layout.json` | 3 NPN | astable 1k/68k/47 µF; R5 10k → C3 100 µF → follower, R_E 100 | 4.6 s cycle, fade-in 1.2 s / out 0.4 s, 13 mA |
| Strobe sweep, transistor | `fm_layout.json` | 5 NPN | fast: R_LED 1k, R2 470 to V_t, R3 150k, R4 33k, C1 10 µF, C2 2.2 µF; slow: 4.7k/22k loads, 220k, 100 µF; smoothing 10k, 470 µF to +5 V, clamp 100k; follower | 1.4 → 22 Hz over ~30 s, 43 ms flashes |
| Phase-shift pulser | `ps_layout.json` | 4 NPN | ladder 3 × 47k/10 µF, R_C 2.2k, bias 330k, follower pull-downs 220k/100k, LED via follower 120 Ω | 0.85 Hz, robust β 60–416 |
| Reservoir heartbeat | `res_layout.json` | 3 NPN | astable 4.7k/1k, 68k/22k, 22 µF/10 µF; follower charger R 10 Ω into 1000 µF; LED 150 Ω | 1.24 s beat, 14.6 → 0.1 mA |
| NE555 blinker | `n555_layout.json` | 1 × 555 | R_A 1k, R_B 68k, C 10 µF, 10 nF pin 5, 100 µF decoupling, LED 150 Ω | 0.96 s, 9.5 mA |
| Alternating blinker (2 LEDs) | `alt_layout.json` | 4 NPN | fast: R1 330 (shared LED resistor), R2 2.2k, R3 15k, R4 68k, C1 22 µF, C2 47 µF; slow: 2.2k loads, 15k, 2 × 470 µF; LEDs F→S3, F→S4 | 0.99 s blink, 0.51 s on, swap every 5.1 s, 9.4 mA |
| Three-LED chaser | `chaser_layout.json` | 3 NPN | R_C 470 (LED collector→GND), R_B 22k, C 47 µF ring | 1.00 s cycle, 0.33 s per LED, 6.9 mA |
| Police strobe | `police_layout.json` | 4 NPN | alternating blinker with C1 = C2 = 3.3 µF, C3 = C4 = 47 µF | 9.3 Hz flashes of 36 ms, locked 4 per burst, swap every 0.51 s |
| Touch flip-flop | `ff_layout.json` | 3 NPN | µA latch: R_C 220k/33k, cross 1 MΩ, 100 nF power-up cap; LED driver 3.3k base, 470 Ω | finger 0.3–3.3 MΩ, β 60–416; 6.6 mA on, 0.15 mA standby |
| 555 strobe sweep | `s555_layout.json` | 2 × 555 + 1 NPN | slow 10k/220k/100 µF → 4.7k + 1000 µF → 39k → saturating CE, 100 Ω series, 1k pull-up into fast pin 5; fast 180k/12k/2.2 µF, LED sink mode 220 Ω + 1k bleed, 2 × 100 µF decoupling | 1.2 → 20 Hz, 18 ms flashes, ~30 s cycle |

Reuse these as starting points; re-simulate whenever values change.
