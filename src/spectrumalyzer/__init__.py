"""spectrumalyzer — audio-reactive analysis toolkit for motion graphics.

Public API:
    analyze(path, *, fps=None, bands=True, sections=True, min_bpm=60, max_bpm=200)
        -> AnalysisResult
    trim(path, target_seconds=90, output=None, crossfade=0.5)
        -> (TrimSelection, written_path | None)   # short version for video use

CLI:
    spectrumalyzer analyze <audio> [--format ...] [--fps N]
    spectrumalyzer report  <audio> [-o report.html]
    spectrumalyzer formats
    spectrumalyzer trim    <audio|video> [--length 90] [-o out.mp3]
"""

from spectrumalyzer._version import __version__
from spectrumalyzer.analysis.beats import detect_bars
from spectrumalyzer.api import analyze
from spectrumalyzer.model import AnalysisResult, Bar, Bars, Beat, Section
from spectrumalyzer.trimmer import TrimSelection, select_trim_window, trim, trim_audio

__all__ = [
    "AnalysisResult",
    "Bar",
    "Bars",
    "Beat",
    "Section",
    "TrimSelection",
    "__version__",
    "analyze",
    "detect_bars",
    "select_trim_window",
    "trim",
    "trim_audio",
]
