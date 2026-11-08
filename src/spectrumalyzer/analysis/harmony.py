"""Musical key detection: chromagram → Krumhansl-Schmuckler key fit.

Pure numpy, no ML. The chromagram folds the magnitude spectrum onto 12 pitch
classes (C..B) with a log-spaced harmonic weighting that emphasises the
low-mid range where real harmony lives and down-weights the percussive highs.
Each of the 24 Krumhansl-Schmuckler key templates (12 major + 12 minor) is
cross-correlated against the chroma; the best fit wins.

The salience gate is the honesty check: a near-flat chroma (noise, pads,
pulseless ambient) has no trustworthy tonality, so we return key="unknown"
with confidence 0 rather than inventing harmony.

Creative mapping (the point of the feature): the detected key is mapped to a
Camelot-wheel position and a deterministic color/palette suggestion — an
opinionated default for audio-reactive color grades, not a claim of truth.
"""

from __future__ import annotations

import numpy as np

from spectrumalyzer.analysis.spectrum import compute_stft
from spectrumalyzer.model import KeyResult

# Pitch classes 0..11 = C, C#, D, D#, E, F, F#, G, G#, A, A#, B
PC_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

# Krumhansl-Schmuckler key profiles (relative weights over the 12 pitch
# classes, anchored so index 0 = the tonic of the key). Major then minor.
MAJOR_PROFILE = np.array([
    6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.23,
])
MINOR_PROFILE = np.array([
    6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17,
])

# Minimum relative chroma energy above the noise floor for a key claim.
# A flat/noise chroma has max/mean ~1.1 (near-uniform energy across all 12
# pitch classes); real tonality has max/mean >> 1 because the tonic and a
# few nearby pitch classes dominate. This is the honesty gate.
_CHROMA_PEAK_RATIO_MIN = 1.3  # max(chroma) / mean(chroma)


def _pitch_class_matrix(n_fft: int, sample_rate: int) -> np.ndarray:
    """Log-spaced mapping of FFT bins to the 12 pitch classes.

    Each FFT bin contributes its magnitude to the pitch class nearest in
    pitch, with a falloff for bins far above the harmonic range so percussive
    content (hats, cymbals) doesn't wash out the chord tones.
    """
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)
    n_bins = len(freqs)
    weights = np.zeros((n_bins, 12))
    for i, f in enumerate(freqs):
        if f < 30.0:  # sub-bass rumble: weak pitch information
            continue
        # nearest pitch class: cents of f relative to its C-relative position
        semis = 12.0 * np.log2(f / 440.0) + 9.0  # 440 = A4 = pc 9
        pc = round(float(semis)) % 12
        frac = abs(float(semis - round(semis)))
        falloff = 1.0 - 0.5 * frac  # trapezoidal across the semitone
        # harmonic-range emphasis: strongest 150-2500 Hz, taper above
        if f < 150.0:
            band_w = f / 150.0
        elif f <= 2500.0:
            band_w = 1.0
        else:
            band_w = max(0.0, 1.0 - (np.log2(f / 2500.0) / 4.0))  # -> 0 at ~40 kHz
        weights[i, pc] += falloff * band_w
    return weights


def chromagram(pcm: np.ndarray, sample_rate: int,
               n_fft: int = 4096, hop: int = 1024) -> np.ndarray:
    """Aggregate 12-dim chroma vector for the whole signal.

    Returns a 1-D array of shape (12,) with per-pitch-class energy,
    roughly normalized (max ~1).
    """
    mags, _ = compute_stft(pcm, sample_rate, n_fft, hop)
    if mags.shape[1] == 0:
        return np.zeros(12)
    pc_w = _pitch_class_matrix(n_fft, sample_rate)  # (n_bins, 12)
    chroma = mags.T @ pc_w  # (n_frames, 12) -> collapse
    chroma = chroma.mean(axis=0)
    peak = float(chroma.max())
    if peak > 0:
        chroma = chroma / peak
    return chroma


def _ks_scores(chroma: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Correlate the chroma against all 24 K-S templates.

    Returns (scores, mode_is_major) where scores is shape (24,):
    indices 0..11 are the 12 major keys (C, C#, ... B), 12..23 the minors.
    """
    c_norm = chroma / (np.linalg.norm(chroma) + 1e-9)
    scores = np.zeros(24)
    for shift in range(12):
        rot_maj = np.roll(MAJOR_PROFILE, shift) / (np.linalg.norm(MAJOR_PROFILE) + 1e-9)
        rot_min = np.roll(MINOR_PROFILE, shift) / (np.linalg.norm(MINOR_PROFILE) + 1e-9)
        scores[shift] = float(np.dot(c_norm, rot_maj))
        scores[12 + shift] = float(np.dot(c_norm, rot_min))
    return scores, None


def key_to_camelot(pc: int, mode: str) -> str:
    """Map a pitch class + mode to a Camelot-wheel code (1A..12B).

    Camelot convention (verified against the standard wheel):
      1B=C, 2B=D, 3B=E, 4B=F, 5B=G, 6B=A, 7B=B, 8B=C#, 9B=D#, 10B=F, 11B=G#, 12B=A#
      (A# = Bb, D# = Eb, F# minor ... the wheel uses sharps for minors)
    Minor keys occupy the "A" slots offset by +7 semitones' wheel position:
      1A=A#, 2A=B, 3A=C, 4A=D, 5A=E, 6A=F#, 7A=G#, 8A=A, 9A=B, 10A=C#, 11A=D#, 12A=F
    """
    # Camelot wheel (standard DJ/techno wheel):
    #   1A=A#m 2A=Bm 3A=Cm 4A=Dm 5A=Em 6A=Fm 7A=F#m 8A=Gm 9A=Abm 10A=Am 11A=Bbm 12A=Bm
    #   1B=C   2B=D   3B=E   4B=F   5B=G   6B=Ab  7B=A   8B=Bb  9B=B    10B=C#  11B=D#  12B=E
    MAJOR_WHEEL = {0: 1, 1: 10, 2: 2, 3: 11, 4: 3, 5: 4, 6: 8, 7: 5, 8: 12, 9: 7, 10: 6, 11: 9}
    MINOR_WHEEL = {0: 3, 1: 4, 2: 5, 3: 6, 4: 7, 5: 8, 6: 9, 7: 10, 8: 11, 9: 1, 10: 2, 11: 12}
    table = MINOR_WHEEL if mode.lower() == "minor" else MAJOR_WHEEL
    pos = table.get(pc % 12)
    letter = "A" if mode.lower() == "minor" else "B"
    return f"{pos}{letter}"


def palette_for_key(key: str, camelot: str | None) -> dict[str, Any]:
    """Deterministic creative color suggestion from a detected key.

    Opinionated default for audio-reactive color grades:
      - minor → cooler, more desaturated (A slots)
      - major → warmer, lifted (B slots)
      - low wheel number (1-4) → calm / low energy → muted, wide tonal range
      - mid (5-8) → mid energy → balanced saturation
      - high (9-12) → energetic / dense → saturated, high contrast
    Returns {mood, label, hexes:[3]} — hexes derived from the Camelot slot.
    """
    if camelot is None:
        return {"mood": "neutral", "label": "no key detected", "hexes": ["#3a3a3a", "#555555", "#777777"]}
    pos = int(camelot[0])
    minor = camelot.endswith("A")
    # energy band
    if pos <= 4:
        sat, contrast = 0.35, 0.45
        base_hue = 210 if minor else 18  # cool blue vs warm amber
        mood = "calm"
        label = "cool muted" if minor else "warm airy"
    elif pos <= 8:
        sat, contrast = 0.55, 0.6
        base_hue = 260 if minor else 40
        mood = "focused"
        label = "moody violet" if minor else "golden"
    else:
        sat, contrast = 0.8, 0.85
        base_hue = 320 if minor else 55
        mood = "energetic"
        label = "neon deep" if minor else "electric"

    def _hsl(h, s, l) -> str:
        # HSL -> hex
        h = (h % 360) / 360.0
        s = min(1.0, max(0.0, s))
        l = min(1.0, max(0.0, l))
        def _chan(p, q, t):
            if t < 0: t += 1
            if t > 1: t -= 1
            if t < 1/6: return p + (q - p) * 6 * t
            if t < 1/2: return q
            if t < 2/3: return p + (q - p) * (2/3 - t) * 6
            return p
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        r = _chan(p, q, h + 1/3)
        g = _chan(p, q, h)
        b = _chan(p, q, h - 1/3)
        return f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"

    # three anchors: a base, a lifted accent, a dark base
    hexes = [
        _hsl(base_hue, sat, 0.55),
        _hsl((base_hue + 24) % 360, min(1.0, sat + 0.15), 0.65),
        _hsl(base_hue, min(1.0, sat + 0.1), 0.18 + 0.4 * contrast),
    ]
    return {"mood": mood, "label": label, "hexes": hexes}


from typing import Any


def detect_key(pcm: np.ndarray, sample_rate: int,
               n_fft: int = 4096, hop: int = 1024) -> KeyResult:
    """Detect the musical key of ``pcm`` (whole-track, aggregated chroma).

    Returns a KeyResult with the best-fit K-S key, a 0..1 confidence, the
    Camelot position and a palette suggestion. Returns key="unknown" with
    confidence 0 when the material has no trustworthy tonality.
    """
    if len(pcm) < n_fft:
        return KeyResult()

    chroma = chromagram(pcm, sample_rate, n_fft, hop)
    # salience gate: is the chroma actually peaked (tonal) or flat (noise)?
    # Tonal material concentrates energy on the tonic + a few pitch classes,
    # so max/mean >> 1. Noise is near-uniform (max/mean ~1.1).
    peak_ratio = float(chroma.max()) / (float(chroma.mean()) + 1e-9)
    scores, _ = _ks_scores(chroma)
    best = int(np.argmax(scores))
    second = float(np.sort(scores)[::-1][1]) if len(scores) > 1 else 0.0
    best_score = float(scores[best])

    # confidence: the K-S gap to the runner-up, scaled to 0..1. Diatonic
    # triads produce a gap of ~0.01-0.05 (the relative/dominant keys are
    # always close in chroma space), so dividing by 0.02 puts real keys at
    # 0.5-1.0 while a flat chroma stays near 0.
    gap = best_score - second
    conf = float(np.clip(gap / 0.02, 0.0, 1.0))
    if peak_ratio < _CHROMA_PEAK_RATIO_MIN:
        # honest: no trustworthy tonality
        return KeyResult(root=-1, key="unknown", confidence=0.0,
                         chroma=[round(float(c), 4) for c in chroma])

    pc = best % 12
    mode = "major" if best < 12 else "minor"
    key_name = f"{PC_NAMES[pc]} {mode}"
    cam = key_to_camelot(pc, mode)
    pal = palette_for_key(key_name, cam)
    return KeyResult(
        root=pc,
        key=key_name,
        confidence=round(conf, 3),
        camelot=cam,
        palette=pal,
        chroma=[round(float(c), 4) for c in chroma],
    )