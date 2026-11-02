"""Trimmer tests — window selection logic + real ffmpeg cuts."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from spectrumalyzer.model import AnalysisResult, Beat, Section
from spectrumalyzer.trimmer import (
    TrimSelection,
    default_output_path,
    select_trim_window,
    trim_audio,
)


def make_result(
    duration: float,
    loudness: list[float] | None = None,
    onsets: list[Beat] | None = None,
    sections: list[Section] | None = None,
    beat_grid: list[Beat] | None = None,
    bpm: float = 120.0,
) -> AnalysisResult:
    return AnalysisResult(
        path="fake.wav",
        duration=duration,
        sample_rate=44100,
        bpm=bpm,
        bpm_confidence=0.5,
        beat_grid=beat_grid or [],
        onsets=onsets or [],
        sections=sections or [],
        loudness=loudness or [],
    )


def test_picks_loudest_window():
    loudness = [0.1] * 1500 + [0.9] * 1500  # 30s: quiet half, loud half
    sel = select_trim_window(make_result(30.0, loudness=loudness), 10.0)
    assert sel.start >= 15.0
    assert sel.end <= 30.0
    assert sel.trimmed


def test_short_track_is_not_trimmed():
    sel = select_trim_window(make_result(30.0), 60.0)
    assert sel.start == 0.0 and sel.end == 30.0
    assert not sel.trimmed
    assert any("already short" in r for r in sel.reasons)


def test_onset_density_attracts_window():
    loud = [0.5] * 3000
    dense = [Beat(20.0 + i * 0.25, strength=0.9) for i in range(40)]  # 4/s in [20,30]
    sparse = [Beat(0.0 + i * 5.0, strength=0.4) for i in range(2)]  # [0,5]
    sel = select_trim_window(
        make_result(30.0, loudness=loud, onsets=dense + sparse), 10.0
    )
    assert sel.start >= 15.0, f"dense-onset window should win, got start={sel.start}"


def test_section_energy_attracts_window():
    loud = [0.5] * 3000
    sections = [
        Section(0.0, 15.0, 0.3, "quiet"),
        Section(15.0, 30.0, 1.0, "peak"),
    ]
    onsets = [Beat(2.5), Beat(7.5), Beat(17.5), Beat(22.5), Beat(27.5)]
    sel = select_trim_window(
        make_result(30.0, loudness=loud, onsets=onsets, sections=sections), 10.0
    )
    assert sel.start >= 15.0


def test_cuts_snap_to_beat_grid():
    beats = [Beat(0.5 + i * 0.5) for i in range(59)]  # 120 bpm grid
    onsets = [Beat(0.5 + i * 0.5) for i in range(59)]
    sel = select_trim_window(
        make_result(30.0, loudness=[0.5] * 3000, beat_grid=beats, onsets=onsets, bpm=120.0),
        5.0,
    )
    # every beat is a multiple of 0.5 s
    assert abs(sel.start % 0.5) < 1e-6, f"start {sel.start} not on the beat grid"
    assert abs(sel.end % 0.5) < 1e-6, f"end {sel.end} not on the beat grid"


def test_no_snap_without_beats():
    sel = select_trim_window(make_result(30.0, loudness=[0.5] * 3000), 10.0)
    assert "no beat grid" in " ".join(sel.reasons) or not any(
        "snapped" in r for r in sel.reasons
    )


def test_selection_to_dict():
    sel = TrimSelection(1.0, 91.0, ["r"])
    d = sel.to_dict()
    assert d["duration"] == pytest.approx(90.0)
    assert d["trimmed"] is True


def test_default_output_path():
    assert default_output_path("/a/b/song.mp3") == "/a/b/song-short.mp3"


def test_trim_window_length_respected():
    sel = select_trim_window(make_result(300.0, loudness=[0.5] * 30000), 120.0)
    # beat snapping may shift by at most one beat period
    assert abs(sel.duration - 120.0) <= 60.0 / 120.0 * 2


# ---- real ffmpeg integration -----------------------------------------------

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)


@pytest.fixture
def server():
    from spectrumalyzer.mcp_server import create_server

    return create_server()


@requires_ffmpeg
def test_ffmpeg_cut_two_sections(two_sections, tmp_path):
    from spectrumalyzer.api import analyze

    result = analyze(str(two_sections))
    assert result.duration > 55.0  # 30 quiet + 30 loud
    sel = select_trim_window(result, 30.0)
    out = tmp_path / "short.wav"
    trim_audio(str(two_sections), str(out), sel.start, sel.end)

    assert out.exists()
    dur = float(
        subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(out),
            ],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    )
    assert 28.0 <= dur <= 32.0, f"cut duration {dur}s not ~30s"


@requires_ffmpeg
def test_cli_trim_end_to_end(two_sections, tmp_path):
    from spectrumalyzer.cli import main

    out = tmp_path / "short.mp3"
    rc = main(["trim", str(two_sections), "--length", "30", "-o", str(out)])
    assert rc == 0
    assert out.exists() and out.stat().st_size > 0


@requires_ffmpeg
def test_cli_trim_preview_writes_nothing(two_sections, tmp_path, capsys):
    from spectrumalyzer.cli import main

    rc = main(["trim", str(two_sections), "--length", "30", "--preview", "-q"])
    assert rc == 0
    assert not list(tmp_path.iterdir())


@requires_ffmpeg
def test_cli_trim_short_track_is_noop(click_120, tmp_path):
    from spectrumalyzer.cli import main

    out = tmp_path / "short.mp3"
    rc = main(["trim", str(click_120), "--length", "60", "-o", str(out), "-q"])
    assert rc == 0
    assert not out.exists()


@requires_ffmpeg
def test_mcp_trim_audio(two_sections, tmp_path, server):
    import asyncio
    import json

    out = tmp_path / "short.wav"
    result, _meta = asyncio.run(
        server.call_tool(
            "trim_audio",
            {"path": str(two_sections), "length_s": 30.0, "output": str(out)},
        )
    )
    data = json.loads(result[0].text)
    assert "error" not in data, data
    assert data["output"] == str(out)
    assert Path(out).exists()
    assert 0.5 <= data["selection"]["start"] <= 35.0  # the loud half wins


@requires_ffmpeg
def test_mcp_trim_audio_missing_file(server):
    import asyncio
    import json

    result, _meta = asyncio.run(
        server.call_tool("trim_audio", {"path": "/nope/missing.mp3"})
    )
    data = json.loads(result[0].text)
    assert data["error"] == "file_not_found"
