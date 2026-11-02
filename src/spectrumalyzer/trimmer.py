"""Trimmer — make a short version of a long track for video use.

Video tools and AI video models take short clips, not full songs. The
trimmer picks the most worthwhile window of a target length from an
AnalysisResult (loudness contour + onset density + section energy), snaps
the cuts to the beat grid so they don't land mid-beat, and cuts the source
(audio or video) with ffmpeg, with short crossfades to avoid clicks.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field

import numpy as np

from spectrumalyzer.model import AnalysisResult

# Window-score weights: loudness dominates, rhythmic activity next,
# structural (section) energy last.
WEIGHT_LOUDNESS = 0.5
WEIGHT_ONSET = 0.3
WEIGHT_SECTION = 0.2

# Candidate window starts are sampled on this step; 0.5 s is dense enough
# that the "best window" granularity matches musical meaning.
STEP_S = 0.5

# 4 onsets/second is considered a saturated transient density.
ONSET_DENSITY_CAP_PER_S = 4.0


@dataclass
class TrimSelection:
    """The chosen window of a longer track."""

    start: float
    end: float
    reasons: list[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def trimmed(self) -> bool:
        """False when the whole track was kept (nothing to trim)."""
        return self.start > 1e-3

    def to_dict(self) -> dict:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": round(self.duration, 3),
            "trimmed": self.trimmed,
            "reasons": list(self.reasons),
        }


def _window_scores(
    result: AnalysisResult, target: float, starts: np.ndarray
) -> np.ndarray:
    """Per-candidate score in [0, 1] — weighted loudness/onsets/sections."""
    duration = result.duration

    # Loudness: mean of the envelope inside each window (prefix sums).
    loud = np.asarray(result.loudness, dtype=np.float64)
    if loud.size:
        # analysis frames are uniform in time; map seconds -> frame index
        idx = np.clip(
            np.round(starts * (loud.size - 1) / duration).astype(int), 0, loud.size - 1
        )
        idx_end = np.clip(
            np.round((starts + target) * (loud.size - 1) / duration).astype(int),
            idx,
            loud.size - 1,
        )
        prefix = np.cumsum(loud)
        spans = np.maximum(idx_end - idx, 1)
        loud_score = ((prefix[idx_end] - prefix[np.maximum(idx - 1, 0)]) / spans).clip(
            0.0, 1.0
        )
    else:
        loud_score = np.zeros_like(starts)

    # Onset density: hits per second inside each window.
    onset_times = np.array(
        [o.time for o in result.onsets if o.time <= duration], dtype=np.float64
    )
    if onset_times.size:
        left = np.searchsorted(onset_times, starts, side="left")
        right = np.searchsorted(onset_times, starts + target, side="right")
        onset_score = np.clip((right - left) / target / ONSET_DENSITY_CAP_PER_S, 0.0, 1.0)
    else:
        onset_score = np.zeros_like(starts)

    # Section energy: strongest structural section overlapping the window.
    section_score = np.zeros_like(starts)
    for s in result.sections:
        overlap = (starts < s.end) & (starts + target > s.start)
        section_score = np.maximum(section_score, s.energy * overlap)

    return (
        WEIGHT_LOUDNESS * loud_score
        + WEIGHT_ONSET * onset_score
        + WEIGHT_SECTION * section_score
    )


def _snap(start: float, end: float, result: AnalysisResult, snap_to_beats: bool) -> tuple[float, float, bool]:
    """Snap cut points to the nearest beat grid time (best effort)."""
    if not snap_to_beats or len(result.beat_grid) < 2:
        return start, end, False
    beats = np.array([b.time for b in result.beat_grid], dtype=np.float64)
    i = int(np.argmin(np.abs(beats - start)))
    start = float(beats[i])
    j = int(np.argmin(np.abs(beats - end)))
    snapped_end = float(beats[j])
    if abs(snapped_end - end) <= result.beat_period:
        end = snapped_end
    return start, end, True


def select_trim_window(
    result: AnalysisResult,
    target_seconds: float,
    snap_to_beats: bool = True,
) -> TrimSelection:
    """Pick the best ``target_seconds`` window of ``result``.

    If the track is already short enough, the whole track is returned
    (``trimmed == False``). Otherwise the highest-scoring window is chosen;
    cut points are snapped to the beat grid when available.
    """
    duration = result.duration
    target = min(float(target_seconds), duration)

    if target <= 1e-3 or target >= duration - 0.25:
        return TrimSelection(
            0.0,
            duration,
            [f"track is already short enough ({duration:.1f}s <= {target_seconds:.1f}s) — no trim needed"],
        )

    starts = np.arange(0.0, duration - target + 1e-3, STEP_S)
    # also consider starts that land exactly on beats (cheap: union)
    if result.beat_grid:
        beat_starts = np.array(
            [b.time for b in result.beat_grid if 0 <= b.time <= duration - target],
            dtype=np.float64,
        )
        starts = np.unique(np.concatenate([starts, beat_starts]))

    scores = _window_scores(result, target, starts)
    best = int(np.argmax(scores))
    start = float(starts[best])
    end = start + target
    snapped = _snap(start, end, result, snap_to_beats)
    start, end = snapped[0], snapped[1]
    end = min(end, duration)

    hot_section = max(
        (s for s in result.sections if s.start < end and s.end > start),
        key=lambda s: s.energy,
        default=None,
    )
    reasons = [
        f"best {target:.0f}s window of {duration:.0f}s by loudness + onset density + section energy",
    ]
    if hot_section is not None and hot_section.energy > 0:
        label = f" ('{hot_section.label}' section)" if hot_section.label else ""
        reasons.append(f"window covers the strongest overlapping section{label}")
    reasons.append(
        "cut points snapped to the beat grid"
        if snapped[2]
        else "no beat grid available — cuts at raw window bounds"
    )
    return TrimSelection(start, end, reasons)


def trim_audio(
    src: str,
    dst: str,
    start: float,
    end: float,
    crossfade: float = 0.5,
) -> str:
    """Cut [start, end] out of ``src`` into ``dst`` with short fades.

    Works on audio files and on video (the video stream is cut to the same
    window). The output container/codec follows the ``dst`` extension.
    Raises RuntimeError when ffmpeg is missing or fails.
    """
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("'ffmpeg' not found on PATH — cannot cut audio")

    dur = end - start
    if dur <= 0:
        raise ValueError("empty window: end must be after start")

    fade_in = min(crossfade, dur * 0.25)
    fade_out = min(crossfade, dur * 0.25)
    cmd = [
        "ffmpeg",
        "-v", "error",
        "-y",
        "-ss", f"{start:.3f}",
        "-i", str(src),
        "-t", f"{dur:.3f}",
    ]
    if fade_in > 0 or fade_out > 0:
        fades = []
        if fade_in > 0:
            fades.append(f"afade=t=in:st=0:d={fade_in:.3f}")
        if fade_out > 0:
            fades.append(f"afade=t=out:st={max(0.0, dur - fade_out):.3f}:d={fade_out:.3f}")
        cmd += ["-af", ",".join(fades)]
    cmd.append(str(dst))

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed to cut {src} -> {dst}: {proc.stderr.strip()[:400]}"
        )
    return dst


def default_output_path(src: str) -> str:
    """``<stem>-short.mp3`` next to the source (a sane default for video beds)."""
    from pathlib import Path

    p = Path(src)
    return str(p.with_name(p.stem + "-short.mp3"))


def trim(
    path: str,
    target_seconds: float = 90.0,
    output: str | None = None,
    crossfade: float = 0.5,
) -> tuple[TrimSelection, str | None]:
    """Analyze ``path``, pick the best short window, cut it.

    Returns ``(selection, written_path)`` — ``written_path`` is None when the
    track was already short enough (nothing cut).
    """
    from spectrumalyzer.api import analyze

    result = analyze(path)
    selection = select_trim_window(result, target_seconds)
    written: str | None = None
    if selection.trimmed:
        written = trim_audio(
            path,
            output or default_output_path(path),
            selection.start,
            selection.end,
            crossfade=crossfade,
        )
    return selection, written
