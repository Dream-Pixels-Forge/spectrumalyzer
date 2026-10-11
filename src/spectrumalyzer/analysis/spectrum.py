"""Real spectral analysis: STFT and frequency-band energies.

Replaces the v0.1.0 pseudo-spectrum (RMS time-slices labelled as frequencies)
with an actual Short-Time Fourier Transform.
"""

from __future__ import annotations

import numpy as np

from spectrumalyzer.model import BAND_EDGES_HZ, BandData

DEFAULT_N_FFT = 1024
DEFAULT_HOP = 512


def _hann(n: int) -> np.ndarray:
    return np.hanning(n).astype(np.float64)


def compute_stft(
    pcm: np.ndarray,
    sample_rate: int,
    n_fft: int = DEFAULT_N_FFT,
    hop: int = DEFAULT_HOP,
) -> tuple[np.ndarray, int]:
    """Short-Time Fourier Transform magnitudes.

    Returns:
        (mags, hop) where mags has shape (n_fft//2 + 1, n_frames),
        DC removed per frame, Hann-windowed, zero-padded at the tail.
    """
    x = np.asarray(pcm, dtype=np.float64)
    if len(x) < n_fft:
        x = np.pad(x, (0, n_fft - len(x)))
    window = _hann(n_fft)
    n_frames = 1 + max(0, (len(x) - n_fft)) // hop
    # stride trick: build frame matrix without copying loops
    idx = np.arange(n_fft)[None, :] + hop * np.arange(n_frames)[:, None]
    frames = x[idx] * window[None, :]
    frames -= frames.mean(axis=1, keepdims=True)  # kill DC leakage
    spec = np.fft.rfft(frames, n=n_fft, axis=1)
    return np.abs(spec).T, hop  # -> (n_freq, n_frames)


def compute_bands(
    pcm: np.ndarray,
    sample_rate: int,
    n_fft: int = 4096,
    hop: int = 1024,
) -> BandData:
    """Per-analysis-frame energy in 6 creative-friendly frequency bands.

    Uses a large FFT (4096 -> ~10.8 Hz/bin at 44.1 kHz) so low bands (sub /
    bass) are actually separable — a 1024-point FFT gives 43 Hz bins, which
    smears a 100 Hz kick straight into the sub band.

    Values are 0..1, normalized per band (adaptive floor prevents noise-floor
    blow-up in bands with no signal), so every band shows its own dynamics —
    exactly what audio-reactive visuals need.
    """
    mags, _ = compute_stft(pcm, sample_rate, n_fft, hop)
    power = mags ** 2
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)
    nyquist = sample_rate / 2.0
    global_max = float(power.max()) or 1.0

    rows: list[list[float]] = []
    band_cols: list[np.ndarray] = []
    for name, lo, hi in BAND_EDGES_HZ:
        hi = min(hi, nyquist)
        if lo >= nyquist:
            band_cols.append(np.zeros(power.shape[1]))
            continue
        mask = (freqs >= lo) & (freqs < hi)
        if not mask.any():
            band_cols.append(np.zeros(power.shape[1]))
            continue
        band_cols.append(power[mask, :].sum(axis=0))

    stacked = np.stack(band_cols)  # (6, n_frames)
    normalized = np.zeros_like(stacked)
    for b in range(stacked.shape[0]):
        band_max = float(stacked[b].max())
        # adaptive floor: bands with essentially no signal stay at zero
        denom = max(band_max, global_max * 1e-3, 1e-12)
        normalized[b] = stacked[b] / denom
    normalized = np.clip(normalized, 0.0, 1.0)

    rows = normalized.T.tolist()  # -> (n_frames, 6)
    return BandData(sample_rate=sample_rate, hop=hop, matrix=rows)


def spectral_centroid(mags: np.ndarray, sample_rate: int, n_fft: int = DEFAULT_N_FFT) -> list[float]:
    """Brightness of the sound per frame, in Hz (higher = crisper/sparklier)."""
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)
    total = mags.sum(axis=0)
    total[total == 0] = 1.0
    centroid = (mags * freqs[:, None]).sum(axis=0) / total
    return centroid.tolist()


def spectral_flux(mags: np.ndarray) -> np.ndarray:
    """Positive magnitude change between consecutive frames — onset strength.

    Rectified spectral flux is the classic robust onset-detection function:
    it reacts to percussive transients (kicks, snares, clicks) regardless of
    the overall loudness of the track.
    """
    diff = np.diff(mags, axis=1)
    flux = np.maximum(diff, 0.0).sum(axis=0)
    if len(flux) == 0:
        return np.zeros(1)
    # prepend so the envelope aligns with the STFT frame count
    return np.concatenate([[0.0], flux])
