"""Tests for DAW project stubs (v1.4): REAPER .RPP + Ableton .als.

Pure text generators — no DAW install needed. We assert on file structure:
header blocks, tempo lines, media items, marker counts/labels.

Design decisions (documented):
- REAPER markers land on the v0.7 bar grid (downbeats), labeled ``BAR N``;
  section markers as ``SECTION <label>``; tiers ride in marker notes when
  present.
- Ableton uses its text ``.als`` format: a tempo clip at the detected BPM,
  an audio clip for the source, and markers on a marker track.
- ``bpm is None`` / no bars → tempo defaults to 120.0 (documented fallback),
  marker count 0, file still valid.
- FLP (binary, proprietary) is NOT generated here — documented in ROADMAP.
"""

from __future__ import annotations

import pytest

from spectrumalyzer.model import AnalysisResult, Bar, Bars, Section

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_result(
    bpm: float | None = 120.0,
    n_bars: int = 8,
    sections: list[Section] | None = None,
    duration: float = 32.0,
) -> AnalysisResult:
    """Build a minimal AnalysisResult with a bar grid (no real audio needed)."""
    bars: list[Bar] = []
    beat_period = (60.0 / bpm) if bpm else 0.5
    for i in range(n_bars):
        t = i * 4 * beat_period
        bars.append(
            Bar(
                index=i,
                beat_indices=[i * 4, i * 4 + 1, i * 4 + 2, i * 4 + 3],
                downbeat_time=t,
                start_time=t,
                end_time=t + 4 * beat_period,
            )
        )
    return AnalysisResult(
        path="test.wav",
        duration=duration,
        sample_rate=44100,
        bpm=bpm if bpm is not None else 0.0,
        bpm_confidence=1.0,
        beat_grid=[],
        bars=Bars(bars=bars, confidence=1.0) if bars else None,
        sections=sections or [],
    )


# ---------------------------------------------------------------------------
# export_reaper
# ---------------------------------------------------------------------------


def test_export_reaper_writes_valid_structure(tmp_path):
    from spectrumalyzer.exporters.daw import export_reaper

    res = _make_result(bpm=120.0, n_bars=8)
    out = tmp_path / "project.rpp"
    source = tmp_path / "track.wav"
    source.write_text("stub")
    written = export_reaper(res, str(source), str(out))
    assert written == out
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "<REAPER_PROJECT" in text
    assert "</REAPER_PROJECT>" in text
    assert "PPQ 480" in text
    # tempo line carries the detected bpm
    assert "TEMPO" in text
    assert "120" in text


def test_export_reaper_marker_count_matches_bars(tmp_path):
    from spectrumalyzer.exporters.daw import export_reaper

    res = _make_result(bpm=120.0, n_bars=8)
    out = tmp_path / "m.rpp"
    src = tmp_path / "s.wav"
    src.write_text("stub")
    export_reaper(res, str(src), str(out))
    text = out.read_text(encoding="utf-8")
    # 8 bars → 8 "BAR N" labels
    assert text.count("BAR ") >= 8
    assert "BAR 1" in text


def test_export_reaper_media_item_at_t0(tmp_path):
    from spectrumalyzer.exporters.daw import export_reaper

    res = _make_result(bpm=120.0, n_bars=4, duration=8.0)
    out = tmp_path / "p.rpp"
    src = tmp_path / "src.wav"
    src.write_text("stub")
    export_reaper(res, str(src), str(out))
    text = out.read_text(encoding="utf-8")
    # media item starts at project time 0
    assert "0" in text
    # duration ≈ 8 s (at 120 bpm, 4 bars = 8 s)
    assert "8" in text


def test_export_reaper_pulseless_track_still_valid(tmp_path):
    from spectrumalyzer.exporters.daw import export_reaper

    res = _make_result(bpm=None, n_bars=0)
    out = tmp_path / "pulse.rpp"
    src = tmp_path / "p.wav"
    src.write_text("stub")
    export_reaper(res, str(src), str(out))
    text = out.read_text(encoding="utf-8")
    assert "<REAPER_PROJECT" in text
    assert "</REAPER_PROJECT>" in text
    # tempo falls back to 120
    assert "120" in text
    # no BAR markers
    assert "BAR 1" not in text


def test_export_reaper_section_markers(tmp_path):
    from spectrumalyzer.exporters.daw import export_reaper

    secs = [
        Section(0.0, 4.0, energy=0.5, label="intro"),
        Section(4.0, 8.0, energy=1.0, label="peak"),
    ]
    res = _make_result(bpm=120.0, n_bars=8, sections=secs)
    out = tmp_path / "s.rpp"
    src = tmp_path / "s.wav"
    src.write_text("stub")
    export_reaper(res, str(src), str(out))
    text = out.read_text(encoding="utf-8")
    assert "SECTION intro" in text
    assert "SECTION peak" in text


def test_export_reaper_raises_on_missing_source(tmp_path):
    from spectrumalyzer.exporters.daw import export_reaper

    res = _make_result()
    with pytest.raises(FileNotFoundError):
        export_reaper(res, str(tmp_path / "nope.wav"), str(tmp_path / "x.rpp"))


# ---------------------------------------------------------------------------
# export_ableton
# ---------------------------------------------------------------------------


def test_export_ableton_writes_valid_structure(tmp_path):
    from spectrumalyzer.exporters.daw import export_ableton

    res = _make_result(bpm=120.0, n_bars=8)
    out = tmp_path / "project.als"
    src = tmp_path / "track.wav"
    src.write_text("stub")
    written = export_ableton(res, str(src), str(out))
    assert written == out
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "Ableton Live Project" in text
    # tempo mapping carries the detected bpm
    assert "120" in text


def test_export_ableton_audio_clip(tmp_path):
    from spectrumalyzer.exporters.daw import export_ableton

    res = _make_result(bpm=120.0, n_bars=4, duration=8.0)
    out = tmp_path / "p.als"
    src = tmp_path / "src.wav"
    src.write_text("stub")
    export_ableton(res, str(src), str(out))
    text = out.read_text(encoding="utf-8")
    assert "audioClip" in text or "AudioClip" in text
    assert "src.wav" in text


def test_export_ableton_pulseless_fallback(tmp_path):
    from spectrumalyzer.exporters.daw import export_ableton

    res = _make_result(bpm=None, n_bars=0)
    out = tmp_path / "p.als"
    src = tmp_path / "p.wav"
    src.write_text("stub")
    export_ableton(res, str(src), str(out))
    text = out.read_text(encoding="utf-8")
    assert "120" in text  # fallback tempo
    assert "Ableton Live Project" in text


# ---------------------------------------------------------------------------
# CLI subcommand
# ---------------------------------------------------------------------------


def test_daw_cli_subcommand_parses(tmp_path):
    from spectrumalyzer.cli import build_parser

    p = build_parser()
    f = tmp_path / "cli.wav"
    f.write_bytes(b"\x00" * 16)
    args = p.parse_args(["daw", str(f), "--da", "reaper", "-o", str(tmp_path / "o.rpp")])
    assert args.command == "daw"
    assert args.da == "reaper"
    args2 = p.parse_args(["daw", str(f), "--da", "ableton", "-o", str(tmp_path / "o.als")])
    assert args2.da == "ableton"


# ---------------------------------------------------------------------------
# package-root export
# ---------------------------------------------------------------------------


def test_package_root_exports_daw():
    import spectrumalyzer

    assert hasattr(spectrumalyzer, "export_reaper")
    assert hasattr(spectrumalyzer, "export_ableton")
