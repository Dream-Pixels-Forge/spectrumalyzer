"""Tests for the bar/downbeat layer (v0.7).

Bar inference rides on the existing kick-anchored beat grid:
- a bar = 4 beats (4/4), grouped from the grid origin
- downbeats = the first beat of each bar
- downbeat confidence: high when the kick (low-band) pulse anchored the grid,
  low when the phase came from generic onsets / envelope energy
"""

from __future__ import annotations

import wave

import numpy as np
import pytest

from spectrumalyzer.analysis.beats import detect_bars, detect_beats
from spectrumalyzer.audio import load
from spectrumalyzer.model import Beat

# ---------------------------------------------------------------------------
# conftest helpers (session-scoped, reused)
# ---------------------------------------------------------------------------

@pytest.fixture
def kick_hat_pcm(tmp_path):
    """20 s drum pattern: 60 Hz kicks on the beat, hats on the off-beat."""
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
    with wave.open(str(tmp_path / "kickhat.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm16.tobytes())
    pcm, _duration, sr = load(str(tmp_path / "kickhat.wav"))
    return pcm, sr


# ---------------------------------------------------------------------------
# bars detection
# ---------------------------------------------------------------------------

def test_bars_group_every_4_beats():
    beats = [Beat(time=0.0 + i * 0.5, strength=1.0) for i in range(12)]
    bars = detect_bars(beats, bpm=120.0, confidence=0.9)
    assert len(bars) == 3
    assert [b.index for b in bars] == [0, 1, 2]
    assert [b.beat_indices for b in bars] == [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11]]
    assert [b.downbeat_time for b in bars] == [0.0, 2.0, 4.0]


def test_bars_frames_resampled():
    beats = [Beat(time=0.0 + i * 0.5, strength=1.0) for i in range(12)]
    bars = detect_bars(beats, bpm=120.0, confidence=0.9, fps=30.0)
    assert [b.frame for b in bars] == [0, 60, 120]  # 30 fps, bar = 4 * 0.5 s = 2 s = 60 frames
    assert [b.end_frame for b in bars] == [60, 120, 180]
    assert [b.downbeat_frame for b in bars] == [0, 60, 120]


def test_bars_high_confidence_with_kicks(kick_hat_pcm):
    pcm, sr = kick_hat_pcm
    result = detect_beats(pcm, sr)
    assert result["confidence"] > 0.3
    bars = detect_bars(result["beat_grid"], result["bpm"], result["confidence"])
    assert bars.confidence > 0.5, f"kick-anchored grid should give high bar confidence, got {bars.confidence}"
    # downbeats land on kicks (integer seconds in the fixture)
    for bar in bars:
        nearest_kick = round(bar.downbeat_time / 1.0) * 1.0
        assert abs(bar.downbeat_time - nearest_kick) < 0.15, (
            f"downbeat {bar.downbeat_time}s off kick by {abs(bar.downbeat_time - nearest_kick):.2f}s"
        )


def test_bars_low_confidence_fallback_for_pulseless():
    """A weak-kick track still gets bars (grouped every 4 beats),
    but downbeat confidence is flagged as low (0.0) so consumers can
    treat the downbeat phase as ambiguous (off-by-one-beat risk)."""
    beats = [Beat(time=0.0 + i * 0.5, strength=0.2) for i in range(8)]
    bars = detect_bars(beats, bpm=120.0, confidence=0.1)
    assert bars.confidence == 0.0
    assert len(bars.bars) == 2  # still produced (fallback)


def test_bars_empty_grid():
    bars = detect_bars([], bpm=120.0, confidence=0.9)
    assert len(bars.bars) == 0


def test_bars_to_dict():
    beats = [Beat(time=0.0 + i * 0.5, strength=1.0, frame=i * 15) for i in range(12)]
    bars = detect_bars(beats, bpm=120.0, confidence=0.9, fps=30.0)
    d = bars.to_dict()
    assert d["barCount"] == 3
    assert d["bars"][0]["index"] == 0
    assert d["bars"][0]["startFrame"] == 0
    assert d["bars"][0]["endFrame"] == 60
    assert d["downbeats"][0]["time"] == 0.0
    assert d["downbeats"][0]["frame"] == 0
    assert d["downbeats"][1]["frame"] == 60
    assert d["downbeats"][2]["frame"] == 120
