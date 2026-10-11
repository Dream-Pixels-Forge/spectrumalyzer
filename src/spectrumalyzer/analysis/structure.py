"""Song structure segmentation — where the track breathes.

Uses the smoothed loudness envelope: heavy smoothing turns the track into an
energy contour; large changes in that contour are section boundaries. Labels
are honest relative-energy descriptors (quiet/mid/high/peak), not genre
guesses.
"""

from __future__ import annotations

import numpy as np

from spectrumalyzer.model import SECTION_LABELS, Section

MIN_SECTION_S = 8.0


def _smooth(x: np.ndarray, k: int) -> np.ndarray:
    if k <= 1 or len(x) < k:
        return x
    kernel = np.ones(k) / k
    return np.convolve(x, kernel, mode="same")


def detect_sections(
    pcm: np.ndarray,
    sample_rate: int,
    duration: float,
    min_section_s: float = MIN_SECTION_S,
    hop: int = 512,
) -> list[Section]:
    """Split the track into structural sections with relative energy labels."""
    n = len(pcm)
    if n == 0 or duration <= 0:
        return []

    # RMS envelope
    n_frames = n // hop
    if n_frames < 2:
        return [Section(start=0.0, end=duration, energy=1.0, label="mid")]
    frames = pcm[: n_frames * hop].reshape(n_frames, hop)
    rms = np.sqrt((frames ** 2).mean(axis=1))

    # heavy smoothing (~2 s) to get the macro energy contour
    smooth_k = max(3, int(2.0 * sample_rate / hop))
    contour = _smooth(rms, smooth_k)

    # novelty = magnitude of contour change
    novelty = np.abs(np.diff(contour, prepend=contour[0]))
    nov_max = float(novelty.max()) or 1.0

    min_gap = max(1, int(min_section_s * sample_rate / hop))
    threshold = 0.25 * nov_max

    boundaries = [0]
    last = 0
    for i in range(1, len(novelty) - 1):
        if (
            novelty[i] > threshold
            and novelty[i] >= novelty[i - 1]
            and novelty[i] >= novelty[i + 1]
            and i - last >= min_gap
        ):
            boundaries.append(i)
            last = i
    boundaries.append(n_frames)

    # merge sections shorter than min_section_s into neighbours
    cleaned: list[int] = [boundaries[0]]
    for b in boundaries[1:-1]:
        if b - cleaned[-1] >= min_gap and boundaries[-1] - b >= min_gap // 2:
            cleaned.append(b)
    cleaned.append(boundaries[-1])

    # per-section energy, normalized to the loudest section
    raw_energy = []
    for a, b in zip(cleaned, cleaned[1:]):
        seg = contour[a:b]
        raw_energy.append(float(seg.mean()) if len(seg) else 0.0)
    peak = max(raw_energy) or 1.0
    energies = [e / peak for e in raw_energy]

    # labels: rank by energy, spread across SECTION_LABELS
    order = sorted(range(len(energies)), key=lambda i: energies[i])
    labels: list[str] = [""] * len(energies)
    for rank, idx in enumerate(order):
        pos = rank / max(1, len(order) - 1)
        labels[idx] = SECTION_LABELS[round(pos * (len(SECTION_LABELS) - 1))]

    sections: list[Section] = []
    for i, (a, b) in enumerate(zip(cleaned, cleaned[1:])):
        sections.append(
            Section(
                start=round(a * hop / sample_rate, 3),
                end=round(min(duration, b * hop / sample_rate), 3),
                energy=round(energies[i], 3),
                label=labels[i],
            )
        )
    return sections
