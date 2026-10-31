"""Board helpers that bblayout 0.0.1 lacks, mainly for boards without power rails (the 170-point "mini").

- supply_points(layout): where the +5 V and GND supply leads go ({"VCC": "a9", "GND": "a2"}).
  On rail boards these are the rails ("T+", "T-"). On rail-less boards the VCC hole is the one bblayout's
  SPICE export uses (its instructions can silently omit VCC when the first VCC strip it looks at is full).
- supply_note(layout): the "connect the supply" sentence for the build list.
- fix_instructions(text, layout): replaces bblayout's supply line with a correct one.
- mark_supply(svg, layout): draws labelled supply-lead markers on the board SVG.
"""
import re

from bblayout import Hole

SUPPLY_NETS = ("VCC", "GND")
_ROW_Y = {"T+": -3.0, "T-": -2.0, "a": 0.0, "b": 1.0, "c": 2.0, "d": 3.0, "e": 4.0,
          "f": 7.0, "g": 8.0, "h": 9.0, "i": 10.0, "j": 11.0, "B-": 13.0, "B+": 14.0}


def _net_holes(layout, net):
    holes = []
    for ref, pin in layout.schematic.nets().get(net, []):
        pl = layout.placements.get(ref)
        if pl and pin in pl.pins:
            holes.append(pl.pins[pin])
    for w in layout.wires:
        if w.net == net:
            holes += [w.start, w.end]
    return holes


def supply_points(layout):
    """{"VCC": hole, "GND": hole} as strings."""
    board = layout.board
    if board.rails:
        out = {}
        for rail, net in layout.rail_nets.items():
            if net in SUPPLY_NETS and net not in out and rail.startswith("T"):
                out[net] = rail
        return out
    spice = layout.spice(analysis=".tran 1m 1m", supplies={"VCC": 5})
    m = re.search(r"supply lead into (\S+)", spice)
    out = {"VCC": m.group(1)} if m else {}
    occupied = layout.occupancy()
    for net in SUPPLY_NETS:
        if net in out:
            continue
        for h in _net_holes(layout, net):
            free = [x for x in board.strip_holes(board.strip_of(h)) if x not in occupied and str(x) not in out.values()]
            if free:
                out[net] = str(free[0])
                break
    missing = [n for n in SUPPLY_NETS if n not in out and layout.schematic.nets().get(n)]
    if missing:
        raise ValueError(f"no free hole for the {', '.join(missing)} supply lead: leave one hole free in a {missing[0]} strip")
    return out


def supply_note(layout, lang="en"):
    p = supply_points(layout)
    if layout.board.rails:
        if lang == "de":
            return "Versorgung zuletzt anschließen: +5 V an die obere <code>+</code>-Schiene, Masse an die obere <code>−</code>-Schiene."
        return "Connect the supply last: +5 V to the top <code>+</code> rail, ground to the top <code>−</code> rail."
    if lang == "de":
        return (f"Versorgung zuletzt anschließen: +5-V-Leitung in <code>{p['VCC']}</code>, Masse in <code>{p['GND']}</code> "
                "(in der Zeichnung markiert). Dieses Brett hat keine Versorgungsschienen; nur diese beiden Löcher führen Spannung.")
    return (f"Connect the supply last: +5 V lead into <code>{p['VCC']}</code>, ground lead into <code>{p['GND']}</code> "
            "(marked on the drawing). This board has no power rails, so these two holes are the only supply connections.")


def fix_instructions(text, layout):
    """Replace bblayout's (possibly incomplete) supply line on rail-less boards."""
    if layout.board.rails:
        return text
    p = supply_points(layout)
    text = re.sub(r"\n*Connect the power supply leads:.*$", "", text.rstrip(), flags=re.S)
    return text + f"\n\nConnect the power supply leads: VCC -> {p['VCC']}, GND -> {p['GND']}.\n"


def mark_supply(svg, layout, scale=14.0):
    """Add +5 V / GND supply-lead markers to an untrimmed bblayout SVG (rail-less boards only).

    Each lead is drawn as a short coloured wire from its hole out over the nearest board edge, ending in a
    label outside the board (above for rows a-e, below for rows f-j). The SVG grows at the bottom if needed.
    """
    if layout.board.rails:
        return svg
    p = supply_points(layout)
    s = scale
    x0, y0, y1 = 1 - 2.0, -2.5, 13.5
    pad_top = 2.0 if layout.schematic.name else 0.0
    X = lambda x: round((x - x0) * s, 2)
    Y = lambda y: round((y - y0 + pad_top) * s, 2)
    top_edge, bot_edge = Y(y0), Y(y1)
    grow = 0.0
    marks = []
    for net, col in (("VCC", "#d62828"), ("GND", "#222")):
        h = Hole.parse(p[net])
        cx, cy = X(h.col), Y(_ROW_Y[h.row])
        label = "+5 V" if net == "VCC" else "GND"
        if h.row in "abcde":
            ly = top_edge - s * 0.55                      # label centre, just above the board
        else:
            ly = bot_edge + s * 0.75
            grow = max(grow, s * 1.5)
        marks.append(f'<g class="supply-mark"><line x1="{cx}" y1="{cy}" x2="{cx}" y2="{ly:.1f}" stroke="{col}" stroke-width="{s*0.22:.1f}" stroke-linecap="round"/>'
                     f'<circle cx="{cx}" cy="{cy}" r="{s*0.32:.1f}" fill="{col}"/>'
                     f'<rect x="{cx - s*1.2:.1f}" y="{ly - s*0.45:.1f}" width="{s*2.4:.1f}" height="{s*0.9:.1f}" rx="{s*0.2:.1f}" fill="{col}"/>'
                     f'<text x="{cx}" y="{ly + s*0.22:.1f}" font-size="{s*0.62:.1f}" fill="#fff" text-anchor="middle">{label}</text></g>')
    if grow:
        m = re.search(r'width="([0-9.]+)" height="([0-9.]+)" viewBox="0 0 ([0-9.]+) ([0-9.]+)"', svg)
        w, h = float(m.group(1)), float(m.group(2)) + grow
        svg = svg.replace(m.group(0), f'width="{w}" height="{h}" viewBox="0 0 {w} {h}"', 1)
    return svg.replace("</svg>", "".join(marks) + "</svg>")


# ---------------------------------------------------------------- 4-leg tactile buttons (6 x 6 mm)
def _tactile(layout):
    """Buttons placed as bblayout two-lead parts in row e (or f) with span 2: the real part has four legs
    straddling the channel (e_c, e_c+2, f_c, f_c+2); each across-channel pair is connected inside the button."""
    out = []
    for ref, pl in layout.placements.items():
        comp = layout.schematic.components.get(ref)
        if comp is None or comp.kind != "button":
            continue
        h = sorted(pl.pins.values(), key=lambda x: x.col)
        if len(h) == 2 and h[0].row == h[1].row and h[0].row in "ef" and h[1].col - h[0].col == 2:
            other = "f" if h[0].row == "e" else "e"
            out.append((ref, h[0].col, h[1].col, h[0].row, other))
    return out


def check_tactile(layout):
    """Issues if a strip that a tactile button bridges across the channel is used by anything else."""
    issues = []
    tac = _tactile(layout)
    if not tac:
        return issues
    occ = {}
    for ref, pl in layout.placements.items():
        for h in pl.pins.values():
            occ.setdefault(str(h), ref)
    for w in layout.wires:
        occ.setdefault(str(w.start), "wire"); occ.setdefault(str(w.end), "wire")
    for ref, c1, c2, row, other in tac:
        rows = "fghij" if other == "f" else "abcde"
        for c in (c1, c2):
            used = [f"{r}{c}" for r in rows if f"{r}{c}" in occ and occ[f"{r}{c}"] != ref]
            if used:
                issues.append(f"{ref}: its leg {other}{c} joins column {c} across the channel, but {', '.join(used)} is used "
                              f"({occ[used[0]]}); keep that strip free or on the same net")
    return issues


def draw_tactile(svg, layout, scale=14.0):
    """Redraw buttons as 6 x 6 mm tactile switches straddling the channel: body over the channel,
    four visible legs in e_c, e_c+2, f_c, f_c+2 (the across-channel leg pairs are connected inside)."""
    tac = _tactile(layout)
    if not tac:
        return svg
    s = scale
    rails = layout.board.rails
    x0 = 1 - 2.0
    y0 = -6.0 if rails else -2.5
    pad_top = 2.0 if layout.schematic.name else 0.0
    X = lambda x: round((x - x0) * s, 2)
    Y = lambda y: round((y - y0 + pad_top) * s, 2)
    g = []
    for ref, c1, c2, row, other in tac:
        # drop bblayout's own small button symbol (square + dot + label) for this ref
        # (its lead line just before the group, then the group with square, dot and label)
        svg = re.sub(r'(<line [^>]*stroke="#a9a9a9"[^>]*/>\n)?<g><title>' + re.escape(ref) + r'</title>(?:(?!<g>).)*?fill="#444"/>(?:(?!<g>).)*?</g>\n?',
                     "", svg, count=1, flags=re.S)
        xa, xb = X(c1), X(c2)
        ye, yf = Y(_ROW_Y["e"]), Y(_ROW_Y["f"])
        cx, cy = (xa + xb) / 2, (ye + yf) / 2
        half = s * 1.18                                   # 6 mm body = 2.36 hole pitches, centred over the channel
        parts = []
        for x in (xa, xb):                                # four legs: bent metal tabs from the body to the holes
            for y, edge in ((ye, cy - half), (yf, cy + half)):
                parts.append(f'<line x1="{x}" y1="{edge:.1f}" x2="{x}" y2="{y}" stroke="#b8b8b8" stroke-width="{s*0.28:.1f}"/>'
                             f'<rect x="{x - s*0.24:.1f}" y="{y - s*0.24:.1f}" width="{s*0.48:.1f}" height="{s*0.48:.1f}" fill="#c9c9c9" stroke="#777" stroke-width="0.8"/>')
        parts.append(f'<rect x="{cx - half:.1f}" y="{cy - half:.1f}" width="{2*half:.1f}" height="{2*half:.1f}" rx="{s*0.12:.1f}" fill="#3a3a3a" stroke="#111"/>'
                     f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{s*0.62:.1f}" fill="#151515" stroke="#555"/>'
                     f'<text x="{cx + half + s*0.35:.1f}" y="{cy + s*0.2:.1f}" font-size="{s*0.6:.1f}" fill="#222">{ref}</text>')
        g.append('<g class="tactile">' + "".join(parts) + '</g>')
    return svg.replace("</svg>", "".join(g) + "</svg>")


# ---------------------------------------------------------------- readable part labels
_LABEL = re.compile(r'<text x="([0-9.]+)" y="([0-9.]+)" font-size="([0-9.]+)" fill="#222" text-anchor="middle">([^<]+)</text>')


def _overlap(a, b, pad=1.0):
    return not (a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1])


def tidy_labels(svg, scale=14.0):
    """Make bblayout's part labels readable: a halo in the board colour hides the holes behind each label,
    and a label that would overlap another label or a part body moves below, right or left of its part.
    Labels are moved to the end of the SVG so no later lead or wire is drawn over them; they also avoid
    column numbers, pin letters and rail names."""
    s = scale
    obstacles = []
    for m in re.finditer(r'<circle cx="([0-9.]+)" cy="([0-9.]+)" r="([0-9.]+)"', svg):
        cx, cy, r = map(float, m.groups())
        if r >= s * 0.4:                                   # LED / capacitor / electrolytic bodies
            obstacles.append(((cx, cy), (cx - r, cy - r, cx + r, cy + r)))
    for m in re.finditer(r'<rect x="([0-9.-]+)" y="([0-9.-]+)" width="([0-9.]+)" height="([0-9.]+)" rx="([0-9.]+)"[^>]*?(?:rotate\(([-0-9.]+) ([0-9.]+) ([0-9.]+)\))?', svg):
        x, y, w, h = map(float, m.groups()[:4])
        if w > 300 or h > 200:                             # board outline
            continue
        cx, cy = x + w / 2, y + h / 2
        if m.group(6) and abs(abs(float(m.group(6))) % 180 - 90) < 1:
            w, h = h, w
        obstacles.append(((cx, cy), (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)))
    for m in re.finditer(r'<text x="([0-9.]+)" y="([0-9.]+)" font-size="([0-9.]+)"[^>]*?(?:text-anchor="(\w+)")?[^>]*>([^<]*)</text>', svg):
        if _LABEL.fullmatch(m.group(0)):
            continue
        x, y, fs = float(m.group(1)), float(m.group(2)), float(m.group(3))
        w = 0.6 * fs * max(len(m.group(5)), 1)
        x0 = x - w / 2 if m.group(4) == "middle" else (x - w if m.group(4) == "end" else x)
        obstacles.append(((-1e9, -1e9), (x0, y - fs * 0.8, x0 + w, y + fs * 0.2)))   # column numbers, pin letters, rail names
    placed = []
    plates = []

    def fix(m):
        x, y, fs, text = float(m.group(1)), float(m.group(2)), float(m.group(3)), m.group(4)
        mx, my = x, y + s * 0.7                            # the part's centre
        w, h = 0.62 * fs * len(text) + 2, fs
        cands = [(mx, my - s * 0.7), (mx, my + s * 1.05 + fs * 0.35), (mx + s * 0.75 + w / 2, my + fs * 0.35),
                 (mx - s * 0.75 - w / 2, my + fs * 0.35), (mx, my - s * 1.25)]
        best = cands[0]
        for cx, cy in cands:
            box = (cx - w / 2, cy - h * 0.8, cx + w / 2, cy + h * 0.2)
            own = lambda o: abs(o[0][0] - mx) < 1 and abs(o[0][1] - my) < 1
            if not any(_overlap(box, p) for p in placed) and not any(_overlap(box, o[1], 0) for o in obstacles if not own(o)):
                best = (cx, cy)
                break
        cx, cy = best
        placed.append((cx - w / 2, cy - h * 0.8, cx + w / 2, cy + h * 0.2))
        bx0, by0, bx1, by1 = placed[-1]
        # opaque plate in the board colour (works in every renderer; paint-order halos do not, e.g. cairosvg)
        plates.append(f'<rect x="{bx0 - 1:.1f}" y="{by0 - 1:.1f}" width="{bx1 - bx0 + 2:.1f}" height="{by1 - by0 + 2:.1f}" rx="2" fill="#f2efe6" fill-opacity="0.92"/>'
                      f'<text x="{cx:.1f}" y="{cy:.1f}" font-size="{fs}" fill="#222" text-anchor="middle" font-weight="600">{text}</text>')
        return ""
    svg = _LABEL.sub(fix, svg)
    return svg.replace("</svg>", '<g class="labels">' + "".join(plates) + "</g></svg>")   # labels on top of everything


def render_board(layout):
    """Board SVG for pages: readable labels, tactile buttons, supply-lead markers (rail-less boards)."""
    return tidy_labels(mark_supply(draw_tactile(layout.svg(), layout), layout))   # tactile first: it removes bblayout's button symbol and label
