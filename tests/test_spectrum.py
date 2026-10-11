"""Tests for spectrum / band analysis — real FFT, real frequency content."""

from __future__ import annotations

from spectrumalyzer.analysis.spectrum import BAND_EDGES_HZ, compute_bands, compute_stft
from spectrumalyzer.audio import load


def test_stft_shape_and_frequencies(bass_sine):
    pcm, duration, sr = load(str(bass_sine))
    mags, _hop = compute_stft(pcm, sr, n_fft=1024, hop=512)
    n_freq, n_frames = mags.shape
    # half-spectrum bins for a real signal
    assert n_freq == 513          # 1024-point FFT -> 512 + 1 bins
    assert n_frames >= int(duration * sr / 512) - 2
    assert n_frames <= int(duration * sr / 512) + 2


def test_bass_sine_dominates_bass_band(bass_sine):
    pcm, _, sr = load(str(bass_sine))
    bands = compute_bands(pcm, sr)
    # find loudest analysis frame and check bass wins
    sums = [sum(row) for row in bands.matrix]
    idx = sums.index(max(sums))
    row = bands.matrix[idx]
    bass_idx = 1  # "bass" is BAND_NAMES[1]
    assert row[bass_idx] == max(row), f"bass should dominate for 100 Hz sine: {row}"


def test_treble_sine_dominates_treble_band(treble_sine):
    pcm, _, sr = load(str(treble_sine))
    bands = compute_bands(pcm, sr)
    sums = [sum(row) for row in bands.matrix]
    idx = sums.index(max(sums))
    row = bands.matrix[idx]
    treble_idx = 5  # "treble" is BAND_NAMES[5]
    assert row[treble_idx] == max(row), f"treble should dominate for 8 kHz sine: {row}"


def test_band_values_normalized(bass_sine):
    pcm, _, sr = load(str(bass_sine))
    bands = compute_bands(pcm, sr)
    for row in bands.matrix:
        for v in row:
            assert 0.0 <= v <= 1.0


def test_band_names_and_edges_consistent():
    names = [e[0] for e in BAND_EDGES_HZ]
    assert names == ["sub", "bass", "lowMid", "mid", "highMid", "treble"]
    for (_, lo, hi) in BAND_EDGES_HZ:
        assert lo < hi


def test_band_frame_duration(bass_sine):
    pcm, _, sr = load(str(bass_sine))
    bands = compute_bands(pcm, sr)
    assert abs(bands.frame_duration - 1024 / sr) < 1e-9
