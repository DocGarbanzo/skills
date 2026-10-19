"""Helpers for the breadboarding skill.

- as_built(): export a saved bblayout layout to SPICE, swap in the real models,
  add a 0 V sense source in series with every LED and run ngspice (errors raise SimError).
- edges() / flashes(): hysteretic LED-onset detection with glitch filtering.

Usage (from the working directory that holds models/ and the *_layout.json):
    from sim_tools import as_built, flashes
    t, i = as_built("blink", T="14", step="2m")
    starts, lengths = flashes(t, i, t0=4)
"""
import os
import re
import subprocess

import numpy as np
from bblayout import Layout

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, "..", "models")

def _models(path=None):
    """Return (npn_model_line, led_model_line) from models.inc, renamed to bblayout's NPN / LED_RED."""
    txt = open(path or os.path.join(MODELS, "models.inc")).read()
    npn = re.search(r"^\.model Q2N3904 NPN\((.*)\)\s*$", txt, re.M).group(1)
    led = re.search(r"^\.model LEDRED D\((.*)\)\s*$", txt, re.M).group(1)
    return f".model NPN NPN({npn})", f".model LED_RED D({led})"


class SimError(RuntimeError):
    pass


def as_built(key, T, step, layout_path=None, beta=None, leds=None, models_path=None, extra=()):
    """Simulate the as-placed board (breadboard parasitics included).

    Every LED (or only those listed in `leds`, e.g. ["D1","D2"]) gets a 0 V sense source.
    Returns (t, I) for a single LED, or (t, {ref: I}) when several LEDs are sensed.
    `extra` adds node voltages to the output, e.g. ["F_a17"], returned in the dict as "v(name)".
    Models come from models/models.inc (single source of truth); beta overrides Bf.
    """
    path = layout_path or f"{key}_layout.json"
    s = Layout.load(path).spice(analysis=f".tran {step} {T} 0 {step}", supplies={"VCC": 5})
    s = s.replace('* .include "NE555.lib"', f'.include {os.path.join(MODELS, "ne555.lib")}')
    s = s.replace("DC 5  ; supply", "PWL(0 0 1m 5)  ; supply")
    refs = leds or re.findall(r"^(D\d+) \S+ \S+ LED_RED", s, re.M)
    if not refs:
        raise SimError("no LED_RED diodes found in the exported netlist")
    for r in refs:
        s, n = re.subn(rf"^{r} {r}_A {r}_K", f"VS_{r} {r}_A {r}_mid 0\n{r} {r}_mid {r}_K", s, flags=re.M)
        if n != 1:
            raise SimError(f"LED {r} not found in netlist")
    npn, led = _models(models_path)
    if beta is not None:
        npn = re.sub(r"Bf=[0-9.eE+-]+", f"Bf={beta}", npn)
    s = re.sub(r"^\.model LED_RED .*$", led, s, flags=re.M)
    s = re.sub(r"^\.model NPN .*$", npn, s, flags=re.M)
    s = s.replace(f".tran {step}", f".options method=gear\n.tran {step}", 1)
    vecs = [f"i(VS_{r})" for r in refs] + [f"v({n})" for n in extra]
    s = re.sub(r"^\.end\s*$", f".control\nrun\nwrdata {key}_ab.dat {' '.join(vecs)}\n.endc\n.end", s, flags=re.M)
    with open(f"{key}_ab.cir", "w") as f:
        f.write(s)
    if os.path.exists(f"{key}_ab.dat"):
        os.remove(f"{key}_ab.dat")
    r = subprocess.run(["ngspice", "-b", f"{key}_ab.cir"], capture_output=True, text=True)
    log = r.stdout + r.stderr
    if r.returncode != 0 or not os.path.exists(f"{key}_ab.dat") or re.search(r"timestep too small|singular matrix", log, re.I):
        raise SimError(f"ngspice failed for {key}_ab.cir:\n" + log[-1500:])
    d = np.loadtxt(f"{key}_ab.dat")
    t = d[:, 0]
    cols = {name: d[:, 2 * k + 1] for k, name in enumerate([r for r in refs] + [f"v({n})" for n in extra])}
    if len(refs) == 1 and not extra:
        return t, cols[refs[0]]
    return t, cols


def edges(t, i, hi, lo):
    """Rising-edge times with hysteresis (on above hi, off below lo)."""
    on, out = False, []
    for a, c in zip(t, i):
        if not on and c > hi:
            on = True
            out.append(a)
        elif on and c < lo:
            on = False
    return np.array(out)


def flashes(t, i, t0=0.0, min_len=2e-3):
    """LED flashes after t0 as (start_times, lengths); drops sub-min_len glitches."""
    m = t > t0
    tt, ii = t[m], i[m]
    imax = ii.max()
    on, starts, lens = False, [], []
    for a, c in zip(tt, ii):
        if not on and c > 0.6 * imax:
            on, s0 = True, a
        elif on and c < 0.3 * imax:
            on = False
            if a - s0 > min_len:
                starts.append(s0)
                lens.append(a - s0)
    return np.array(starts), np.array(lens)


if __name__ == "__main__":
    import sys
    key = sys.argv[1] if len(sys.argv) > 1 else "blink"
    t, i = as_built(key, T=sys.argv[2] if len(sys.argv) > 2 else "14", step=sys.argv[3] if len(sys.argv) > 3 else "1m")
    s, l = flashes(t, i, t0=float(t[-1]) * 0.3)
    if len(s) > 2:
        f = 1 / np.diff(s)
        print(f"{key}: rate {f.min():.2f}..{f.max():.2f} Hz, flash {1e3*np.median(l):.0f} ms, I_LED max {i.max()*1e3:.1f} mA")
