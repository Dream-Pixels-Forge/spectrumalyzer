"""Format registry — the single place that maps format names to exporters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional

from spectrumalyzer.exporters import (
    aftereffects,
    csv_export,
    fcpxml,
    hyperframes,
    json_export,
    remotion,
)
from spectrumalyzer.model import AnalysisResult


@dataclass(frozen=True)
class ExporterSpec:
    name: str
    suffix: str  # appended to the output base path
    description: str
    render: Callable[[AnalysisResult], str]
    requires_fps: bool = False
    extras: Optional[Callable[[AnalysisResult], Dict[str, str]]] = None


FORMATS: Dict[str, ExporterSpec] = {
    spec.name: spec
    for spec in [
        ExporterSpec(
            "json", ".json",
            "Rich JSON: bpm, beat grid, onsets, sections, bands, centroid, loudness",
            json_export.render,
        ),
        ExporterSpec(
            "remotion", ".remotion.json",
            "Frame-native JSON for Remotion + useBeats.ts React hook",
            remotion.render, requires_fps=True, extras=remotion.extras,
        ),
        ExporterSpec(
            "hyperframes", ".hyperframes.json",
            "Timeline-event JSON for HyperFrames + data-hf snippet",
            hyperframes.render, requires_fps=True, extras=hyperframes.extras,
        ),
        ExporterSpec(
            "ae", ".markers.jsx",
            "After Effects ExtendScript: comp markers on every beat/onset/section",
            aftereffects.render, requires_fps=True,
        ),
        ExporterSpec(
            "csv", ".markers.csv",
            "Marker CSV for Premiere Pro, DaVinci Resolve, spreadsheets",
            csv_export.render, requires_fps=True,
        ),
        ExporterSpec(
            "fcpxml", ".fcpxml",
            "FCPXML markers for Final Cut Pro, Resolve, Compressor",
            fcpxml.render, requires_fps=True,
        ),
    ]
}


def export(result: AnalysisResult, fmt: str) -> str:
    """Render the result in the given format (raises KeyError for unknown)."""
    spec = FORMATS[fmt]
    return spec.render(result)


def export_filename(result: AnalysisResult, fmt: str, base: Optional[str] = None) -> str:
    """Default output filename for a format, derived from the audio path.

    Idempotent on the format's FINAL extension (e.g. '.csv' for the csv
    format whose full suffix is '.markers.csv'): if ``base`` already ends
    with it, the base is used exactly as given — so ``-o beats.json`` with
    format json does not become .json.json and ``-o beats.csv`` with format
    csv stays beats.csv.
    """
    spec = FORMATS[fmt]
    stem = base or str(Path(result.path).with_suffix(""))
    final_ext = "." + spec.suffix.lstrip(".").rsplit(".", 1)[-1]
    if stem.endswith(final_ext):
        return stem
    return f"{stem}{spec.suffix}"


def extra_files(result: AnalysisResult, fmt: str, base: Optional[str] = None) -> Dict[str, str]:
    """Companion files for a format (TS hooks, snippets).

    Returns a mapping of filename suffix (starting with '.') to content, so the
    caller composes the final names from its own output base path.
    """
    spec = FORMATS[fmt]
    if spec.extras is None:
        return {}
    stem = Path(base or result.path).with_suffix("").name or "song"
    return spec.extras(result, stem)


def format_names() -> list[str]:
    return list(FORMATS.keys())
