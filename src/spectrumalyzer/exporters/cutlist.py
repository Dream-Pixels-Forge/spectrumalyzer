"""Edit-decision cut-list export — the roadmap v0.4 "cut-list generator".

A `cuts` export format: the analysis' beat grid + bars + sections rendered as
a deterministic edit-decision CSV (index, in, out, time, frame, tier,
section, reason) that NLEs and scripts can import. Uses the default
every-4-beats cadence; for custom cadences/section/tier use the `cuts` CLI
subcommand or the `generate_cut_list` API directly.
"""

from __future__ import annotations

from spectrumalyzer.analysis.cutlist import CutList, cut_list_csv, generate_cut_list
from spectrumalyzer.model import AnalysisResult


def render(result: AnalysisResult) -> str:
    """Default cut list: every 4 beats (one per bar), no section/tier filter."""
    cuts = generate_cut_list(result, every_beats=4)
    cl = CutList(cuts=cuts, every_beats=4, fps=result.fps)
    return cut_list_csv(cl)


def render_with(
    result: AnalysisResult,
    every_beats: int = 4,
    section: str | None = None,
    tier: str | None = None,
    clip_len: float | None = None,
) -> str:
    """Cut-list CSV with custom parameters (used by the CLI `cuts` command)."""
    cuts = generate_cut_list(
        result, every_beats=every_beats, section=section,
        tier=tier, clip_len=clip_len,
    )
    cl = CutList(
        cuts=cuts, every_beats=every_beats, section=section,
        tier=tier, clip_len=clip_len, fps=result.fps,
    )
    return cut_list_csv(cl)
