"""Universal marker CSV — imports into Premiere Pro / DaVinci Resolve
(marker-import extensions and scripts), spreadsheets, and any NLE tooling."""

from __future__ import annotations

import csv
import io

from spectrumalyzer.model import AnalysisResult, time_to_frame


def _require_fps(result: AnalysisResult) -> float:
    if not result.fps:
        raise ValueError("CSV export needs fps for frame numbers — pass --fps")
    return result.fps


def render(result: AnalysisResult) -> str:
    fps = _require_fps(result)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["index", "type", "time", "frame", "label", "strength", "bpm"])
    i = 1
    for b in result.beat_grid:
        writer.writerow([i, "beat", f"{b.time:.4f}", time_to_frame(b.time, fps),
                         f"beat {i}", f"{b.strength:.3f}", round(result.bpm, 2)])
        i += 1
    for o in result.onsets:
        writer.writerow([i, "hit", f"{o.time:.4f}", time_to_frame(o.time, fps),
                         "hit", f"{o.strength:.3f}", round(result.bpm, 2)])
        i += 1
    for s in result.sections:
        writer.writerow([i, "section", f"{s.start:.4f}", time_to_frame(s.start, fps),
                         f"section: {s.label}", f"{s.energy:.3f}", round(result.bpm, 2)])
        i += 1
    if result.bars is not None:
        for bar in result.bars:
            f = bar.frame if bar.frame is not None else time_to_frame(bar.downbeat_time, fps)
            writer.writerow([i, "bar", f"{bar.downbeat_time:.4f}", f,
                             f"bar {bar.index + 1}", f"{bar.beat_count}", round(result.bpm, 2)])
            i += 1
        for bar in result.bars:
            f = bar.downbeat_frame if bar.downbeat_frame is not None else time_to_frame(bar.downbeat_time, fps)
            writer.writerow([i, "downbeat", f"{bar.downbeat_time:.4f}", f,
                             f"BAR {bar.index + 1} ↓", f"{bar.beat_count}", round(result.bpm, 2)])
            i += 1
    return buf.getvalue()
