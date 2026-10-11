"""Tests for the beat/tempo engine."""

from __future__ import annotations

import pytest

from spectrumalyzer.audio import load
from spectrumalyzer.analysis.beats import detect_beats, estimate_tempo


@pytest.mark.parametrize(
    "fixture, expected_bpm",
    [("click_120", 120.0), ("click_90", 90.0), ("click_140", 140.0)],
)
def test_tempo_within_3_bpm(fixture, expected_bpm, request):
    path = request.getfixturevalue(fixture)
    pcm, duration, sr = load(str(path))
    bpm, confidence = estimate_tempo(pcm, sr)
    assert abs(bpm - expected_bpm) <= 3.0, f"got {bpm:.1f}, want {expected_bpm}"
    assert 0.0 <= confidence <= 1.0


@pytest.mark.parametrize("fixture", ["click_120", "click_90", "click_140"])
def test_beat_grid_hits_every_click(fixture, request):
    path = request.getfixturevalue(fixture)
    pcm, duration, sr = load(str(path))
    result = detect_beats(pcm, sr)
    beats = result["beat_grid"]
    assert len(beats) >= 10
    # Uniform grid: consecutive deltas must be near-identical
    deltas = [beats[i + 1].time - beats[i].time for i in range(len(beats) - 1)]
    assert max(deltas) - min(deltas) < 0.05
    # The critical property: every click (0.5 + k*period) lands ON the grid
    # (within 60 ms). Grid phase is ambiguous modulo the period, so anchoring
    # at t=0 is as valid as anchoring at the first click.
    grid_times = [b.time for b in beats]
    period = 60.0 / result["bpm"]
    click_t = 0.5
    while click_t < duration - 0.1:
        nearest = min(grid_times, key=lambda g: abs(g - click_t))
        assert abs(nearest - click_t) < 0.06, f"click {click_t:.3f}s vs grid {nearest:.3f}s"
        click_t += period


def test_onsets_near_clicks(click_120):
    pcm, _, sr = load(str(click_120))
    result = detect_beats(pcm, sr)
    onsets = result["onsets"]
    assert len(onsets) >= 10
    # every onset should be within 60 ms of an exact 120 BPM click position
    for onset in onsets:
        nearest_click = round((onset.time - 0.5) / 0.5) * 0.5 + 0.5
        assert abs(onset.time - nearest_click) < 0.06, f"{onset.time} vs {nearest_click}"


def test_onset_strengths_normalized(click_120):
    pcm, _, sr = load(str(click_120))
    result = detect_beats(pcm, sr)
    for onset in result["onsets"]:
        assert 0.0 <= onset.strength <= 1.0


def test_bpm_range_hints(click_120):
    """min/max BPM hints constrain the autocorrelation search."""
    pcm, _, sr = load(str(click_120))
    bpm_low, _ = estimate_tempo(pcm, sr, min_bpm=60, max_bpm=100)
    # 120 BPM track with a 60-100 window should report 60 (half-time) not 120
    assert 55 <= bpm_low <= 100


def _make_kick_hat_track(path):
    """Drum pattern: kicks on the beat (1 kHz too high for lowband), hats off-beat.

    Kicks = 60 Hz decaying sine every 1.0 s, hats = noise bursts at +0.5 s.
    Hats have HIGHER spectral flux than kicks, so a naive phase lock lands on
    the off-beat. The grid must lock onto the KICKS (low-frequency energy).
    """
    import numpy as np
    import wave as _wave

    sr = 44100
    n = 20 * sr
    rng = np.random.default_rng(5)
    audio = np.zeros(n)
    kick_t = np.arange(int(0.06 * sr)) / sr
    kick = np.sin(2 * np.pi * 60 * kick_t) * np.exp(-kick_t * 30)
    hat_t = np.arange(int(0.02 * sr)) / sr
    hat = rng.standard_normal(len(hat_t)) * np.exp(-hat_t * 200)
    for beat in np.arange(1.0, 20.0, 0.5):
        i = int(beat * sr)
        if beat % 1.0 == 0:
            audio[i:i + len(kick)] += kick * 0.9
        else:
            audio[i:i + len(hat)] += hat * 0.8
    audio += rng.standard_normal(n) * 0.005
    pcm16 = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    with _wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm16.tobytes())
    return path


def test_beat_grid_locks_to_kicks_not_hats(tmp_path):
    """Regression: hats (off-beat noise) have more flux than kicks, but the
    beat grid must anchor on the low-frequency kick pulse."""
    path = _make_kick_hat_track(tmp_path / "kickhat.wav")
    pcm, duration, sr = load(str(path))
    result = detect_beats(pcm, sr)
    beats = result["beat_grid"]
    assert len(beats) >= 15
    # every KICK (integer seconds) must land on the grid within 60 ms
    for kick_t in [1.0 + k for k in range(0, 18)]:
        nearest = min(beats, key=lambda b: abs(b.time - kick_t)).time
        assert abs(nearest - kick_t) < 0.06, f"kick {kick_t}s vs grid {nearest}s"
