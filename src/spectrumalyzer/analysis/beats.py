"""Tempo estimation and beat grid construction.

Pipeline:
    PCM -> STFT -> spectral flux (onset envelope)
        -> autocorrelation tempo (with octave disambiguation)
        -> phase-locked uniform beat grid
    PCM -> STFT -> adaptive-threshold onset picking (raw hits)

The beat grid is *quantized* (uniform spacing) which is what creative timing
needs: animation loops, camera cuts and easing all want a steady pulse. The
raw onsets are kept separately as "hits" for accent-driven effects.
"""

from __future__ import annotations

import numpy as np

from spectrumalyzer.analysis.spectrum import (
    DEFAULT_HOP,
    DEFAULT_N_FFT,
    compute_stft,
    spectral_flux,
)
from spectrumalyzer.model import Bar, Bars, Beat, time_to_frame

MIN_ONSET_DISTANCE_S = 0.1
MIN_TEMPO_CONFIDENCE = 0.3  # below this, the track has no trustworthy pulse


def onset_salience(env: np.ndarray) -> float:
    """How much the envelope is dominated by isolated transients.

    Pulsed material (kicks, clicks) produces sparse spikes over a near-zero
    floor (ratio ≈ 6-10+); continuous material (pads, noise beds, sines)
    produces flat fluctuation (ratio ≈ 1-3). This — not autocorrelation
    sharpness — is what tells us whether a tempo claim is meaningful.
    """
    if len(env) == 0:
        return 0.0
    median = float(np.median(env))
    return float(env.max() / (median + 1e-9))


def _smooth(x: np.ndarray, k: int = 3) -> np.ndarray:
    if k <= 1 or len(x) < k:
        return x
    kernel = np.ones(k) / k
    return np.convolve(x, kernel, mode="same")


def onset_envelope(pcm: np.ndarray, sample_rate: int,
                   n_fft: int = DEFAULT_N_FFT, hop: int = DEFAULT_HOP,
                   stft_cache: dict | None = None) -> np.ndarray:
    """Normalized (0..1) spectral-flux onset envelope, one value per hop frame."""
    mags, _ = compute_stft(pcm, sample_rate, n_fft, hop, cache=stft_cache)
    env = spectral_flux(mags)
    peak = float(env.max())
    if peak > 0:
        env = env / peak
    return _smooth(env, 3)


def _frames_per_second(sample_rate: int, hop: int) -> float:
    return sample_rate / hop


def _autocorr_lags(x: np.ndarray, lags: np.ndarray) -> np.ndarray:
    """FFT-based autocorrelation at the requested lags only.

    O(n log n) instead of the O(n²) ``np.correlate(x, x, mode='full')``:
    the zero-padded FFT gives the full autocorrelation, and we slice out
    just the lags the tempo search needs.
    """
    n = len(x)
    m = 2 * n - 1
    # next fast length (pow2 is enough here; sizes are small)
    size = 1
    while size < m:
        size *= 2
    X = np.fft.rfft(x, n=size)
    acf_full = np.fft.irfft(X * np.conj(X), n=size)[:m]
    return acf_full[lags]


def estimate_tempo(
    pcm: np.ndarray,
    sample_rate: int,
    min_bpm: float = 60.0,
    max_bpm: float = 200.0,
    n_fft: int = DEFAULT_N_FFT,
    hop: int = DEFAULT_HOP,
    stft_cache: dict | None = None,
) -> tuple[float, float]:
    """Estimate BPM from the onset envelope via autocorrelation.

    Octave disambiguation: among lags whose score is within 0.9 of the best,
    prefer the fastest tempo (shortest period) — metronomes and most produced
    music peak at both the beat and its half-time, and DAW projects are almost
    always authored at the faster interpretation.

    Returns (bpm, confidence) with confidence in 0..1 (autocorrelation peak
    sharpness; 1 = metronome-perfect).
    """
    env = onset_envelope(pcm, sample_rate, n_fft, hop, stft_cache=stft_cache)
    fps_env = _frames_per_second(sample_rate, hop)

    min_lag = max(2, round(fps_env * 60.0 / max_bpm))
    max_lag = min(len(env) - 2, round(fps_env * 60.0 / min_bpm))
    if max_lag <= min_lag or len(env) < max_lag * 3:
        return 0.0, 0.0

    # Full-lag autocorrelation via FFT (O(n log n)); normalize by lag-0.
    lags_all = np.arange(max_lag + 1)
    acf = _autocorr_lags(env, lags_all)
    if acf[0] <= 0:
        return 0.0, 0.0
    acf = acf / acf[0]

    lags = lags_all
    scores = acf[min_lag:max_lag + 1].copy()
    if len(scores) == 0 or scores.max() <= 0:
        return 0.0, 0.0

    best_score = float(scores.max())
    # candidates within 90% of the best, choose the shortest lag (fastest BPM)
    qualified = lags[min_lag:max_lag + 1][scores >= 0.9 * best_score]
    lag = int(qualified.min())

    # parabolic refinement around the peak for sub-frame precision
    if 1 <= lag - 1 and lag + 1 < len(acf):
        y0, y1, y2 = acf[lag - 1], acf[lag], acf[lag + 1]
        denom = (y0 - 2 * y1 + y2)
        if abs(denom) > 1e-12:
            shift = 0.5 * (y0 - y2) / denom
            if abs(shift) <= 1.0:
                lag = lag + shift

    bpm = 60.0 * fps_env / lag
    bpm = float(np.clip(bpm, min_bpm, max_bpm))
    # Confidence must combine autocorrelation sharpness WITH onset salience:
    # overlapping STFT windows make the flux envelope smooth, so raw acf
    # peaks near 1.0 even for pure noise. Salience separates pulse from
    # texture — this is the number exports expose, so it must be honest.
    salience = onset_salience(env)
    salience_factor = float(np.clip((salience - 1.0) / 8.0, 0.0, 1.0))
    confidence = float(np.clip(best_score, 0.0, 1.0) * salience_factor)
    return round(bpm, 2), round(confidence, 3)


def lowband_envelope(pcm: np.ndarray, sample_rate: int, cutoff_hz: float = 250.0,
                     n_fft: int = DEFAULT_N_FFT, hop: int = DEFAULT_HOP,
                     stft_cache: dict | None = None) -> np.ndarray:
    """Onset envelope built only from low frequencies (< cutoff, the kick zone).

    Noise hats and snare transients carry far more broadband flux than a 60 Hz
    kick; anchoring the beat phase on the low band keeps the grid on the beat
    instead of the off-beat.
    """
    mags, _ = compute_stft(pcm, sample_rate, n_fft, hop, cache=stft_cache)
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)
    low = mags[freqs <= cutoff_hz, :]
    if low.shape[0] == 0:
        return np.zeros(mags.shape[1])
    env = spectral_flux(low)
    peak = float(env.max())
    if peak > 0:
        env = env / peak
    return _smooth(env, 3)


def pick_onsets(env: np.ndarray, sample_rate: int, hop: int = DEFAULT_HOP) -> list[Beat]:
    """Adaptive-threshold onset picking -> raw transient hits with strengths."""
    if len(env) < 3:
        return []
    fps_env = _frames_per_second(sample_rate, hop)
    env_max = float(env.max()) or 1.0
    min_distance = max(1, int(MIN_ONSET_DISTANCE_S * fps_env))

    # local mean over a ~1 s window as the adaptive threshold base
    win = max(3, int(fps_env))
    kernel = np.ones(win) / win
    local_mean = np.convolve(env, kernel, mode="same")
    threshold = np.maximum(0.06 * env_max, local_mean * 1.4)

    candidates: list[tuple[int, float]] = []
    for i in range(2, len(env) - 2):
        if env[i] > env[i - 1] and env[i] >= env[i + 1] and env[i] > threshold[i]:
            candidates.append((i, float(env[i])))

    # enforce min distance, keeping the strongest peaks
    candidates.sort(key=lambda c: -c[1])
    chosen: list[int] = []
    for idx, _ in candidates:
        if all(abs(idx - c) >= min_distance for c in chosen):
            chosen.append(idx)
    chosen.sort()

    return [
        Beat(time=i * hop / sample_rate, strength=round(float(env[i]) / env_max, 3))
        for i in chosen
    ]


def _phase_from_onsets(onsets, period_frames: float, fps_env: float):
    """Weighted circular mean of onset phases; returns frames or None."""
    import math

    if not onsets:
        return None
    sin_sum = 0.0
    cos_sum = 0.0
    for o in onsets:
        frac = (o.time * fps_env) % period_frames / period_frames  # 0..1
        angle = 2.0 * math.pi * frac
        weight = max(o.strength, 0.05)
        sin_sum += weight * math.sin(angle)
        cos_sum += weight * math.cos(angle)
    if sin_sum == 0 and cos_sum == 0:
        return None
    mean_angle = math.atan2(sin_sum, cos_sum)
    return (mean_angle / (2.0 * math.pi)) % 1.0 * period_frames


def _phase_from_envelope(env: np.ndarray, period_frames: float) -> tuple[float, float]:
    """Brute-force phase: maximize envelope energy sampled on the grid."""
    n = len(env)
    best_offset, best_score = 0.0, -1.0
    for offset in range(max(1, int(period_frames))):
        positions = offset + period_frames * np.arange(int((n - offset) / period_frames) + 1)
        positions = positions[positions < n]
        if len(positions) == 0:
            continue
        score = float(np.interp(positions, np.arange(n), env).sum())
        if score > best_score:
            best_score, best_offset = score, float(offset)
    return best_offset, best_score


def impact_tiers(
    beat_grid: list[Beat],
    bars: Bars | None,
    accent_quantile: float = 0.75,
) -> list[Beat]:
    """Label each beat as downbeat / accent / normal.

    Rides the existing bar grid (no new DSP):
      - **downbeat** — the first beat of each bar
      - **accent**   — the top ``accent_quantile`` of the *non-downbeat*
        beats by strength (a statistical emphasis, not a loudness claim)
      - **normal**   — everything else

    If ``bars`` is None (pulseless track / no grid) the beats are returned
    with ``tier=None`` — no invented emphasis. Mutates and returns the grid.
    """
    if not beat_grid:
        return beat_grid
    if bars is None or not bars.bars:
        for b in beat_grid:
            b.tier = None
        return beat_grid

    downbeats = set()
    for bar in bars.bars:
        if bar.beat_indices:
            downbeats.add(bar.beat_indices[0])

    for i, b in enumerate(beat_grid):
        if i in downbeats:
            b.tier = "downbeat"
        else:
            b.tier = "normal"

    # Accents: the non-downbeat beats at or above the ``accent_quantile``
    # strength threshold (a statistical emphasis, not a loudness claim).
    # A lower quantile raises the bar for "accent" coverage — i.e. it labels
    # MORE beats as accents (top 75% at q=0.25 vs top 10% at q=0.9).
    if accent_quantile < 1.0:
        non_down = [b for b in beat_grid if b.tier == "normal"]
        if non_down:
            strengths = sorted(b.strength for b in non_down)
            threshold = strengths[int(len(strengths) * accent_quantile)]
            for b in beat_grid:
                if b.tier == "normal" and b.strength >= threshold:
                    b.tier = "accent"

    return beat_grid


def detect_bars(
    beat_grid: list[Beat],
    bpm: float,
    confidence: float,
    fps: float | None = None,
    beats_per_bar: int = 4,
) -> Bars:
    """Group the beat grid into bars of ``beats_per_bar`` beats (4/4 by default).

    The downbeat of each bar is the first beat of the group. ``confidence``
    is the grid's tempo confidence — if it is below 0.3 the downbeat phase is
    ambiguous (off-by-one-beat risk) and the result's confidence is 0.0 so
    consumers can treat the first bar as a guess.
    """
    if not beat_grid:
        return Bars(bars=[], confidence=0.0)

    if confidence < MIN_TEMPO_CONFIDENCE:
        bar_confidence = 0.0
    else:
        # scale up: a confident grid gives confident bars
        bar_confidence = min(1.0, confidence)

    bars: list[Bar] = []
    beat_period = 60.0 / bpm if bpm > 0 else 0.0
    for i in range(0, len(beat_grid), beats_per_bar):
        group = beat_grid[i:i + beats_per_bar]
        downbeat = group[0]
        start_t = downbeat.time
        end_t = start_t + beats_per_bar * beat_period
        idx = len(bars)
        f = None
        ef = None
        if fps:
            f = time_to_frame(start_t, fps)
            ef = time_to_frame(end_t, fps)
        bars.append(Bar(
            index=idx,
            beat_indices=list(range(i, i + len(group))),
            downbeat_time=start_t,
            start_time=start_t,
            end_time=end_t,
            downbeat_frame=f,
            frame=f,
            end_frame=ef,
        ))

    return Bars(bars=bars, confidence=round(bar_confidence, 3))


def detect_beats(
    pcm: np.ndarray,
    sample_rate: int,
    min_bpm: float = 60.0,
    max_bpm: float = 200.0,
    duration: float = 0.0,
    stft_cache: dict | None = None,
) -> dict[str, object]:
    """Full beat analysis: onsets, BPM, phase-locked uniform beat grid."""
    env = onset_envelope(pcm, sample_rate, stft_cache=stft_cache)
    fps_env = _frames_per_second(sample_rate, DEFAULT_HOP)

    onsets = pick_onsets(env, sample_rate)
    bpm, confidence = estimate_tempo(pcm, sample_rate, min_bpm, max_bpm, stft_cache=stft_cache)

    # Honesty gate: pulseless material (ambient, pads, noise beds) yields a
    # sharp-looking but meaningless autocorrelation peak. Refuse to report a
    # tempo or a grid we do not actually hear.
    if confidence < MIN_TEMPO_CONFIDENCE:
        bpm = 0.0

    if duration <= 0:
        duration = len(pcm) / sample_rate

    grid: list[Beat] = []
    if bpm > 0 and duration > 0:
        period_frames = 60.0 / bpm * fps_env
        n = len(env)
        env_max = float(env.max()) or 1.0

        # --- phase estimation -------------------------------------------
        # Priority: (1) low-band kick pulse (drum kit anchoring),
        #           (2) weighted circular mean of onsets,
        #           (3) brute-force envelope energy.
        phase = None
        kick_env = lowband_envelope(pcm, sample_rate, stft_cache=stft_cache)
        if float(kick_env.max()) > 0.1 * max(float(env.max()), 1e-9) and duration > 0:
            phase, _score = _phase_from_envelope(kick_env, period_frames)
        if phase is None:
            phase = _phase_from_onsets(onsets, period_frames, fps_env)
        if phase is None:
            phase, _best = _phase_from_envelope(env, period_frames)

        # local fractional refinement around the phase (max env energy)
        # — direct indexing, no full-envelope np.interp scan
        lo = max(0, int(np.floor(phase - 2.0)))
        hi = min(n, int(np.ceil(phase + 2.0)))
        candidates = np.arange(lo, hi, 1)
        vals = env[candidates]
        phase = float((lo + int(np.argmax(vals))) % period_frames)

        k = 0
        while True:
            frame = phase + k * period_frames
            t = frame / fps_env
            if t > duration + 1e-6:
                break
            strength = float(np.interp(frame, np.arange(n), env)) if frame < n else 0.0
            grid.append(Beat(time=round(t, 4), strength=round(min(1.0, strength / env_max), 3)))
            k += 1

    return {
        "bpm": bpm,
        "confidence": confidence,
        "beat_grid": grid,
        "onsets": onsets,
    }
