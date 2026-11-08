"""Tests for all exporters — frame math, parseability, creative-tool syntax."""

from __future__ import annotations

import csv
import io
import json
import xml.etree.ElementTree as ET

import pytest

from spectrumalyzer.exporters import (
    FORMATS,
    export,
    export_filename,
    extra_files,
)
from spectrumalyzer.model import AnalysisResult, Bar, Bars, Beat, Section


@pytest.fixture
def result() -> AnalysisResult:
    """Small deterministic result: 120 BPM, beats every 0.5 s, fps=30, bars every 4 beats."""
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
        metadata={"version": "0.2.0", "analyzer": "spectrumalyzer"},
    )
    for b in r.beat_grid:
        b.frame = round(b.time * 30)
    return r


def test_json_key_export():
    import wave

    import numpy as np

    from spectrumalyzer.api import analyze
    from spectrumalyzer.exporters import export

    def _chord_pcm(freqs_hz, n_chords=24, sustain_s=0.5, sample_rate=44100):
        sr = sample_rate
        per = int(sustain_s * sr)
        n = per * n_chords
        audio = np.zeros(n)
        t = np.arange(per) / sr
        for f in freqs_hz:
            partials = [f, 2.0 * f, 3.0 * f]
            amps = [0.5, 0.2, 0.1]
            sig = sum(a * np.sin(2 * np.pi * p * t) for a, p in zip(amps, partials))
            for c in range(n_chords):
                i = c * per
                env = np.ones(per)
                fade = int(0.02 * sr)
                env[:fade] = np.linspace(0, 1, fade)
                env[-fade:] = np.linspace(1, 0, fade)
                audio[i:i + per] += sig * env * 0.6
        return audio.astype(np.float32)

    import os
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        p = tf.name
    with wave.open(p, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
        w.writeframes((np.clip(_chord_pcm([220.0, 261.63, 329.63]), -1, 1) * 32767).astype(np.int16).tobytes())
    r = analyze(p, fps=30)
    os.unlink(p)
    data = json.loads(export(r, "json"))
    assert data["key"] != "unknown"
    assert "keyConfidence" in data
    assert data["camelot"] is not None
    assert "palette" in data


def test_json_key_absent_when_unknown():
    import os
    import tempfile
    import wave

    import numpy as np

    from spectrumalyzer.api import analyze
    from spectrumalyzer.exporters import export
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        p = tf.name
    sr = 44100
    pcm = (np.random.default_rng(9).standard_normal(int(12 * sr)) * 0.05).astype(np.float32)
    with wave.open(p, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(pcm, -1, 1) * 32767).astype(np.int16).tobytes())
    r = analyze(p, fps=30)
    os.unlink(p)
    data = json.loads(export(r, "json"))
    assert data["key"] == "unknown"
    assert data["keyConfidence"] == 0.0
    assert "camelot" not in data


def test_mcp_lean_payload_has_key():
    import asyncio
    import wave

    import numpy as np

    from spectrumalyzer.mcp_server import create_server

    def _chord_pcm(freqs_hz, n_chords=24, sustain_s=0.5, sample_rate=44100):
        sr = sample_rate
        per = int(sustain_s * sr)
        n = per * n_chords
        audio = np.zeros(n)
        t = np.arange(per) / sr
        for f in freqs_hz:
            partials = [f, 2.0 * f, 3.0 * f]
            amps = [0.5, 0.2, 0.1]
            sig = sum(a * np.sin(2 * np.pi * p * t) for a, p in zip(amps, partials))
            for c in range(n_chords):
                i = c * per
                env = np.ones(per)
                fade = int(0.02 * sr)
                env[:fade] = np.linspace(0, 1, fade)
                env[-fade:] = np.linspace(1, 0, fade)
                audio[i:i + per] += sig * env * 0.6
        return audio.astype(np.float32)

    import os
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        p = tf.name
    with wave.open(p, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
        w.writeframes((np.clip(_chord_pcm([220.0, 261.63, 329.63]), -1, 1) * 32767).astype(np.int16).tobytes())
    server = create_server()
    result, _meta = asyncio.run(server.call_tool("analyze_audio", {"path": p, "fps": 30}))
    os.unlink(p)
    data = json.loads(result[0].text)
    assert "key" in data
    assert data["key"] != "unknown"
    assert "camelot" in data
    assert "palette" in data
    expected = {"json", "remotion", "hyperframes", "ae", "csv", "fcpxml"}
    assert expected == set(FORMATS.keys())


def test_json_export(result):
    data = json.loads(export(result, "json"))
    assert data["bpm"] == 120.0
    assert data["beats"][0]["frame"] == 0
    assert data["beats"][1]["frame"] == 15  # 0.5 s * 30 fps
    assert data["durationInFrames"] == 135  # 4.5 s * 30 fps


def test_remotion_export_frames(result):
    data = json.loads(export(result, "remotion"))
    assert data["bpm"] == 120.0
    assert data["fps"] == 30
    assert data["durationInFrames"] == 135
    assert data["beatsInFrames"] == [0, 15, 30, 45, 60, 75, 90, 105, 120]
    assert data["beatPeriodInFrames"] == 15


def test_remotion_ts_snippet(result):
    extras = extra_files(result, "remotion")
    assert "useBeats" in "".join(extras.values())
    assert "useVideoConfig" in "".join(extras.values())


def test_hyperframes_export(result):
    data = json.loads(export(result, "hyperframes"))
    assert data["bpm"] == 120.0
    assert "timeline" in data
    assert data["timeline"]["fps"] == 30
    events = data["timeline"]["events"]
    # frame 0 has beat, bar and downbeat — all tied on (frame, type),
    # so "bar" < "beat" alphabetically puts bar first
    assert events[0]["frame"] == 0
    assert events[0]["type"] == "bar"
    beat_events = [e for e in events if e["type"] == "beat"]
    assert beat_events[0]["frame"] == 0


def test_hyperframes_snippet(result):
    extras = extra_files(result, "hyperframes")
    joined = "".join(extras.values())
    assert "hf-seek" in joined or "data-" in joined


def test_aftereffects_jsx(result):
    jsx = export(result, "ae")
    # AE scripting: comp markers via setValueAtTime(seconds)
    assert "setValueAtTime" in jsx
    assert "comp.markerProperty" in jsx or "markerProperty" in jsx
    # beat times present as seconds (0.5 s -> 0.5)
    assert "0.5" in jsx
    # it should be valid-ish JS: balanced braces
    assert jsx.count("{") == jsx.count("}")


def test_csv_export(result):
    text = export(result, "csv")
    rows = list(csv.DictReader(io.StringIO(text)))
    bar_rows = [r for r in rows if r["type"] in ("bar", "downbeat")]
    assert len(rows) == len(result.beat_grid) + len(result.onsets) + len(result.sections) + len(bar_rows)
    assert {"index", "type", "time", "frame", "label"} <= set(rows[0].keys())
    beat_rows = [r for r in rows if r["type"] == "beat"]
    assert beat_rows[1]["frame"] == "15"
    assert float(beat_rows[1]["time"]) == 0.5


def test_fcpxml_export(result):
    text = export(result, "fcpxml")
    root = ET.fromstring(text)
    assert root.tag == "fcpxml"
    markers = root.findall(".//marker")
    assert len(markers) >= len(result.beat_grid)
    # FCPXML uses rational time: 0.5 s at 30 fps = 15/30s
    start_vals = [m.get("start") for m in markers]
    assert "15/30s" in start_vals


def test_filenames(result):
    assert export_filename(result, "json").endswith(".json")
    assert export_filename(result, "remotion").endswith(".remotion.json")
    assert export_filename(result, "ae").endswith(".jsx")
    assert export_filename(result, "csv").endswith(".csv")
    assert export_filename(result, "fcpxml").endswith(".fcpxml")
    assert export_filename(result, "hyperframes").endswith(".hyperframes.json")


def test_unknown_format_raises(result):
    with pytest.raises(KeyError):
        export(result, "wav")


def test_no_fps_raises_for_frame_exports():
    r = AnalysisResult(path="x", duration=1.0, sample_rate=44100, bpm=120.0,
                       bpm_confidence=0.5)
    with pytest.raises(ValueError):
        export(r, "remotion")  # frame-based export without fps


def test_export_filename_idempotent_suffix(result):
    """Regression: -o beats.json with format json must not become .json.json."""
    assert export_filename(result, "json", base="beats.json") == "beats.json"
    assert export_filename(result, "csv", base="beats.csv") == "beats.csv"
    assert export_filename(result, "csv", base="beats") == "beats.markers.csv"
    assert export_filename(result, "remotion", base="beats") == "beats.remotion.json"
