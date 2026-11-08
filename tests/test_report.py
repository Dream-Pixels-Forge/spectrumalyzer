"""Tests for the HTML visual report and the CLI."""

from __future__ import annotations

import json

from spectrumalyzer.report.html_report import render_report


def test_report_contains_canvas_and_data(click_120):
    html = render_report(str(click_120), fps=30)
    assert "<canvas" in html
    assert "spectrumalyzer" in html
    # embedded analysis payload
    assert "window.__SPECTRUMALYZER__" in html
    assert '"bpm"' in html
    assert '"beats"' in html
    # bars & downbeats layer
    assert '"bars"' in html
    assert '"downbeats"' in html
    assert 'id="bars"' in html  # bar strip canvas


def test_report_embeds_valid_json(click_120):
    html = render_report(str(click_120), fps=30)
    marker = "window.__SPECTRUMALYZER__ = "
    start = html.index(marker) + len(marker)
    end = html.index("</script>", start)
    payload = html[start:end].rstrip().rstrip(";")
    data = json.loads(payload)
    assert data["bpm"] > 0
    assert len(data["beats"]) >= 10
    assert len(data["bars"]) > 0
    assert "downbeatConfidence" in data


def test_report_band_names(click_120):
    html = render_report(str(click_120), fps=30)
    for band in ("sub", "bass", "lowMid", "mid", "highMid", "treble"):
        assert band in html
