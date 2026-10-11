"""Tests for song structure segmentation and feature extraction."""

from __future__ import annotations

from spectrumalyzer.analysis.features import loudness_envelope, waveform_peaks
from spectrumalyzer.analysis.structure import detect_sections
from spectrumalyzer.audio import load


def test_two_sections_detected(two_sections):
    pcm, duration, sr = load(str(two_sections))
    sections = detect_sections(pcm, sr, duration)
    assert len(sections) >= 2
    # Boundary near the 30 s mark
    boundary = sections[0].end
    assert abs(boundary - 30.0) < 3.0, f"boundary at {boundary:.2f}, expected ~30"


def test_section_energy_ordering(two_sections):
    pcm, duration, sr = load(str(two_sections))
    sections = detect_sections(pcm, sr, duration)
    energies = [s.energy for s in sections]
    # the loud section must have strictly more energy than the quiet one
    assert max(energies) > 2 * min(energies)
    # labels rank with energy: loudest section labelled "peak"
    loudest = max(sections, key=lambda s: s.energy)
    assert loudest.label == "peak"


def test_sections_cover_track(two_sections):
    pcm, duration, sr = load(str(two_sections))
    sections = detect_sections(pcm, sr, duration)
    assert sections[0].start <= 1.0
    assert sections[-1].end >= duration - 2.0
    for a, b in zip(sections, sections[1:]):
        assert b.start >= a.end - 0.5  # contiguous-ish


def test_loudness_envelope_shape(bass_sine):
    pcm, _duration, sr = load(str(bass_sine))
    env = loudness_envelope(pcm, sr)
    assert len(env) >= 10
    assert all(0.0 <= v <= 1.0 for v in env)


def test_loudness_envelope_reflects_energy(two_sections):
    pcm, _duration, sr = load(str(two_sections))
    env = loudness_envelope(pcm, sr)
    half = len(env) // 2
    quiet = sum(env[:half]) / max(1, half)
    loud = sum(env[half:]) / max(1, len(env) - half)
    assert loud > 2 * quiet


def test_waveform_peaks(bass_sine):
    pcm, _duration, _sr = load(str(bass_sine))
    peaks = waveform_peaks(pcm, buckets=200)
    assert len(peaks) == 200
    assert all(0.0 <= v <= 1.0 for v in peaks)
    assert max(peaks) > 0.1  # a 0.5-amplitude sine has real peaks
