"""Cut-list generator — pure edit-decision logic over existing analysis.

Turns an AnalysisResult (beat grid + bars + sections) into a deterministic
list of cuts for video editing. This is *selection* logic, not media
processing: it never touches the source file. The output is data (CSV / JSON)
that an NLE or a script can consume.

    every-N-beats cadence  ->  cuts on the beat grid (snapped to bars)
    section filter         ->  restrict to one structural region
    tier filter            ->  only downbeats / accents
    clip windows           ->  optional in/out hold per cut (montage style)

No new DSP, no new dependencies — it rides the beat grid, bar grid and
sections that the analysis already produced.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any

from spectrumalyzer.model import AnalysisResult, time_to_frame


@dataclass
class Cut:
    """One edit point (optionally with a clip window).

    ``time`` is the cut in/out point in seconds; ``in_time``/``out_time``
    describe the segment to keep when ``clip_len`` was requested (a montage
    "hold this segment" window). ``section`` is the label of the section
    the cut falls in (None when no section spans it). ``reason`` is a short
    human string (e.g. "every-4-beat on downbeat, peak").
    """

    time: float
    in_time: float | None = None
    out_time: float | None = None
    frame: int | None = None
    tier: str | None = None
    section: str | None = None
    energy: float | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.in_time is None:
            self.in_time = self.time
        if self.out_time is None:
            self.out_time = self.time

    @property
    def duration(self) -> float:
        return round(self.out_time - self.in_time, 4)

    def _dict(self) -> dict[str, Any]:
        return {
            "time": self.time,
            "in": self.in_time,
            "out": self.out_time,
            "frame": self.frame,
            "tier": self.tier,
            "section": self.section,
            "energy": self.energy,
            "duration": self.duration,
            "reason": self.reason,
        }


@dataclass
class CutList:
    """The full edit-decision list + the parameters that produced it."""

    cuts: list[Cut]
    every_beats: int = 4
    section: str | None = None
    tier: str | None = None
    clip_len: float | None = None
    fps: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.cuts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "everyBeats": self.every_beats,
            "section": self.section,
            "tier": self.tier,
            "clipLen": self.clip_len,
            "count": self.count,
            "cuts": [c._dict() for c in self.cuts],
        }


def _section_at(sections, t: float) -> Any | None:
    for s in sections:
        if s.start <= t < s.end:
            return s
    return None


def _peak_section(sections):
    """Return the section labelled 'peak', or the highest-energy one if none."""
    if not sections:
        return None
    for s in sections:
        if s.label == "peak":
            return s
    return max(sections, key=lambda s: s.energy)


def generate_cut_list(
    result: AnalysisResult,
    every_beats: int = 4,
    section: str | None = None,
    tier: str | None = None,
    clip_len: float | None = None,
    fps: float | None = None,
) -> list[Cut]:
    """Produce a list of cuts from an analysis.

    Args:
        result: an AnalysisResult (beat_grid + bars + sections populated).
        every_beats: cadence — cut every N beats along the grid.
        section: restrict to this section by label ("peak" picks the loudest
            region when no section has that exact label). If the label matches
            no section, the filter is ignored (full cadence is returned).
        tier: restrict to beats with this impact tier ("downbeat", "accent",
            "normal"); None = all beats.
        clip_len: when set, each cut carries an in/out window of this length
            (truncated at the track end).
        fps: when set, cuts gain frame numbers.

    A pulseless track (no beat grid) returns an empty list — no crash, no
    invented cuts.
    """
    beats = result.beat_grid
    if not beats:
        return []
    f = fps if fps is not None else result.fps

    # --- optional section window -------------------------------------------
    sec_filter: Any | None = None
    if section is not None:
        match = next((s for s in result.sections if s.label == section), None)
        sec_filter = match if match is not None else _peak_section(result.sections)

    cuts: list[Cut] = []
    step = max(1, int(every_beats))
    for i, beat in enumerate(beats):
        if i % step != 0:
            continue  # cadence: only every-Nth beat
        t = beat.time

        if sec_filter is not None and not (sec_filter.start <= t < sec_filter.end):
            continue

        if tier is not None and beat.tier != tier:
            continue

        sec = _section_at(result.sections, t)
        energy = sec.energy if sec is not None else None
        out_time = t
        in_time = t
        if clip_len is not None:
            in_time = t
            out_time = min(t + clip_len, result.duration)

        reason_bits = [f"every-{step}-beat"]
        if beat.tier:
            reason_bits.append(beat.tier)
        if sec is not None:
            reason_bits.append(sec.label)
        if sec_filter is not None and sec is not None and sec.start <= t < sec.end:
            reason_bits.append(f"in {sec.label} window")

        cuts.append(Cut(
            time=round(t, 4),
            in_time=round(in_time, 4),
            out_time=round(out_time, 4),
            frame=beat.frame if beat.frame is not None else (time_to_frame(t, f) if f else None),
            tier=beat.tier,
            section=sec.label if sec is not None else None,
            energy=round(energy, 3) if energy is not None else None,
            reason=", ".join(reason_bits),
        ))
    return cuts


def cut_list_csv(cl: CutList) -> str:
    """Stable edit-decision CSV (index, in, out, time, frame, tier, section, reason)."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["index", "in", "out", "time", "frame", "tier", "section", "reason"])
    for i, c in enumerate(cl.cuts, start=1):
        writer.writerow([
            i,
            f"{c.in_time:.4f}",
            f"{c.out_time:.4f}",
            f"{c.time:.4f}",
            c.frame if c.frame is not None else "",
            c.tier or "",
            c.section or "",
            c.reason,
        ])
    return buf.getvalue()
