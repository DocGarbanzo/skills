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


def supply_note(layout):
    p = supply_points(layout)
    if layout.board.rails:
        return ("Connect the supply last: +5 V to the top <code>+</code> rail, ground to the top <code>−</code> rail.")
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
