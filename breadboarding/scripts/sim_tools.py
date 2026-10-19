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
import uuid

import numpy as np
from bblayout import Layout

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.environ.get("BB_MODELS", os.path.join(HERE, "..", "models"))

def _models(path=None):
    """Return (npn_model_line, {bblayout_led_model: line}) from models.inc.

    models.inc names LEDs LED<COLOUR> (LEDRED, LEDBLUE, ...); bblayout's export calls them LED_<COLOUR>.
    """
    txt = open(path or os.path.join(MODELS, "models.inc")).read()
    npn = re.search(r"^\.model Q2N3904 NPN\((.*)\)\s*$", txt, re.M).group(1)
    leds = {f"LED_{m.group(1)}": f".model LED_{m.group(1)} D({m.group(2)})"
            for m in re.finditer(r"^\.model LED([A-Z]+) D\((.*)\)\s*$", txt, re.M)}
    return f".model NPN NPN({npn})", leds


class SimError(RuntimeError):
    pass


def _spice_num(x):
    m = re.fullmatch(r"([0-9.eE+-]+)\s*(meg|[fpnumkg]?)\w*", str(x).strip(), re.I)
    mult = {"": 1, "f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "meg": 1e6, "g": 1e9}
    return float(m.group(1)) * mult[m.group(2).lower()]


def _check_complete(t, T, name):
    """ngspice can stop a transient early (e.g. a model warning) yet exit 0; refuse truncated data."""
    if t[-1] < 0.999 * _spice_num(T):
        raise SimError(f"{name}: transient stopped at t = {t[-1]:.4g} s of {T}; check model warnings in the log")


def as_built(key, T, step, layout_path=None, beta=None, leds=None, models_path=None, extra=(), extra_netlist="", timeout=600, parasitic_L="auto"):
    """Simulate the as-placed board (breadboard parasitics included).

    Every LED (or only those listed in `leds`, e.g. ["D1","D2"]) gets a 0 V sense source.
    Returns (t, I) for a single LED, or (t, {ref: I}) when several LEDs are sensed.
    `extra` adds node voltages to the output, e.g. ["F_a17"], returned in the dict as "v(name)".
    Models come from models/models.inc (single source of truth); beta overrides Bf.
    `extra_netlist` is inserted before .tran: stimuli the board cannot show, e.g. a finger as a
    voltage-controlled switch between two hole nodes ("<NET>_<hole>", e.g. VCC_b2 and B1_b3).
    parasitic_L: True keeps bblayout's nH strip/jumper inductors, False replaces them by 1 uOhm,
    "auto" (default): False for boards with an NE555, otherwise True with one retry without them when
    ngspice reports "timestep too small". nH inductors next to the 1 mV-sharp behavioural NE555 switches make
    the transient stiff (failures, or > 10 min for 8 s at 10 us); at LED time scales they do nothing.
    `timeout` (s) bounds the ngspice run; long runs at fine steps take minutes, so keep T to a few slow cycles.
    """
    path = layout_path or f"{key}_layout.json"
    s = Layout.load(path).spice(analysis=f".tran {step} {T} 0 {step}", supplies={"VCC": 5})
    s = s.replace('* .include "NE555.lib"', f'.include {os.path.join(MODELS, "ne555.lib")}')
    s = s.replace("DC 5  ; supply", "PWL(0 0 1m 5)  ; supply")
    refs = leds or re.findall(r"^(D\d+) \S+ \S+ LED_[A-Z]+", s, re.M)
    if not refs:
        raise SimError("no LEDs found in the exported netlist")
    for r in refs:
        s, n = re.subn(rf"^{r} {r}_A {r}_K", f"VS_{r} {r}_A {r}_mid 0\n{r} {r}_mid {r}_K", s, flags=re.M)
        if n != 1:
            raise SimError(f"LED {r} not found in netlist")
    npn, led_models = _models(models_path)
    if beta is not None:
        npn = re.sub(r"Bf=[0-9.eE+-]+", f"Bf={beta}", npn)
    for name in set(re.findall(r"^\.model (LED_[A-Z]+) ", s, re.M)):
        if name not in led_models:
            raise SimError(f"no model {name.replace('_', '')} in models.inc (LED colour not characterised)")
        s = re.sub(rf"^\.model {name} .*$", led_models[name], s, flags=re.M)
    s = re.sub(r"^\.model NPN .*$", npn, s, flags=re.M)
    s = s.replace(f".tran {step}", f"{extra_netlist}\n.options method=gear\n.tran {step}", 1)
    vecs = [f"i(VS_{r})" for r in refs] + [f"v({n})" for n in extra]
    # save only the vectors we write: by default ngspice keeps every node (GBs for long fine-step runs)
    s = re.sub(r"^\.end\s*$", f".save {' '.join(vecs)}\n.control\nrun\nwrdata {key}_ab.dat {' '.join(vecs)}\n.endc\n.end", s, flags=re.M)
    if parasitic_L == "auto" and re.search(r"^X\S+ .* NE555\b", s, re.M):
        parasitic_L = False
    if parasitic_L is False:
        s = re.sub(r"^L(SEG\d+) (\S+) (\S+) \S+", r"RL\1 \2 \3 1u", s, flags=re.M)
    run = f"{key}_ab_{os.getpid()}_{uuid.uuid4().hex[:6]}"   # unique: parallel runs must not share files
    s = s.replace(f"wrdata {key}_ab.dat", f"wrdata {run}.dat")
    with open(f"{run}.cir", "w") as f:
        f.write(s)
    r = subprocess.run(["ngspice", "-b", f"{run}.cir"], capture_output=True, text=True, timeout=timeout)
    log = r.stdout + r.stderr
    m = re.search(r"Timestep too small[^\n]*", log)
    if m and parasitic_L == "auto":
        print(f"as_built({key}): {m.group(0)[:100]} -> retrying without parasitic inductors")
        for f in (f"{run}.cir", f"{run}.dat"):
            if os.path.exists(f):
                os.remove(f)
        return as_built(key, T, step, layout_path, beta, leds, models_path, extra, extra_netlist, timeout, parasitic_L=False)
    if r.returncode != 0 or not os.path.exists(f"{run}.dat") or m or re.search(r"singular matrix", log, re.I):
        raise SimError(f"ngspice failed for {run}.cir: " + (m.group(0) if m else log[-1500:]))
    d = np.loadtxt(f"{run}.dat")
    os.replace(f"{run}.cir", f"{key}_ab.cir")          # keep the last netlist for inspection
    os.remove(f"{run}.dat")
    _check_complete(d[:, 0], T, f"{key}_ab.cir")
    t = d[:, 0]
    cols = {name: d[:, 2 * k + 1] for k, name in enumerate([r for r in refs] + [f"v({n})" for n in extra])}
    if len(refs) == 1 and not extra:
        return t, cols[refs[0]]
    return t, cols


def run_netlist(netlist, vectors, name="design", timeout=600):
    """Run a hand-written design netlist in ngspice batch mode and return {vector: array} plus "t".

    `netlist` is the full text WITHOUT .control/.end; `vectors` e.g. ["i(VSA)", "v(F)"].
    Use "{models}" in the text for the path of models/models.inc. Write 1Meg, never 1M (SPICE M = milli).
    Use a unique `name` per parallel run.
    """
    text = netlist.replace("{models}", os.path.join(MODELS, "models.inc")).replace("{ne555}", os.path.join(MODELS, "ne555.lib"))
    if re.search(r"\b\d+(\.\d+)?M\b(?!eg)", re.sub(r"^\*.*$", "", text, flags=re.M)):
        raise SimError("netlist contains a value like '1M' (= 1 milliohm in SPICE); write 1Meg")
    out = f"{name}.dat"
    if os.path.exists(out):
        os.remove(out)
    text = text.rstrip() + f"\n.control\nrun\nwrdata {out} {' '.join(vectors)}\n.endc\n.end\n"
    with open(f"{name}.cir", "w") as f:
        f.write(text)
    r = subprocess.run(["ngspice", "-b", f"{name}.cir"], capture_output=True, text=True, timeout=timeout)
    log = r.stdout + r.stderr
    if r.returncode != 0 or not os.path.exists(out) or re.search(r"timestep too small|singular matrix", log, re.I):
        raise SimError(f"ngspice failed for {name}.cir:\n" + log[-1500:])
    d = np.loadtxt(out)
    m = re.search(r"^\.tran\s+\S+\s+(\S+)", text, re.M | re.I)
    if m:
        _check_complete(d[:, 0], m.group(1), f"{name}.cir")
    res = {"t": d[:, 0]}
    for k, v in enumerate(vectors):
        res[v] = d[:, 2 * k + 1]          # wrdata writes (t, value) pairs per vector
    return res


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


def flash_groups(t, currents, t0=0.0, thresh=None, min_len=1e-3):
    """Group flashes of several LEDs into bursts.

    currents: {name: I}. Returns a list of (name, [flash lengths]) in time order; a new group starts
    whenever a different LED flashes. Flashes shorter than min_len are dropped.
    """
    events = []
    for name, i in currents.items():
        i = np.asarray(i)
        th = thresh if thresh is not None else 0.5 * np.percentile(i[t > t0], 99.5)  # robust to edge spikes
        m = t > t0
        tt, ii = t[m], i[m]
        on = False
        for a, c in zip(tt, ii):
            if not on and c > th:
                on, s0 = True, a
            elif on and c < 0.6 * th:
                on = False
                if a - s0 >= min_len:
                    events.append((s0, name, a - s0))
    events.sort()
    groups = []
    for s0, name, ln in events:
        if groups and groups[-1][0] == name:
            groups[-1][1].append(ln)
        else:
            groups.append((name, [ln]))
    return groups
