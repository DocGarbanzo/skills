"""Helpers for the breadboarding skill.

- as_built(): export a saved bblayout layout to SPICE, swap in the real models,
  add a 0 V sense source in series with D1 and run ngspice.
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

NPN = (".model NPN NPN(Is=6.734f Xti=3 Eg=1.11 Vaf=74.03 Bf=416.4 Ne=1.259 Ise=6.734f "
       "Ikf=66.78m Xtb=1.5 Br=.7371 Nc=2 Rc=1 Cjc=3.638p Mjc=.3085 Vjc=.75 Fc=.5 Cje=4.493p "
       "Mje=.2593 Vje=.75 Tr=239.5n Tf=301.2p Itf=.4 Vtf=4 Xtf=2 Rb=10)")
LED = ".model LED_RED D(Is=93.2p Rs=42m N=3.73 Cjo=2.97p Vj=.75 M=.333 Tt=4.32u)"


def as_built(key, T, step, layout_path=None, beta=None):
    """Simulate the as-placed board (breadboard parasitics included). Returns (t, I_LED)."""
    path = layout_path or f"{key}_layout.json"
    s = Layout.load(path).spice(analysis=f".tran {step} {T} 0 {step}", supplies={"VCC": 5})
    s = s.replace('* .include "NE555.lib"', f'.include {os.path.join(MODELS, "ne555.lib")}')
    s = s.replace("DC 5  ; supply", "PWL(0 0 1m 5)  ; supply")
    s = re.sub(r"^D1 D1_A D1_K", "VSENSE D1_A dmid 0\nD1 dmid D1_K", s, flags=re.M)
    npn = NPN if beta is None else NPN.replace("Bf=416.4", f"Bf={beta}")
    s = re.sub(r"^\.model LED_RED .*$", LED, s, flags=re.M)
    s = re.sub(r"^\.model NPN .*$", npn, s, flags=re.M)
    s = s.replace(f".tran {step}", f".options method=gear\n.tran {step}", 1)
    s = re.sub(r"^\.end\s*$", f".control\nrun\nwrdata {key}_ab.dat i(VSENSE)\n.endc\n.end", s, flags=re.M)
    with open(f"{key}_ab.cir", "w") as f:
        f.write(s)
    subprocess.run(["ngspice", "-b", f"{key}_ab.cir"], capture_output=True)
    d = np.loadtxt(f"{key}_ab.dat")
    return d[:, 0], d[:, 1]


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
