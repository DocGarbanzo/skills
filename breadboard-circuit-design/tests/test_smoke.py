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


@pytest.mark.parametrize("key", ["blink", "breathe", "fm", "ps", "res", "n555", "s555"])
def test_example_layouts_verify(key):
    from bblayout import Layout
    L = Layout.load(os.path.join(EXAMPLES, f"{key}_layout.json"))
    assert L.verify().ok
    assert L.svg().startswith("<svg")


def test_svg_renders_to_png(tmp_path):
    import cairosvg
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
