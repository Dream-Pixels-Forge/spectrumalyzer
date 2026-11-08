"""High-level public API — one call to analyze anything."""

from __future__ import annotations

import math

import numpy as np

from spectrumalyzer._version import __version__
from spectrumalyzer.analysis.beats import detect_bars, detect_beats
from spectrumalyzer.analysis.features import loudness_envelope, waveform_peaks
from spectrumalyzer.analysis.harmony import detect_key
from spectrumalyzer.analysis.spectrum import compute_bands, spectral_centroid
from spectrumalyzer.analysis.structure import detect_sections
from spectrumalyzer.audio import DEFAULT_SAMPLE_RATE, load
from spectrumalyzer.model import AnalysisResult


def analyze(
    path: str,
    fps: float | None = None,
    bands: bool = True,
    sections: bool = True,
    key: bool = True,
    min_bpm: float = 60.0,
    max_bpm: float = 200.0,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    waveform_buckets: int = 400,
) -> AnalysisResult:
    """Analyze an audio file and return a rich AnalysisResult.

    Args:
        path: audio file path (any format ffmpeg reads).
        fps: when set, all data gains frame numbers at this rate
             (creative tools work in frames, not seconds).
        bands: include per-frame frequency-band energies.
        sections: attempt song-structure segmentation.
        min_bpm / max_bpm: tempo search range hints.
        sample_rate: internal decode rate (44100 default).
        waveform_buckets: resolution of the visualization waveform.
        key: include musical key detection (Krumhansl-Schmuckler over the
             chromagram) with Camelot + palette suggestion.
    """
    pcm, duration, sr = load(path, sample_rate)
    if len(pcm) == 0:
        raise ValueError(f"No decodable audio in {path}")

    beats = detect_beats(pcm, sr, min_bpm=min_bpm, max_bpm=max_bpm, duration=duration)

    band_data = compute_bands(pcm, sr) if bands else None
    if band_data is not None:

        mags, _ = __import__("spectrumalyzer.analysis.spectrum", fromlist=["compute_stft"]).compute_stft(pcm, sr)
        centroid = spectral_centroid(mags, sr)
    else:
        centroid = []
    loudness = loudness_envelope(pcm, sr)
    # true loudness (dBFS) — per-track normalization above erases absolute
    # level, which is real musical information (a quiet ballad vs a loud master)
    rms = float(np.sqrt(np.mean(np.asarray(pcm, dtype=np.float64) ** 2)))
    loudness_db = 20.0 * math.log10(max(rms, 1e-6))

    result = AnalysisResult(
        path=str(path),
        duration=duration,
        sample_rate=sr,
        bpm=float(beats["bpm"]),
        bpm_confidence=float(beats["confidence"]),
        beat_grid=beats["beat_grid"],      # type: ignore[arg-type]
        onsets=beats["onsets"],            # type: ignore[arg-type]
        bands=band_data,
        centroid=centroid,
        loudness=loudness,
        waveform_peaks=waveform_peaks(pcm, waveform_buckets),
        loudness_db=loudness_db,
        fps=fps,
        metadata={
            "version": __version__,
            "analyzer": "spectrumalyzer",
            "engine": "spectral-flux + autocorrelation tempo",
        },
    )
    if sections:
        result.sections = detect_sections(pcm, sr, duration)
    result.bars = detect_bars(
        beat_grid=result.beat_grid,
        bpm=result.bpm,
        confidence=result.bpm_confidence,
        fps=fps,
    )
    if key:
        result.key = detect_key(pcm, sr)
    return result
