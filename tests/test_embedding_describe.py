"""Tests for deterministic track description generation (no model needed)."""

from __future__ import annotations

from conftest import write_wav

from spectrumalyzer.embedding.describe import describe


def _result(bpm=120.0, sections=None, energy_peak=1.0, centroid=3000.0, beats=32):
    from spectrumalyzer.model import AnalysisResult, Beat, Section

    return AnalysisResult(
        path="song.mp3",
        duration=60.0,
        sample_rate=44100,
        bpm=bpm,
        bpm_confidence=0.9,
        beat_grid=[Beat(time=i * 60.0 / bpm) for i in range(beats)],
        sections=sections
        or [Section(start=0, end=30, energy=0.4, label="quiet"),
            Section(start=30, end=60, energy=energy_peak, label="peak")],
        centroid=[centroid] * 10 if centroid else [],
        loudness=[0.5] * 10,
        waveform_peaks=[0.5] * 100,
    )


def test_summary_contains_bpm_and_structure():
    d = describe(_result(bpm=128.0))
    assert "128" in d["summary"]
    assert "bpm" in d["summary"].lower()


def test_tempo_adjectives():
    assert "slow" in describe(_result(bpm=70))["summary"].lower()
    assert "fast" in describe(_result(bpm=160))["summary"].lower()
    assert "mid-tempo" in describe(_result(bpm=110))["summary"].lower()


def test_brightness_words_from_centroid():
    assert "bright" in describe(_result(centroid=7000.0))["summary"].lower()
    assert "dark" in describe(_result(centroid=300.0))["summary"].lower()


def test_sections_mentioned():
    d = describe(_result())
    assert "2" in d["description"]  # 2 sections
    assert "peak" in d["description"].lower()


def test_description_is_strings():
    d = describe(_result())
    assert isinstance(d["summary"], str) and d["summary"]
    assert isinstance(d["description"], str) and d["description"]
    assert isinstance(d["text"], str)  # combined text used for embedding


def test_text_includes_dominant_band_and_transient_density(two_sections):
    from spectrumalyzer.api import analyze
    from spectrumalyzer.embedding.describe import describe

    result = analyze(str(two_sections))
    d = describe(result)
    text = d["text"].lower()
    # measured features must appear as words the embedder can use
    assert "transients" in text
    assert "dominant" in text


def test_text_sparse_vs_dense_transients(click_120, pulseless_pad):
    from spectrumalyzer.api import analyze
    from spectrumalyzer.embedding.describe import describe

    dense = describe(analyze(str(click_120)))["text"].lower()
    sparse = describe(analyze(str(pulseless_pad)))["text"].lower()
    # 120 BPM clicks = 2 onsets/s = "steady"; pulseless pad = "sparse"
    assert "steady transients" in dense
    assert "sparse transients" in sparse


def test_tagged_text_includes_top_tags():
    from spectrumalyzer.embedding.describe import tagged_text

    d = {"summary": "s", "description": "d", "text": "s d."}
    tags = {"mood": [("calm", 0.9), ("dark", 0.5)], "energy": [("low energy", 0.8)],
            "flavor": [("ambient", 0.7)], "use": [("bed music", 0.6)]}
    text = tagged_text(d, tags)
    assert "calm" in text and "low energy" in text and "ambient" in text
    assert text.startswith("s d.")


def test_energy_feature_uses_absolute_loudness(tmp_path):
    """A quiet master and a loud master must differ in energy — per-track
    normalization alone erases the difference."""
    import numpy as np

    from spectrumalyzer.api import analyze
    from spectrumalyzer.embedding.describe import feature_vector

    sr = 44100
    t = np.arange(int(10 * sr)) / sr
    tone = np.sin(2 * np.pi * 220 * t).astype(np.float32)
    quiet = write_wav(tmp_path / "quiet.wav", tone * 0.02)
    loud = write_wav(tmp_path / "loud.wav", tone * 0.6)
    eq, el = feature_vector(analyze(str(quiet))), feature_vector(analyze(str(loud)))
    assert el["energy"] > eq["energy"] + 0.3
    assert el["energy"] > 0.7 and eq["energy"] < 0.4
