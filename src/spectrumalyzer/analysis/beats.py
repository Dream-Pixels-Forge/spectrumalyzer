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
from spectrumalyzer.model import Beat

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
                   n_fft: int = DEFAULT_N_FFT, hop: int = DEFAULT_HOP) -> np.ndarray:
    """Normalized (0..1) spectral-flux onset envelope, one value per hop frame."""
    mags, _ = compute_stft(pcm, sample_rate, n_fft, hop)
    env = spectral_flux(mags)
    peak = float(env.max())
    if peak > 0:
        env = env / peak
    return _smooth(env, 3)


def _frames_per_second(sample_rate: int, hop: int) -> float:
    return sample_rate / hop


def estimate_tempo(
    pcm: np.ndarray,
    sample_rate: int,
    min_bpm: float = 60.0,
    max_bpm: float = 200.0,
    n_fft: int = DEFAULT_N_FFT,
    hop: int = DEFAULT_HOP,
) -> tuple[float, float]:
    """Estimate BPM from the onset envelope via autocorrelation.

    Octave disambiguation: among lags whose score is within 0.9 of the best,
    prefer the fastest tempo (shortest period) — metronomes and most produced
    music peak at both the beat and its half-time, and DAW projects are almost
    always authored at the faster interpretation.

    Returns (bpm, confidence) with confidence in 0..1 (autocorrelation peak
    sharpness; 1 = metronome-perfect).
    """
    env = onset_envelope(pcm, sample_rate, n_fft, hop)
    fps_env = _frames_per_second(sample_rate, hop)

    min_lag = max(2, round(fps_env * 60.0 / max_bpm))
    max_lag = min(len(env) - 2, round(fps_env * 60.0 / min_bpm))
    if max_lag <= min_lag or len(env) < max_lag * 3:
        return 0.0, 0.0

    acf = np.correlate(env, env, mode="full")[len(env) - 1:]
    if acf[0] <= 0:
        return 0.0, 0.0
    acf = acf / acf[0]

    lags = np.arange(min_lag, max_lag + 1)
    scores = acf[min_lag:max_lag + 1].copy()
    if len(scores) == 0 or scores.max() <= 0:
        return 0.0, 0.0

    best_score = float(scores.max())
    # candidates within 90% of the best, choose the shortest lag (fastest BPM)
    qualified = lags[scores >= 0.9 * best_score]
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
                     n_fft: int = DEFAULT_N_FFT, hop: int = DEFAULT_HOP) -> np.ndarray:
    """Onset envelope built only from low frequencies (< cutoff, the kick zone).

    Noise hats and snare transients carry far more broadband flux than a 60 Hz
    kick; anchoring the beat phase on the low band keeps the grid on the beat
    instead of the off-beat.
    """
    mags, _ = compute_stft(pcm, sample_rate, n_fft, hop)
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


def detect_beats(
    pcm: np.ndarray,
    sample_rate: int,
    min_bpm: float = 60.0,
    max_bpm: float = 200.0,
    duration: float = 0.0,
) -> dict[str, object]:
    """Full beat analysis: onsets, BPM, phase-locked uniform beat grid."""
    env = onset_envelope(pcm, sample_rate)
    fps_env = _frames_per_second(sample_rate, DEFAULT_HOP)

    onsets = pick_onsets(env, sample_rate)
    bpm, confidence = estimate_tempo(pcm, sample_rate, min_bpm, max_bpm)

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
        kick_env = lowband_envelope(pcm, sample_rate)
        if float(kick_env.max()) > 0.1 * max(float(env.max()), 1e-9) and duration > 0:
            phase, _score = _phase_from_envelope(kick_env, period_frames)
        if phase is None:
            phase = _phase_from_onsets(onsets, period_frames, fps_env)
        if phase is None:
            phase, _best = _phase_from_envelope(env, period_frames)

        # local fractional refinement around the phase (max env energy)
        candidates = np.arange(phase - 2.0, phase + 2.01, 0.25)
        vals = []
        for pos in candidates:
            pos_mod = pos % period_frames
            vals.append(float(np.interp(pos_mod, np.arange(n), env)) if pos_mod < n else 0.0)
        phase = float(candidates[int(np.argmax(vals))] % period_frames)

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
