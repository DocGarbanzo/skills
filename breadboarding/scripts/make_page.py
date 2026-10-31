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


# ---------------------------------------------------------------- UI strings (lang="en" | "de")
STR = {
    "en": dict(parts="Parts", build="Build order", how="How it works", before="Before you power up", live="Live simulation",
               play="Play", pause="Pause", of="of", now="now", ref="Ref", value="Value", note="Note", time="time (s)",
               jumper="{col} jumper, about {ln}\"", player_caption="Real-time replay of the ngspice LED current; the trace shows the last 4 seconds.",
               supply_rail="Connect the supply last: +5 V to the top <code>+</code> rail, ground to the top <code>−</code> rail.",
               kinds={"inline-3": "transistor", "led": "LED", "electrolytic": "electrolytic capacitor", "resistor": "resistor",
                      "capacitor": "capacitor", "button": "push button", "DIP-8": "chip (DIP-8), notch facing {side}"},
               colors={}, sides={"left": "left", "right": "right"}),
    "de": dict(parts="Bauteile", build="Aufbau Schritt für Schritt", how="So funktioniert es", before="Vor dem Einschalten",
               live="Live-Simulation", play="Start", pause="Pause", of="von", now="jetzt", ref="Bez.", value="Wert", note="Hinweis",
               time="Zeit (s)", jumper="{col} Drahtbrücke, ca. {ln}\"",
               player_caption="Echtzeit-Wiedergabe des simulierten LED-Stroms (ngspice); die Kurve zeigt die letzten 4 Sekunden.",
               supply_rail="Versorgung zuletzt anschließen: +5 V an die obere <code>+</code>-Schiene, Masse an die obere <code>−</code>-Schiene.",
               kinds={"inline-3": "Transistor", "led": "LED", "electrolytic": "Elko", "resistor": "Widerstand",
                      "capacitor": "Kondensator", "button": "Taster", "DIP-8": "Chip (DIP-8), Kerbe nach {side}"},
               colors={"red": "Rote", "black": "Schwarze", "yellow": "Gelbe", "green": "Grüne", "blue": "Blaue", "orange": "Orange", "white": "Weiße"},
               sides={"left": "links", "right": "rechts"}),
}
_LED_DE = {"red": "rot", "blue": "blau", "green": "grün", "yellow": "gelb", "white": "weiß"}


# ---------------------------------------------------------------- build steps
def steps_html(instructions, lang="en"):
    """Convert bblayout Layout.instructions() text into <li> items (lang "en" or "de")."""
    T = STR[lang]
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
                         f'<span class="what">{T["jumper"].format(col=T["colors"].get(col, col.capitalize()), ln=ln if lang == "en" else ln.replace(".", ","))}</span>'
                         f'<span class="holes"><code>{a}</code> → <code>{b}</code></span><span class="net">{net}</span></li>')
            continue
        hm = re.match(r"Insert (\w+)(?: (\S+))? \(([^)]+)\)", head)   # value is absent for buttons
        if not hm:
            raise ValueError(f"unparsed instruction line: {head!r}")
        ref, val, kind = hm.groups()
        val = val or ""
        nm = re.search(r"notch facing (\w+)", head)
        side = T["sides"].get(nm.group(1) if nm else "left", "left")
        kind = T["kinds"].get(kind, kind).format(side=side)
        if lang == "de" and kind == "LED":
            val, kind = "", f"LED, {_LED_DE.get(val, val)}"
        elif lang == "de" and kind == "Transistor":
            val, kind = "", f"{val}-Transistor"
        pl = []
        legs = []
        for p in pins:
            pm = re.match(r"\s*pin (\S+)(?: \((\w+)\))?\s+-> (\S+)\s+\[(\w+)\]", p)
            if pm:
                legs.append(pm.group(3))
        tactile = (hm.group(3) == "button" and len(legs) == 2 and legs[0][0] == legs[1][0] and legs[0][0] in "ef")
        if tactile:   # 6 x 6 mm button across the channel: four legs
            o = "f" if legs[0][0] == "e" else "e"
            allx = legs + [o + legs[0][1:], o + legs[1][1:]]
            lab = "Beine" if lang == "de" else "legs"
            items.append(f'<li><span class="ref">{ref}</span><span class="what">{kind}{" (6×6 mm, über den Mittelkanal)" if lang == "de" else " (6×6 mm, across the channel)"}</span>'
                         f'<span class="holes"><span class="pin"><b>{lab}</b> {" ".join(f"<code>{x}</code>" for x in allx)}</span></span></li>')
            continue
        for p in pins:
            pm = re.match(r"\s*pin (\S+)(?: \((\w+)\))?\s+-> (\S+)\s+\[(\w+)\]", p)
            if pm:
                lab = pm.group(1) + (" " + pm.group(2) if pm.group(2) else "")
                pl.append(f'<span class="pin"><b>{_html.escape(lab)}</b> <code>{pm.group(3)}</code></span>')
        items.append(f'<li><span class="ref">{ref}</span><span class="what">{val} {kind}</span>'
                     f'<span class="holes">{"".join(pl)}</span></li>')
    return "\n".join(items)


# ---------------------------------------------------------------- charts
def chart_svg(t, series, ymax, yticks, xmax, xstep, yunit="mA", label="Simulated trace", area=True, decimate=1500, ymin=0.0, bands=(), xlabel="time (s)"):
    """Line chart. series: list of (y_array, css_class); css_class '' (LED red), 't2', 't3' (2nd/3rd colour), 'blue', 'cu' (copper).
    ymin < 0 allows negative values (e.g. base voltages); areas are filled down to y = max(ymin, 0).
    bands: [(t0, t1, label)] shaded event windows (touches, button presses) drawn behind the traces."""
    W, H, l, r, top, b = 640, 210, 44, 12, 14, 34
    X = lambda x: l + (W - l - r) * x / xmax
    Y = lambda y: top + (H - top - b) * (1 - (min(max(y, ymin), ymax) - ymin) / (ymax - ymin))
    t = np.asarray(t)
    g = []
    for b0, b1, lab in bands:
        g.append(f'<rect x="{X(b0):.1f}" y="{top}" width="{max(X(b1)-X(b0), 1.5):.1f}" height="{H-top-b}" class="band"/>'
                 f'<text x="{X(b0)+3:.1f}" y="{top+11}" class="tick">{_html.escape(lab)}</text>')
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
            y0 = max(ymin, 0.0)
            paths.append(f'<path d="M{X(pts[0][0]):.1f},{Y(y0):.1f} L{p.replace(" ", " L")} L{X(pts[-1][0]):.1f},{Y(y0):.1f} Z" class="area {cls}"/>')
        paths.append(f'<polyline points="{p}" class="trace {cls}"/>')
    return (f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="{_html.escape(label)}">'
            + "".join(g) + "".join(paths)
            + f'<text x="{l}" y="{top-3}" class="axis">{yunit}</text>'
            + f'<text x="{W-r}" y="{H-4}" text-anchor="end" class="axis">{_html.escape(xlabel)}</text></svg>')


# ---------------------------------------------------------------- player data
def player_data(t, currents, t0, t1, dt=1e-3, rate_led=None, show_rate=True, colors=None, smooth_s=0.0):
    """Bin-average LED currents (dict name -> A) into dt bins on [t0, t1), quantise to uint8 with a shared full scale.
    Bin averages (not point samples) keep the light energy right for pulses shorter than dt (no aliasing).
    smooth_s > 0: glow, readout and scope show the moving average over that window (eye integration); use
    ~0.03 s for carriers above ~30 Hz, which a 60 fps display cannot reproduce. The scope is then scaled to
    the largest averaged value (scope_max_mA), so the averaged curves use the full height.
    The Hz readout counts onsets of any LED; pass rate_led=k to count only LED k (e.g. a chaser's cycle rate).
    show_rate=False hides the Hz readout (latches, one-shots).
    colors: {name: "red"|"blue"|"green"|"yellow"|"white"} sets each LED's glow and scope-trace colour (default red)."""
    t = np.asarray(t)
    tg = np.arange(t0, t1 + dt / 2, dt)

    def binavg(v):
        v = np.asarray(v) * 1e3
        c = np.concatenate([[0.0], np.cumsum(0.5 * (v[1:] + v[:-1]) * np.diff(t))])
        return np.diff(np.interp(tg, t, c)) / dt

    ys = {k: np.clip(binavg(v), 0, None) for k, v in currents.items()}
    imax = max(float(np.percentile(y, 99.5)) for y in ys.values())
    leds = [{"name": k, "color": (colors or {}).get(k, "red"),
             "b64": base64.b64encode(np.round(np.clip(y / imax, 0, 1) * 255).astype(np.uint8).tobytes()).decode()}
            for k, y in ys.items()]
    out = {"dt": dt, "n": len(tg) - 1, "imax_mA": round(imax, 2), "leds": leds}
    if smooth_s:
        k = max(1, int(round(smooth_s / dt)))
        sm = max(float(np.convolve(y, np.ones(k) / k, mode="valid").max()) for y in ys.values())
        out["smooth_s"] = float(smooth_s)
        out["scope_max_mA"] = round(min(sm * 1.1, imax), 2)
    if rate_led is not None:
        out["rate_led"] = int(rate_led)
    out["show_rate"] = bool(show_rate)
    return out


# ---------------------------------------------------------------- page
_TRANSISTOR_NOTE = ("<b>Transistor pinout.</b> The layout assumes E-B-C pin order, read left to right with the flat face toward you, "
                    "as on the 2N2222A, 2N3904, S8050 and S9013. The build order always lists a transistor's pins as E, B, C, so compare "
                    "their column numbers. If E is in the lower-numbered column (E left of C), the flat face points toward the bottom edge "
                    "of the board, toward you. If C is left of E, the flat face points toward the top edge. If your part is a BC547 or BC548 "
                    "(C-B-E order), turn every transistor 180° from what the drawing shows.")
_TRANSISTOR_NOTE_DE = ("<b>Transistor-Anschlüsse.</b> Das Layout setzt die Reihenfolge E-B-C voraus, von links nach rechts gelesen mit der flachen Seite zu dir, "
                       "wie beim 2N2222A, 2N3904, S8050 und S9013. Die Aufbauliste nennt die Beine immer in der Reihenfolge E, B, C; vergleiche die Spaltennummern. "
                       "Liegt E links von C (kleinere Spalte), zeigt die flache Seite zur unteren Brettkante, also zu dir; liegt C links von E, zur oberen Kante. "
                       "Bei BC547/BC548 (Reihenfolge C-B-E) jeden Transistor gegenüber der Zeichnung um 180° drehen.")
_CAP_NOTE_DE = ("<b>Elko-Polung.</b> Das <code>+</code>-Bein ist das längere; der Streifen auf dem Gehäuse markiert <code>−</code>.")
_CAP_NOTE = ("<b>Electrolytic polarity.</b> The <code>+</code> lead is the longer one; the stripe on the can marks <code>−</code>.")


def board_svg(svg_text):
    """Strip bblayout's title and crop the title band (keeps room for supply-lead labels if present)."""
    s = re.sub(r'<text x="7\.0" y="19\.[0-9]+"[^>]*>[^<]*</text>\n?', "", svg_text, count=1)
    top = 4 if 'class="supply-mark"' in s else 25
    return re.sub(r'width="[0-9.]+" height="[0-9.]+" viewBox="0 0 ([0-9.]+) ([0-9.]+)"',
                  lambda m: f'viewBox="0 {top} {m.group(1)} {float(m.group(2))-top}" role="img" aria-label="Breadboard layout"', s, count=1)


def build_page(spec):
    """spec keys:
    title, eyebrow, lede (html), specs [(label, value)], player (from player_data) and player_caption,
    layout (bblayout Layout: fills board_svg, instructions and supply_note, incl. supply markers on rail-less boards)
    or board_svg (raw bblayout svg text) + instructions; board_caption, charts [(title, svg, caption)],
    parts [(refs, value, note)] — value like '330', '2.2k' gets bands; prefix with '=' to print verbatim,
    instructions (Layout.instructions() text), supply_note, how (html), notes [html] (extra notes),
    has_transistors / has_electrolytics (bool; default: detected from instructions), footer (html),
    lang ("en" default, "de": German UI strings, build list and notes; write your own texts in that language).
    Player options live in player_data(): rate_led, show_rate.
    """
    if "layout" in spec:                       # derive board drawing, build list and supply note from the Layout
        from board_tools import check_tactile, draw_tactile, fix_instructions, mark_supply, supply_note
        L = spec["layout"]
        bad = check_tactile(L)
        if bad:
            raise ValueError("tactile button conflicts: " + "; ".join(bad))
        spec = dict(spec)
        spec.setdefault("board_svg", draw_tactile(mark_supply(L.svg(), L), L))
        spec.setdefault("instructions", fix_instructions(L.instructions(), L))
        spec.setdefault("supply_note", supply_note(L, lang=spec.get("lang", "en")))
    lang = spec.get("lang", "en")
    T = STR[lang]
    css = open(os.path.join(TEMPLATES, "page.css")).read() + "\n" + spec.get("extra_css", "")
    js = open(os.path.join(TEMPLATES, "player.js")).read()
    e = _html.escape
    specs = "".join(f'<div class="spec"><span>{e(a)}</span><b>{e(b)}</b></div>' for a, b in spec["specs"])
    pl = dict(spec["player"], labels={k: T[k] for k in ("play", "pause", "of", "now")})
    multi = len(pl["leds"]) > 1
    leds = "".join(f'<figure><div class="led {e(d.get("color", "red"))}"><div class="glow"></div></div><figcaption>{e(d["name"])}</figcaption></figure>'
                   for d in pl["leds"])
    cur = " · ".join(f'{e(d["name"])} <b class="cur">0.0</b> mA' for d in pl["leds"])
    player = f'''<figure class="panel player" data-key="main">
    <div class="player-head"><h3>{T["live"]}</h3><button type="button" class="play" aria-pressed="false">{T["play"]}</button></div>
    <div class="player-body{' multi' if multi else ''}">
      <div class="leds" aria-hidden="true">{leds}</div>
      <div class="scope-wrap"><canvas class="scope" aria-label="Scrolling LED current trace"></canvas></div>
    </div>
    <div class="readout">{'<span><b class="rate">–</b> Hz</span>' if pl.get("show_rate", True) else ''}<span>{cur}</span><span class="tpos">t = 0.0 s</span></div>
    <figcaption>{spec.get("player_caption", T["player_caption"])}</figcaption>
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
    has_el = spec.get("has_electrolytics", "electrolytic" in spec["instructions"])
    tn, cn = (_TRANSISTOR_NOTE_DE, _CAP_NOTE_DE) if lang == "de" else (_TRANSISTOR_NOTE, _CAP_NOTE)
    notes = ([tn] if spec.get("has_transistors", "inline-3" in spec["instructions"]) else []) \
        + ([cn] if has_el else []) + spec.get("notes", [])
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
      <h2>{T["parts"]}</h2>
      <table><tr><th>{T["ref"]}</th><th>{T["value"]}</th><th>{T["note"]}</th></tr>{"".join(rows)}</table>
    </div>
    <div>
      <h2>{T["build"]}</h2>
      <ol class="steps">{steps_html(spec["instructions"], lang)}</ol>
      <p class="lede">{spec.get("supply_note", T["supply_rail"])}</p>
    </div>
  </div>
  <div class="notes">
    <h2>{T["how"]}</h2>
    {spec["how"]}
  </div>
</section>
<section class="notes" aria-label="{T["before"]}">
  <h2>{T["before"]}</h2>
  {notes_html}
</section>
<footer>{spec["footer"]}</footer>
</div>
<script id="player-data" type="application/json">{data}</script>
<script>
{js}
</script>
'''
