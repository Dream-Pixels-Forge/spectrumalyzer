"""Simple per-frame features: loudness envelope and waveform peaks (for viz)."""

from __future__ import annotations

import numpy as np


def loudness_envelope(pcm: np.ndarray, sample_rate: int, hop: int = 512) -> list[float]:
    """Normalized RMS loudness per analysis frame (0..1)."""
    n = len(pcm)
    n_frames = n // hop
    if n_frames < 1:
        return [0.0] if n else []
    frames = pcm[: n_frames * hop].reshape(n_frames, hop)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    peak = float(rms.max()) or 1.0
    return np.clip(rms / peak, 0.0, 1.0).tolist()


def waveform_peaks(pcm: np.ndarray, buckets: int = 400) -> list[float]:
    """Max-abs amplitude per bucket — a compact waveform for visualization."""
    n = len(pcm)
    if n == 0 or buckets <= 0:
        return []
    buckets = min(buckets, n)
    trimmed = pcm[: (n // buckets) * buckets]
    bucketed = trimmed.reshape(buckets, -1)
    peaks = np.abs(bucketed).max(axis=1)
    peak = float(peaks.max()) or 1.0
    return np.clip(peaks / peak, 0.0, 1.0).tolist()
