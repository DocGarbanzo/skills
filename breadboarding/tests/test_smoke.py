"""Smoke tests: environment, ngspice, bundled models, and the example layouts.

Run with:  uv run pytest -q
"""
import json
import os
import shutil
import subprocess
import sys

import numpy as np
import pytest

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL, "scripts"))
EXAMPLES = os.path.join(SKILL, "examples")


def test_ngspice_installed():
    assert shutil.which("ngspice"), "ngspice not found: apt install ngspice / brew install ngspice"
    out = subprocess.run(["ngspice", "-v"], capture_output=True, text=True).stdout
    assert "ngspice" in out


@pytest.mark.parametrize("key", ["blink", "breathe", "fm", "ps", "res", "n555", "s555", "alt"])
def test_example_layouts_verify(key):
    from bblayout import Layout
    L = Layout.load(os.path.join(EXAMPLES, f"{key}_layout.json"))
    assert L.verify().ok
    assert L.svg().startswith("<svg")


def test_svg_renders_to_png(tmp_path):
    try:
        import cairosvg
    except OSError as e:  # raised when the system cairo library cannot be found
        pytest.fail("cairo library not found: brew install cairo / apt install libcairo2 "
                    "(macOS Apple Silicon: export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib). " + str(e))
    from bblayout import Layout
    svg = Layout.load(os.path.join(EXAMPLES, "blink_layout.json")).svg()
    out = tmp_path / "blink.png"
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(out), output_width=700)
    assert out.stat().st_size > 1000


@pytest.mark.parametrize("key,T,step,expected_period", [
    ("blink", "14", "2m", 1.33),
    ("n555", "14", "0.2m", 0.96),
])
def test_as_built_period(key, T, step, expected_period, tmp_path, monkeypatch):
    from sim_tools import as_built, flashes
    monkeypatch.chdir(tmp_path)
    t, i = as_built(key, T=T, step=step, layout_path=os.path.join(EXAMPLES, f"{key}_layout.json"))
    starts, _ = flashes(t, i, t0=4)
    period = float(np.diff(starts).mean())
    assert abs(period - expected_period) / expected_period < 0.05, period


def test_as_built_two_leds(tmp_path, monkeypatch):
    """Alternating blinker: both LEDs sensed; 1 Hz blink, LEDs never on together."""
    from sim_tools import as_built, flashes
    monkeypatch.chdir(tmp_path)
    t, I = as_built("alt", T="16", step="2m", layout_path=os.path.join(EXAMPLES, "alt_layout.json"))
    assert set(I) == {"D1", "D2"}
    m = t > 4
    both = (I["D1"][m] > 3e-3) & (I["D2"][m] > 3e-3)
    assert both.mean() < 0.002
    s, _ = flashes(t, np.maximum(I["D1"], I["D2"]), t0=4)
    period = float(np.median(np.diff(s)))
    assert abs(period - 0.99) / 0.99 < 0.05, period


def test_as_built_reports_ngspice_failure(tmp_path, monkeypatch):
    from sim_tools import SimError, as_built
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SimError):
        as_built("blink", T="1", step="bogus", layout_path=os.path.join(EXAMPLES, "blink_layout.json"))


def test_make_page(tmp_path):
    from bblayout import Layout
    from make_page import bands, build_page, chart_svg, player_data
    assert bands("330").count("<i") == 3 and bands("2.2k").count("#d62828") == 3
    L = Layout.load(os.path.join(EXAMPLES, "alt_layout.json"))
    t = np.linspace(0, 4, 4001)
    i1 = 0.01 * (np.sin(2 * np.pi * t) > 0)
    spec = dict(title="Test", eyebrow="x", lede="x", specs=[("A", "1")],
                player=player_data(t, {"D1": i1, "D2": i1[::-1]}, 0, 4),
                board_svg=L.svg(), board_caption="x",
                charts=[("I", chart_svg(t, [(i1 * 1e3, ""), (i1[::-1] * 1e3, "t2")], 12, (0, 5, 10), 4, 1), "x")],
                parts=[("R1", "330", "x"), ("C1", "=22 µF", "x")], instructions=L.instructions(),
                how="<p>x</p>", footer="x")
    html = build_page(spec)
    assert html.count('class="led"') == 2 and "@media print" in html and "player-data" in html
