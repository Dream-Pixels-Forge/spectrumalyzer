"""Core data model for spectrumalyzer analysis results.

Everything the analyzers produce is expressed in these dataclasses, so the
exporters, the CLI and the HTML report all share one contract.

Time units:
    - seconds (float) for human-readable data
    - frames  (int)   when an fps was requested (creative tools work in frames)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Ordered low -> high. Creative mapping cheat sheet:
#   sub     -> room-shaking rumble, camera shake
#   bass    -> kicks, glow pulses
#   lowMid  -> warmth, body of the track
#   mid     -> vocals, leads, melody
#   highMid -> presence, snare crack
#   treble  -> hats, sparkle, particle effects
BAND_NAMES = ("sub", "bass", "lowMid", "mid", "highMid", "treble")

# Default band edges in Hz (Nyquist permitting; upper edge is clamped).
BAND_EDGES_HZ: tuple[tuple[str, float, float], ...] = (
    ("sub", 20.0, 60.0),
    ("bass", 60.0, 250.0),
    ("lowMid", 250.0, 500.0),
    ("mid", 500.0, 2000.0),
    ("highMid", 2000.0, 6000.0),
    ("treble", 6000.0, 20000.0),
)

# Section labels by relative energy rank within the track.
SECTION_LABELS = ("quiet", "mid", "high", "peak")


def time_to_frame(t: float, fps: float) -> int:
    """Convert seconds to a frame index (round-to-nearest, never negative)."""
    return max(0, round(t * fps))


@dataclass
class Beat:
    """A single beat on the quantized grid, or an onset 'hit'."""

    time: float  # seconds
    strength: float = 1.0  # 0..1 normalized onset strength
    frame: int | None = None  # filled when fps was requested

    def to_dict(self, fps: float | None = None) -> dict[str, Any]:
        d: dict[str, Any] = {"time": round(self.time, 4), "strength": round(self.strength, 3)}
        f = self.frame if self.frame is not None else (
            time_to_frame(self.time, fps) if fps else None
        )
        if f is not None:
            d["frame"] = f
        return d


@dataclass
class Section:
    """A structural region of the track (intro, build, peak, ...)."""

    start: float
    end: float
    energy: float  # 0..1 relative to the loudest section
    label: str = ""

    @property
    def duration(self) -> float:
        return self.end - self.start

    def to_dict(self, fps: float | None = None) -> dict[str, Any]:
        d: dict[str, Any] = {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": round(self.duration, 3),
            "energy": round(self.energy, 3),
            "label": self.label,
        }
        if fps:
            d["startFrame"] = time_to_frame(self.start, fps)
            d["endFrame"] = time_to_frame(self.end, fps)
        return d


@dataclass
class BandData:
    """Per-frame frequency-band energies.

    ``matrix`` has shape (n_analysis_frames, len(BAND_NAMES)); rows are time
    steps of ``hop / sample_rate`` seconds, values are 0..1 normalized.
    """

    sample_rate: int
    hop: int
    matrix: list[list[float]] = field(default_factory=list)

    @property
    def frame_duration(self) -> float:
        return self.hop / self.sample_rate

    def row_at(self, t: float) -> list[float]:
        """Band energies at time ``t`` (nearest analysis frame)."""
        if not self.matrix:
            return [0.0] * len(BAND_NAMES)
        idx = min(len(self.matrix) - 1, max(0, round(t / self.frame_duration)))
        return self.matrix[idx]

    def resample_to_fps(self, fps: float, duration: float) -> list[list[float]]:
        """Linear-resample rows to one row per video frame (fps * duration rows)."""
        import math

        n = max(1, math.ceil(duration * fps))
        out: list[list[float]] = []
        src = self.matrix or [[0.0] * len(BAND_NAMES)]
        for i in range(n):
            pos = (i + 0.5) / fps / self.frame_duration  # centre of video frame
            lo = math.floor(pos)
            hi = min(len(src) - 1, lo + 1)
            frac = pos - lo
            lo = min(lo, len(src) - 1)
            row = [
                round(src[lo][b] * (1.0 - frac) + src[hi][b] * frac, 4)
                for b in range(len(BAND_NAMES))
            ]
            out.append(row)
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "names": list(BAND_NAMES),
            "frameDuration": round(self.frame_duration, 6),
            "matrix": [[round(v, 4) for v in row] for row in self.matrix],
        }


@dataclass
class AnalysisResult:
    """Complete analysis of one audio file."""

    path: str
    duration: float
    sample_rate: int
    bpm: float
    bpm_confidence: float  # 0..1 autocorrelation peak sharpness
    beat_grid: list[Beat] = field(default_factory=list)  # quantized, uniform spacing
    onsets: list[Beat] = field(default_factory=list)  # raw transients / hits
    sections: list[Section] = field(default_factory=list)
    bands: BandData | None = None
    centroid: list[float] = field(default_factory=list)  # per analysis frame, Hz
    loudness: list[float] = field(default_factory=list)  # per analysis frame, 0..1
    waveform_peaks: list[float] = field(default_factory=list)  # downsampled for viz
    fps: float | None = None  # set when frame numbers were requested
    metadata: dict[str, Any] = field(default_factory=dict)

    # ---- convenience -----------------------------------------------------
    @property
    def beat_period(self) -> float:
        """Seconds per beat (0 if unknown)."""
        return 60.0 / self.bpm if self.bpm > 0 else 0.0

    @property
    def beat_count(self) -> int:
        return len(self.beat_grid)

    def beats_as_frames(self, fps: float | None = None) -> list[int]:
        f = fps or self.fps
        if not f:
            raise ValueError("No fps available — pass fps to analyze() or the CLI --fps flag")
        return [time_to_frame(b.time, f) for b in self.beat_grid]

    def band_rows_at_fps(self, fps: float | None = None) -> list[list[float]] | None:
        f = fps or self.fps
        if self.bands is None or not f:
            return None
        return self.bands.resample_to_fps(f, self.duration)

    # ---- serialization ----------------------------------------------------
    def to_dict(self, fps: float | None = None, include_analysis: bool = True) -> dict[str, Any]:
        f = fps or self.fps
        d: dict[str, Any] = {
            "bpm": round(self.bpm, 2),
            "bpmConfidence": round(self.bpm_confidence, 3),
            "duration": round(self.duration, 3),
            "sampleRate": self.sample_rate,
            "beatCount": self.beat_count,
            "beats": [b.to_dict(f) for b in self.beat_grid],
            "onsets": [o.to_dict(f) for o in self.onsets],
            "sections": [s.to_dict(f) for s in self.sections],
        }
        if f:
            d["fps"] = f
            d["durationInFrames"] = time_to_frame(self.duration, f)
        if include_analysis and self.bands is not None:
            d["bands"] = self.bands.to_dict()
            d["centroid"] = [round(c, 1) for c in self.centroid]
            d["loudness"] = [round(v, 4) for v in self.loudness]
        d["waveformPeaks"] = [round(v, 3) for v in self.waveform_peaks]
        d["metadata"] = dict(self.metadata)
        return d

    def to_legacy_dict(self) -> dict[str, Any]:
        """Backwards-compatible shape for v0.1.0 consumers (beats/bpm/beatTimes)."""
        return {
            "bpm": round(self.bpm, 2),
            "duration": round(self.duration, 3),
            "sampleRate": self.sample_rate,
            "beatCount": self.beat_count,
            "beats": [round(b.time, 4) for b in self.beat_grid],
            "beatTimes": [round(b.time, 4) for b in self.beat_grid],
            "metadata": dict(self.metadata),
        }
