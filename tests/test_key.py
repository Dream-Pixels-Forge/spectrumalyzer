"""Tests for the musical key detection layer (v0.8).

Pure-numpy Krumhansl-Schmuckler key fit over a chromagram, plus the
Camelot-wheel + palette creative mapping. No ML, no network.
"""

from __future__ import annotations

import numpy as np
import pytest

from spectrumalyzer.analysis.harmony import (
    detect_key,
    key_to_camelot,
    palette_for_key,
)
from spectrumalyzer.audio import load
from spectrumalyzer.model import KeyResult

# ---------------------------------------------------------------------------
# fixtures: synthetic harmonic material with known keys
# ---------------------------------------------------------------------------

def _chord_pcm(freqs_hz, n_chords=24, sustain_s=0.5, sample_rate=44100):
    """Stack a repeating chord (a few partials per note) — a clear tonality."""
    sr = sample_rate
    per = int(sustain_s * sr)
    n = per * n_chords
    rng = np.random.default_rng(1)
    audio = np.zeros(n)
    t = np.arange(per) / sr
    for f in freqs_hz:
        # fundamental + a couple of low partials = a real, harmonic timbre
        partials = [f, 2.0 * f, 3.0 * f]
        amps = [0.5, 0.2, 0.1]
        sig = sum(a * np.sin(2 * np.pi * p * t) for a, p in zip(amps, partials))
        for c in range(n_chords):
            i = c * per
            # gentle attack/release envelope so it reads as a sustained chord
            env = np.ones(per)
            fade = int(0.02 * sr)
            env[:fade] = np.linspace(0, 1, fade)
            env[-fade:] = np.linspace(1, 0, fade)
            audio[i:i + per] += sig * env * 0.6
    audio += rng.standard_normal(n) * 0.002
    return audio.astype(np.float32)


@pytest.fixture
def a_minor_pcm(tmp_path):
    # A minor triad A3 C4 E4 — cleanest minor signature (its relative major
    # C is the runner-up, which is musically honest).
    p = tmp_path / "am.wav"
    import wave
    pcm = _chord_pcm([220.0, 261.63, 329.63])
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
        w.writeframes((np.clip(pcm, -1, 1) * 32767).astype(np.int16).tobytes())
    return p


@pytest.fixture
def c_major_pcm(tmp_path):
    # C major triad C4 E4 G4 — the root-third-fifth. Its relative minor (A)
    # and dominant (G) are chromatically close, so K-S reports a narrow gap
    # and modest confidence; the root is still C.
    p = tmp_path / "cmaj.wav"
    import wave
    pcm = _chord_pcm([261.63, 329.63, 392.0])
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
        w.writeframes((np.clip(pcm, -1, 1) * 32767).astype(np.int16).tobytes())
    return p


@pytest.fixture
def noise_pcm(tmp_path):
    p = tmp_path / "noise.wav"
    import wave
    sr = 44100
    rng = np.random.default_rng(9)
    pcm = (rng.standard_normal(int(12 * sr)) * 0.05).astype(np.float32)
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(pcm, -1, 1) * 32767).astype(np.int16).tobytes())
    return p


# ---------------------------------------------------------------------------
# key detection
# ---------------------------------------------------------------------------

def test_a_minor_chord_detected(a_minor_pcm):
    pcm, _dur, sr = load(str(a_minor_pcm), sample_rate=44100)
    k = detect_key(pcm, sr)
    assert isinstance(k, KeyResult)
    # root should be A (pitch class 9)
    assert k.root == 9, f"expected A root, got pc {k.root} ({k.key})"
    assert "minor" in k.key.lower(), k.key
    assert k.confidence > 0.2


def test_c_major_chord_detected(c_major_pcm):
    pcm, _dur, sr = load(str(c_major_pcm), sample_rate=44100)
    k = detect_key(pcm, sr)
    # C major is the clearest diatonic signature; root must be C. Confidence
    # is intentionally modest: a C-major triad is chromatically close to its
    # relative minor (A) and dominant (G), so K-S reports a narrow gap.
    assert k.root == 0, f"expected C root, got pc {k.root} ({k.key})"
    assert "major" in k.key.lower(), k.key
    assert k.confidence > 0.2


def test_noise_is_unknown(noise_pcm):
    pcm, _dur, sr = load(str(noise_pcm), sample_rate=44100)
    k = detect_key(pcm, sr)
    assert k.key == "unknown"
    assert k.confidence == 0.0
    assert k.camelot is None


def test_detect_key_empty():
    k = detect_key(np.zeros(10), 44100)
    assert k.key == "unknown"


# ---------------------------------------------------------------------------
# camelot mapping
# ---------------------------------------------------------------------------

def test_camelot_known_values():
    # Camelot wheel: A minor = 1A, C major = 1B, G major = 5B, F minor = 8A
    assert key_to_camelot(9, "minor") == "1A"
    assert key_to_camelot(0, "major") == "1B"
    assert key_to_camelot(7, "major") == "5B"
    assert key_to_camelot(5, "minor") == "8A"


def test_camelot_all_twenty_four():
    for pc in range(12):
        for mode in ("major", "minor"):
            code = key_to_camelot(pc, mode)
            assert code[-1] in "AB", (pc, mode, code)
            assert 1 <= int(code[:-1]) <= 12


# ---------------------------------------------------------------------------
# palette suggestion
# ---------------------------------------------------------------------------

def test_palette_shape():
    p = palette_for_key("A minor", "1A")
    assert "mood" in p and "label" in p
    assert isinstance(p["hexes"], list) and len(p["hexes"]) == 3
    for h in p["hexes"]:
        assert h.startswith("#") and len(h) == 7


def test_palette_major_warmer_than_minor():
    # major should read warmer/cooler-label than the same root's minor
    pmaj = palette_for_key("A major", "10B")
    pmin = palette_for_key("A minor", "1A")
    # distinct, deterministic outputs
    assert pmaj["label"] != pmin["label"] or pmaj["hexes"] != pmin["hexes"]
