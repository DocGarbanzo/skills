"""Build a single-circuit, print-ready artifact page from a spec dict.

    from make_page import build_page, chart_svg, player_data
    html = build_page(spec)      # spec keys documented in build_page()

Everything visual (CSS, print rules) lives in ../templates/page.css; the player
script supports any number of LEDs.
"""
import base64
import html as _html
import json
import os
import re

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, "..", "templates")

# ---------------------------------------------------------------- resistor colour code
_BAND = ["#111", "#7a4a1e", "#d62828", "#f08a24", "#f2d21b", "#2a9d48", "#1f6fd1", "#7b3fb0", "#8a8a8a", "#f4f4f4"]
_GOLD = "#c9a227"


def _ohms(v):
    m = re.fullmatch(r"([0-9.]+)\s*([kKmM]?)", v.strip().replace("Ω", ""))
    if not m:
        raise ValueError(f"cannot parse resistor value {v!r}")
    return float(m.group(1)) * {"": 1, "k": 1e3, "K": 1e3, "m": 1e6, "M": 1e6}[m.group(2)]


def bands(value):
    """4-band colour code (digit, digit, multiplier) as HTML swatches."""
    r = _ohms(value)
    e = int(np.floor(np.log10(r))) - 1
    d = int(round(r / 10 ** e))
    if d >= 100:
        d //= 10
        e += 1
    cols = [_BAND[d // 10], _BAND[d % 10], _BAND[e] if e >= 0 else _GOLD]
    return '<span class="bands">' + "".join(f'<i style="background:{c}"></i>' for c in cols) + "</span>"


def pretty_ohms(value):
    r = _ohms(value)
    if r >= 1e6:
        return f"{r/1e6:g} MΩ"
    if r >= 1e3:
        return f"{r/1e3:g} kΩ"
    return f"{r:g} Ω"


# ---------------------------------------------------------------- build steps
def steps_html(instructions):
    """Convert bblayout Layout.instructions() text into <li> items."""
    items = []
    for block in re.split(r"\n(?=\d+\. )", instructions):
        if not re.match(r"\d+\. ", block):
            continue
        head, *pins = block.split("\n")
        head = re.sub(r"^\d+\. ", "", head).rstrip(":")
        wm = re.match(r"Wire \((\w+), ~([0-9.]+)\"\): (\S+) -> (\S+)\s+\[(\w+)\]", head)
        if wm:
            col, ln, a, b, net = wm.groups()
            items.append(f'<li><span class="sw" style="--w:var(--wire-{col})"></span>'
                         f'<span class="what">{col.capitalize()} jumper, about {ln}"</span>'
                         f'<span class="holes"><code>{a}</code> → <code>{b}</code></span><span class="net">{net}</span></li>')
            continue
        hm = re.match(r"Insert (\w+) (\S+) \(([^)]+)\)", head)
        if not hm:
            raise ValueError(f"unparsed instruction line: {head!r}")
        ref, val, kind = hm.groups()
        nm = re.search(r"notch facing (\w+)", head)
        kind = {"inline-3": "transistor", "led": "LED", "electrolytic": "electrolytic capacitor",
                "DIP-8": "chip (DIP-8), notch facing " + (nm.group(1) if nm else "left")}.get(kind, kind)
        pl = []
        for p in pins:
            pm = re.match(r"\s*pin (\S+)(?: \((\w+)\))?\s+-> (\S+)\s+\[(\w+)\]", p)
            if pm:
                lab = pm.group(1) + (" " + pm.group(2) if pm.group(2) else "")
                pl.append(f'<span class="pin"><b>{_html.escape(lab)}</b> <code>{pm.group(3)}</code></span>')
        items.append(f'<li><span class="ref">{ref}</span><span class="what">{val} {kind}</span>'
                     f'<span class="holes">{"".join(pl)}</span></li>')
    return "\n".join(items)


# ---------------------------------------------------------------- charts
def chart_svg(t, series, ymax, yticks, xmax, xstep, yunit="mA", label="Simulated trace", area=True, decimate=1500):
    """Line chart. series: list of (y_array, css_class) where css_class is '' or 't2' (second colour), 'cu' (copper)."""
    W, H, l, r, top, b = 640, 210, 44, 12, 14, 34
    X = lambda x: l + (W - l - r) * x / xmax
    Y = lambda y: top + (H - top - b) * (1 - min(max(y, 0), ymax) / ymax)
    t = np.asarray(t)
    g = []
    for v in yticks:
        g.append(f'<line x1="{l}" x2="{W-r}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="grid"/>'
                 f'<text x="{l-8}" y="{Y(v)+4:.1f}" text-anchor="end" class="tick">{v:g}</text>')
    x = 0.0
    while x <= xmax + 1e-9:
        g.append(f'<text x="{X(x):.1f}" y="{H-b+18}" text-anchor="middle" class="tick">{x:g}</text>')
        x += xstep
    paths = []
    for y, cls in series:
        y = np.asarray(y)
        m = t <= xmax
        tt, yy = t[m], y[m]
        # min/max decimation keeps edges sharp
        k = max(1, len(tt) // decimate)
        pts = []
        for i in range(0, len(tt), k):
            seg = yy[i:i + k]
            pts.append((tt[i], seg.max()))
            pts.append((tt[min(i + k - 1, len(tt) - 1)], seg.min() if seg.argmin() > seg.argmax() else seg.max()))
        p = " ".join(f"{X(a):.1f},{Y(c):.1f}" for a, c in pts)
        if area and cls != "cu":
            paths.append(f'<path d="M{X(pts[0][0]):.1f},{Y(0):.1f} L{p.replace(" ", " L")} L{X(pts[-1][0]):.1f},{Y(0):.1f} Z" class="area {cls}"/>')
        paths.append(f'<polyline points="{p}" class="trace {cls}"/>')
    return (f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="{_html.escape(label)}">'
            + "".join(g) + "".join(paths)
            + f'<text x="{l}" y="{top-3}" class="axis">{yunit}</text>'
            + f'<text x="{W-r}" y="{H-4}" text-anchor="end" class="axis">time (s)</text></svg>')


# ---------------------------------------------------------------- player data
def player_data(t, currents, t0, t1, dt=1e-3):
    """Resample LED currents (dict name -> A) on [t0, t1) at dt, quantise to uint8 with a shared full scale."""
    tg = np.arange(t0, t1, dt)
    ys = {k: np.clip(np.interp(tg, t, np.asarray(v) * 1e3), 0, None) for k, v in currents.items()}
    imax = max(float(np.percentile(y, 99.5)) for y in ys.values())
    leds = [{"name": k, "b64": base64.b64encode(np.round(np.clip(y / imax, 0, 1) * 255).astype(np.uint8).tobytes()).decode()}
            for k, y in ys.items()]
    return {"dt": dt, "n": len(tg), "imax_mA": round(imax, 2), "leds": leds}


# ---------------------------------------------------------------- page
_TRANSISTOR_NOTE = ("<b>Transistor pinout.</b> The layout assumes E-B-C pin order, read left to right with the flat face toward you, "
                    "as on the 2N2222A, 2N3904, S8050 and S9013. The build order always lists a transistor's pins as E, B, C, so compare "
                    "their column numbers. If E is in the lower-numbered column (E left of C), the flat face points toward the bottom edge "
                    "of the board, toward you. If C is left of E, the flat face points toward the top edge. If your part is a BC547 or BC548 "
                    "(C-B-E order), turn every transistor 180° from what the drawing shows.")
_CAP_NOTE = ("<b>Electrolytic polarity.</b> The <code>+</code> lead is the longer one; the stripe on the can marks <code>−</code>.")


def board_svg(svg_text):
    s = re.sub(r'<text x="7\.0" y="19\.[0-9]+"[^>]*>[^<]*</text>\n?', "", svg_text, count=1)
    return re.sub(r'width="[0-9.]+" height="[0-9.]+" viewBox="0 0 ([0-9.]+) ([0-9.]+)"',
                  lambda m: f'viewBox="0 25 {m.group(1)} {float(m.group(2))-25}" role="img" aria-label="Breadboard layout"', s, count=1)


def build_page(spec):
    """spec keys:
    title, eyebrow, lede (html), specs [(label, value)], player (from player_data) and player_caption,
    board_svg (raw bblayout svg text), board_caption, charts [(title, svg, caption)],
    parts [(refs, value, note)] — value like '330', '2.2k' gets bands; prefix with '=' to print verbatim,
    instructions (Layout.instructions() text), supply_note, how (html), notes [html] (extra notes),
    has_transistors (bool), footer (html).
    """
    css = open(os.path.join(TEMPLATES, "page.css")).read()
    js = open(os.path.join(TEMPLATES, "player.js")).read()
    e = _html.escape
    specs = "".join(f'<div class="spec"><span>{e(a)}</span><b>{e(b)}</b></div>' for a, b in spec["specs"])
    pl = spec["player"]
    multi = len(pl["leds"]) > 1
    leds = "".join(f'<figure><div class="led"><div class="glow"></div></div><figcaption>{e(d["name"])}</figcaption></figure>'
                   for d in pl["leds"])
    cur = " · ".join(f'{e(d["name"])} <b class="cur">0.0</b> mA' for d in pl["leds"])
    player = f'''<figure class="panel player" data-key="main">
    <div class="player-head"><h3>Live simulation</h3><button type="button" class="play" aria-pressed="false">Play</button></div>
    <div class="player-body{' multi' if multi else ''}">
      <div class="leds" aria-hidden="true">{leds}</div>
      <div class="scope-wrap"><canvas class="scope" aria-label="Scrolling LED current trace"></canvas></div>
    </div>
    <div class="readout"><span><b class="rate">–</b> Hz</span><span>{cur}</span><span class="tpos">t = 0.0 s</span></div>
    <figcaption>{spec.get("player_caption", "Real-time replay of the ngspice LED current; the trace shows the last 4 seconds.")}</figcaption>
  </figure>'''
    charts = "".join(f'<figure class="panel"><h3>{e(t)}</h3>{svg}<figcaption>{cap}</figcaption></figure>' for t, svg, cap in spec["charts"])
    rows = []
    for refs, val, note in spec["parts"]:
        if val.startswith("="):
            v = val[1:]
        elif re.fullmatch(r"[0-9.]+\s*[kKmM]?", val):
            v = f'{pretty_ohms(val)} {bands(val)}'
        else:
            v = e(val)
        rows.append(f"<tr><td>{e(refs)}</td><td class=\"n\">{v}</td><td>{note}</td></tr>")
    notes = ([_TRANSISTOR_NOTE] if spec.get("has_transistors", True) else []) + [_CAP_NOTE] + spec.get("notes", [])
    notes_html = "".join(f'<div class="note">{n}</div>' for n in notes)
    data = json.dumps({"main": pl})
    return f'''<title>{e(spec["title"])}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600&family=Barlow:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
<style>
{css}
</style>
<div class="wrap">
<header>
  <div class="eyebrow">{e(spec["eyebrow"])}</div>
  <h1>{e(spec["title"])}</h1>
</header>
<section class="circuit" id="main" data-title="{e(spec["title"])}">
  <div class="specs">{specs}</div>
  <p class="lede">{spec["lede"]}</p>
  {player}
  <figure>
    <div class="board">{board_svg(spec["board_svg"])}</div>
    <figcaption>{spec["board_caption"]}</figcaption>
  </figure>
  {charts}
  <div class="two">
    <div>
      <h2>Parts</h2>
      <table><tr><th>Ref</th><th>Value</th><th>Note</th></tr>{"".join(rows)}</table>
    </div>
    <div>
      <h2>Build order</h2>
      <ol class="steps">{steps_html(spec["instructions"])}</ol>
      <p class="lede">{spec.get("supply_note", "Connect the supply last: +5 V to the top <code>+</code> rail, ground to the top <code>−</code> rail.")}</p>
    </div>
  </div>
  <div class="notes">
    <h2>How it works</h2>
    {spec["how"]}
  </div>
</section>
<section class="notes" aria-label="Before you power up">
  <h2>Before you power up</h2>
  {notes_html}
</section>
<footer>{spec["footer"]}</footer>
</div>
<script id="player-data" type="application/json">{data}</script>
<script>
{js}
</script>
'''
