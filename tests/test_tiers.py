"""Tests for the beat impact-tier layer (v0.9).

Tiers ride the existing bar grid + beat strength — no new DSP:
  - downbeat = the first beat of each bar
  - accent   = the top ``accent_quantile`` of the *non-downbeat* beats
  - normal   = everything else
"""

from __future__ import annotations

from spectrumalyzer.analysis.beats import detect_beats, impact_tiers
from spectrumalyzer.audio import load
from spectrumalyzer.model import Bar, Bars, Beat

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _grid(n: int, period: float = 0.5, downbeat_every: int = 4,
          strength_by_index: dict[int, float] | None = None,
          default_strength: float = 0.4) -> tuple[list[Beat], Bars]:
    """A uniform beat grid + bar grid where beat 0, 4, 8... are downbeats.

    ``strength_by_index`` lets a test plant a realistic strength gradient so
    the accent-quantile math has meaningful separation.
    """
    beats = []
    for i in range(n):
        strength = (strength_by_index or {}).get(i, default_strength)
        beats.append(Beat(time=i * period, strength=strength, frame=int(i * period * 30)))
    bars = []
    for b in range(0, n, downbeat_every):
        idxs = list(range(b, min(b + downbeat_every, n)))
        bars.append(Bar(
            index=len(bars),
            beat_indices=idxs,
            downbeat_time=beats[b].time,
            start_time=beats[b].time,
            end_time=beats[b + len(idxs) - 1].time if b + len(idxs) - 1 < n else beats[b].time,
            downbeat_frame=beats[b].frame,
            frame=beats[b].frame,
            end_frame=beats[b + len(idxs) - 1].frame if b + len(idxs) - 1 < n else beats[b].frame,
        ))
    return beats, Bars(bars=bars, confidence=0.9)


def _bars_of(beats):
    return Bars(bars=beats, confidence=0.9)


# ---------------------------------------------------------------------------
# tier assignment
# ---------------------------------------------------------------------------

def test_downbeats_are_bar_starts():
    beats, bars = _grid(8)
    impact_tiers(beats, bars)
    # beat 0 and beat 4 are bar starts -> downbeat
    assert beats[0].tier == "downbeat"
    assert beats[4].tier == "downbeat"
    # beat 2, 6 are not
    assert beats[2].tier in ("normal", "accent")
    assert beats[6].tier in ("normal", "accent")


def test_accents_are_top_quantile_of_non_downbeats():
    # 16 beats, downbeats at 0,4,8,12. Plant a monotonic strength gradient on
    # the non-downbeats so the q=0.5 threshold splits them exactly in half.
    strengths = {i: round(0.4 + 0.05 * i, 3) for i in range(1, 16) if i not in (4, 8, 12)}
    beats, bars = _grid(16, strength_by_index=strengths)
    impact_tiers(beats, bars, accent_quantile=0.5)
    non_down = [b for i, b in enumerate(beats) if i not in (0, 4, 8, 12)]
    accents = [b for b in non_down if b.tier == "accent"]
    # at q=0.5 about half the non-downbeats are accents
    assert len(accents) == len(non_down) // 2


def test_lower_quantile_means_more_accents():
    strengths = {i: round(0.4 + 0.05 * i, 3) for i in range(1, 16) if i not in (4, 8, 12)}
    beats, bars = _grid(16, strength_by_index=strengths)
    tiers_lo = impact_tiers([b.copy() for b in beats], bars, accent_quantile=0.25)
    beats2, bars2 = _grid(16, strength_by_index=strengths)
    tiers_hi = impact_tiers(beats2, bars2, accent_quantile=0.9)
    n_lo = sum(1 for b in tiers_lo if b.tier == "accent")
    n_hi = sum(1 for b in tiers_hi if b.tier == "accent")
    assert n_lo > n_hi, f"q=0.25 ({n_lo} accents) should beat q=0.9 ({n_hi})"


def test_no_bars_leaves_tiers_none():
    beats = [Beat(time=0.0, strength=0.5), Beat(time=0.5, strength=0.5)]
    impact_tiers(beats, None)
    assert all(b.tier is None for b in beats)


def test_empty_grid():
    assert impact_tiers([], Bars(bars=[], confidence=0.0)) == []


def test_pulseless_track_has_no_tiers(pulseless_pad):
    pcm, _dur, sr = load(str(pulseless_pad))
    result = detect_beats(pcm, sr)
    assert len(result["beat_grid"]) == 0  # no grid -> no tiers
    tiers = impact_tiers(result["beat_grid"], None)
    assert tiers == []


# ---------------------------------------------------------------------------
# summary counts
# ---------------------------------------------------------------------------

def test_impact_summary_counts():
    beats, bars = _grid(8, strength_by_index={2: 0.8, 6: 0.8})
    impact_tiers(beats, bars, accent_quantile=0.5)
    from collections import Counter
    c = Counter(b.tier for b in beats)
    assert c["downbeat"] == 2  # beats 0, 4
    assert c["normal"] + c["accent"] == 6
