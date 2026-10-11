"""spectrumalyzer — audio-reactive analysis toolkit for motion graphics.

Public API:
    analyze(path, *, fps=None, bands=True, sections=True, min_bpm=60, max_bpm=200)
        -> AnalysisResult

CLI:
    spectrumalyzer analyze <audio> [--format ...] [--fps N]
    spectrumalyzer report  <audio> [-o report.html]
    spectrumalyzer formats
"""

from spectrumalyzer._version import __version__
from spectrumalyzer.api import analyze
from spectrumalyzer.model import AnalysisResult, Beat, Section

__all__ = ["AnalysisResult", "Beat", "Section", "__version__", "analyze"]
