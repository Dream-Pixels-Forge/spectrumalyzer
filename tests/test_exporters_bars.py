"""v0.7 bar-layer tests for all six exporters (frame math + presence).

Each exporter gains bar / downbeat content — the bar-layer addition to the
v0.2 exporter contract.
"""

from __future__ import annotations

import csv
import io
import json
import xml.etree.ElementTree as ET

import pytest

from spectrumalyzer.exporters import export, extra_files
from spectrumalyzer.model import AnalysisResult, Bar, Bars, Beat, Section


@pytest.fixture
def result() -> AnalysisResult:
    """120 BPM, 4-beat bars @ 30 fps — bars every 2 s (60 frames)."""
    beats = [Beat(time=0.0 + i * 0.5, strength=0.8) for i in range(9)]
    r = AnalysisResult(
        path="song.mp3",
        duration=4.5,
        sample_rate=44100,
        bpm=120.0,
        bpm_confidence=0.9,
        beat_grid=beats,
        onsets=[Beat(time=0.12, strength=1.0), Beat(time=1.37, strength=0.6)],
        sections=[
            Section(start=0.0, end=2.0, energy=0.4, label="quiet"),
            Section(start=2.0, end=4.5, energy=1.0, label="peak"),
        ],
        bars=Bars(
            bars=[
                Bar(index=0, beat_indices=[0, 1, 2, 3], downbeat_time=0.0,
                    start_time=0.0, end_time=2.0, frame=0, end_frame=60, downbeat_frame=0),
                Bar(index=1, beat_indices=[4, 5, 6, 7], downbeat_time=2.0,
                    start_time=2.0, end_time=4.0, frame=60, end_frame=120, downbeat_frame=60),
                Bar(index=2, beat_indices=[8], downbeat_time=4.0,
                    start_time=4.0, end_time=4.5, frame=120, end_frame=135, downbeat_frame=120),
            ],
            confidence=0.9,
        ),
        fps=30.0,
        metadata={"version": "0.7.0", "analyzer": "spectrumalyzer"},
    )
    for b in r.beat_grid:
        b.frame = round(b.time * 30)
    return r


# --- json -------------------------------------------------------------------

def test_json_bars(result):
    data = json.loads(export(result, "json"))
    assert data["barCount"] == 3
    assert data["downbeatConfidence"] == 0.9
    assert data["bars"][0]["index"] == 0
    assert data["bars"][0]["startFrame"] == 0
    assert data["bars"][0]["endFrame"] == 60
    assert data["bars"][1]["startFrame"] == 60
    assert data["bars"][2]["startFrame"] == 120
    assert data["downbeats"][0]["frame"] == 0
    assert data["downbeats"][1]["frame"] == 60
    assert data["downbeats"][2]["frame"] == 120


# --- remotion ---------------------------------------------------------------

def test_remotion_bars(result):
    data = json.loads(export(result, "remotion"))
    assert data["barsInFrames"] == [0, 60, 120]
    assert data["downbeatsInFrames"] == [0, 60, 120]
    assert data["barPeriodInFrames"] == 60
    assert data["barCount"] == 3
    assert data["downbeatConfidence"] == 0.9


def test_remotion_hook_has_bar_helpers(result):
    extras = extra_files(result, "remotion")
    joined = "".join(extras.values())
    assert "useBarIndex" in joined
    assert "useBarProgress" in joined
    assert "useIsOnBar" in joined
    assert "BARS" in joined


# --- hyperframes ------------------------------------------------------------

def test_hyperframes_bar_events(result):
    data = json.loads(export(result, "hyperframes"))
    events = data["timeline"]["events"]
    bar_events = [e for e in events if e["type"] == "bar"]
    downbeat_events = [e for e in events if e["type"] == "downbeat"]
    assert len(bar_events) == 3
    assert [e["frame"] for e in bar_events] == [0, 60, 120]
    assert [e["index"] for e in bar_events] == [0, 1, 2]
    assert len(downbeat_events) == 3
    assert [e["frame"] for e in downbeat_events] == [0, 60, 120]


# --- aftereffects -----------------------------------------------------------

def test_aftereffects_bar_markers(result):
    jsx = export(result, "ae")
    assert "BAR 1" in jsx
    assert "BAR 2" in jsx
    assert "BAR 1" in jsx  # downbeat marker shares the BAR prefix
    # bars come after beats in the output — check the loop
    assert "bars[i]" in jsx or "bars.length" in jsx
    # balanced braces (valid-ish JS)
    assert jsx.count("{") == jsx.count("}")


# --- csv --------------------------------------------------------------------

def test_csv_bar_rows(result):
    text = export(result, "csv")
    rows = list(csv.DictReader(io.StringIO(text)))
    bar_rows = [r for r in rows if r["type"] == "bar"]
    downbeat_rows = [r for r in rows if r["type"] == "downbeat"]
    assert len(bar_rows) == 3
    assert [r["frame"] for r in bar_rows] == ["0", "60", "120"]
    assert [r["label"] for r in bar_rows] == ["bar 1", "bar 2", "bar 3"]
    assert len(downbeat_rows) == 3
    assert [r["frame"] for r in downbeat_rows] == ["0", "60", "120"]
    assert [r["label"] for r in downbeat_rows] == [
        "BAR 1 ↓", "BAR 2 ↓", "BAR 3 ↓"
    ]


# --- fcpxml -----------------------------------------------------------------

def test_fcpxml_bar_markers(result):
    text = export(result, "fcpxml")
    root = ET.fromstring(text)
    markers = root.findall(".//marker")
    values = [m.get("value") for m in markers]
    assert "BAR 1" in values
    assert "BAR 2" in values
    assert "BAR 1 ↓" in values
    assert "BAR 2 ↓" in values
    # frame math: bar 2 starts at 2.0 s = 60/30 s in rational time
    bar2 = next(m for m in markers if m.get("value") == "BAR 2")
    assert bar2.get("start") == "60/30s"
    down1 = next(m for m in markers if m.get("value") == "BAR 1 ↓")
    assert down1.get("start") == "0/30s"

