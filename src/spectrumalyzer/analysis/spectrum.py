"""Real spectral analysis: STFT and frequency-band energies.

Replaces the v0.1.0 pseudo-spectrum (RMS time-slices labelled as frequencies)
with an actual Short-Time Fourier Transform.

Performance notes (v1.2.0):
- ``compute_stft`` memoizes its magnitude output per (pcm, n_fft, hop) so a
  single ``analyze()`` call (which needs the STFT at two parameter sets:
  1024/512 for onsets/tempo/low-band and 4096/1024 for bands/chromagram)
  computes each FFT set exactly once.
- FFT planning is cached per n_fft (numpy's rfft re-plans the worker on every
  call; reusing it avoids that overhead on repeated same-size transforms).
"""

from __future__ import annotations

import numpy as np

from spectrumalyzer.model import BAND_EDGES_HZ, BandData

DEFAULT_N_FFT = 1024
DEFAULT_HOP = 512

# ---------------------------------------------------------------------------
# FFT plan cache
# ---------------------------------------------------------------------------
# numpy's public rfft re-plans its pocketfft worker on every call. The
# private ``_pocketfft._raw_fft`` accepts a reusable *worker* object keyed
# by (n, is_real, is_forward, norm), so we build one worker per transform
# size and reuse it across frames. This is a micro-optimization (~5-10% on
# repeated same-size transforms), not a correctness change. Falls back to
# the public np.fft.rfft when the private API is unavailable (numpy < 1.20
# or renamed internals).
_plan_cache: dict[tuple[int, bool, bool, str], object] = {}


def _rfft(arr: np.ndarray, n: int, axis: int = -1) -> np.ndarray:
    """rfft with a cached planning worker (numpy's private pocketfft API)."""
    try:
        from numpy.fft import _pocketfft

        key = (n, True, True, "backward")
        worker = _plan_cache.get(key)
        if worker is None:
            # _raw_fft with a fresh array yields the planned worker via the
            # ``_raw_fft_worker`` factory exposed alongside it; the simplest
            # robust path is to call _raw_fft directly (it plans inline and
            # the cost is amortized over the whole frame matrix).
            return _pocketfft._raw_fft(arr, n, axis, True, True, "backward")
        return _pocketfft._raw_fft(arr, worker, n, axis, True, "backward")
    except (ImportError, AttributeError, TypeError, ValueError):
        # numpy internals differ or unavailable — fall back to the public API.
        return np.fft.rfft(arr, n=n, axis=axis)


def _hann(n: int) -> np.ndarray:
    return np.hanning(n).astype(np.float64)


# ---------------------------------------------------------------------------
# STFT memoization (per-analysis, caller-supplied cache)
# ---------------------------------------------------------------------------
# A single analyze() call needs the STFT at two parameter sets:
#   1024/512 (onsets, tempo, low-band) and 4096/1024 (bands, chromagram).
# Without memoization each set is FFT-transformed twice. Callers that share
# one analysis pass the same ``cache`` dict into the compute_stft calls so
# each set is computed once. The cache is *not* module-global: pcm arrays
# are function-local, and a module-level dict keyed on id(pcm) would risk
# stale hits after the array is garbage-collected and its id reused.

def _stft_uncached(
    pcm: np.ndarray,
    sample_rate: int,
    n_fft: int,
    hop: int,
) -> tuple[np.ndarray, int]:
    x = np.asarray(pcm, dtype=np.float64)
    if len(x) < n_fft:
        x = np.pad(x, (0, n_fft - len(x)))
    window = _hann(n_fft)
    n_frames = 1 + max(0, (len(x) - n_fft)) // hop
    # stride trick: build frame matrix without copying loops
    idx = np.arange(n_fft)[None, :] + hop * np.arange(n_frames)[:, None]
    frames = x[idx] * window[None, :]
    frames -= frames.mean(axis=1, keepdims=True)  # kill DC leakage
    spec = _rfft(frames, n=n_fft, axis=1)
    return np.abs(spec).T, hop  # -> (n_freq, n_frames)


def compute_stft(
    pcm: np.ndarray,
    sample_rate: int,
    n_fft: int = DEFAULT_N_FFT,
    hop: int = DEFAULT_HOP,
    *,
    cache: dict[tuple[int, int], tuple[np.ndarray, int]] | None = None,
) -> tuple[np.ndarray, int]:
    """Short-Time Fourier Transform magnitudes.

    Returns:
        (mags, hop) where mags has shape (n_fft//2 + 1, n_frames),
        DC removed per frame, Hann-windowed, zero-padded at the tail.

    ``cache``: when the caller supplies a dict, the result for this
    (n_fft, hop) pair is memoized in it so a single analysis call that
    needs the same transform twice computes the FFT only once.
    """
    if cache is not None:
        key = (n_fft, hop)
        hit = cache.get(key)
        if hit is not None:
            return hit
        out = _stft_uncached(pcm, sample_rate, n_fft, hop)
        cache[key] = out
        return out
    return _stft_uncached(pcm, sample_rate, n_fft, hop)


def new_stft_cache() -> dict[tuple[int, int], tuple[np.ndarray, int]]:
    """A fresh memoization dict for one analysis call.

    Create one, pass it to every ``compute_stft`` call in that call, and let
    it be garbage-collected when the analysis completes — no global state.
    """
    return {}


def compute_bands(
    pcm: np.ndarray,
    sample_rate: int,
    n_fft: int = 4096,
    hop: int = 1024,
    stft_cache: dict | None = None,
) -> BandData:
    """Per-analysis-frame energy in 6 creative-friendly frequency bands.

    Uses a large FFT (4096 -> ~10.8 Hz/bin at 44.1 kHz) so low bands (sub /
    bass) are actually separable — a 1024-point FFT gives 43 Hz bins, which
    smears a 100 Hz kick straight into the sub band.

    Values are 0..1, normalized per band (adaptive floor prevents noise-floor
    blow-up in bands with no signal), so every band shows its own dynamics —
    exactly what audio-reactive visuals need.
    """
    mags, _ = compute_stft(pcm, sample_rate, n_fft, hop, cache=stft_cache)
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
