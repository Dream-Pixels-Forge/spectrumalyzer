"""Tests for the cut-list generator (v1.0).

Pure selection logic over existing analysis outputs — no ffmpeg, no DSP.
A beat-locked 120 BPM synthetic track gives a deterministic grid to assert
cadence, section filtering, tier filtering, and clip windows against.
"""

from __future__ import annotations

from spectrumalyzer.analysis.cutlist import Cut, CutList, generate_cut_list
from spectrumalyzer.model import AnalysisResult, Bar, Bars, Beat, Section

# ---------------------------------------------------------------------------
# helpers: a deterministic analysis result without running the full engine
# ---------------------------------------------------------------------------

def make_result(n_beats: int, bpm: float = 120.0,
                sections: list[Section] | None = None,
                tier_every: int = 4,
                fps: float | None = 30.0) -> AnalysisResult:
    """Build a minimal AnalysisResult with a uniform beat grid + bars.

    Beats every 60/bpm seconds. Downbeats = bar starts (every 4 beats).
    """
    period = 60.0 / bpm if bpm > 0 else 0.0
    beats: list[Beat] = []
    for i in range(n_beats):
        t = i * period
        beats.append(Beat(
            time=round(t, 4),
            strength=0.9 if i % tier_every == 0 else 0.5,
            frame=round(t * fps) if fps else None,
        ))
    # label tiers + build bars the same way the engine would
    bars = []
    for b in range(0, len(beats), 4):
        idxs = list(range(b, min(b + 4, len(beats))))
        bars.append(Bar(
            index=len(bars),
            beat_indices=idxs,
            downbeat_time=beats[b].time,
            start_time=beats[b].time,
            end_time=beats[b + 3].time if b + 3 < len(beats) else beats[b].time,
            downbeat_frame=beats[b].frame,
            frame=beats[b].frame,
            end_frame=beats[b + 3].frame if b + 3 < len(beats) else beats[b].frame,
        ))
    for i, beat in enumerate(beats):
        beat.tier = "downbeat" if i % 4 == 0 else "normal"
    return AnalysisResult(
        path="track.wav",
        duration=n_beats * period,
        sample_rate=44100,
        bpm=bpm,
        bpm_confidence=0.9,
        beat_grid=beats,
        onsets=[],
        sections=sections or [],
        bars=Bars(bars=bars, confidence=0.9),
        fps=fps,
        metadata={"version": "1.0.0", "analyzer": "spectrumalyzer"},
    )


# ---------------------------------------------------------------------------
# every-N-beats cadence
# ---------------------------------------------------------------------------

def test_every_4_beats_cuts_on_bar_starts():
    r = make_result(20, bpm=120.0)  # 20 beats @ 120 = 10 s
    cuts = generate_cut_list(r, every_beats=4)
    # 20 beats, every 4 -> cuts on beats 0,4,8,12,16 = 5 cuts
    assert len(cuts) == 5
    assert [c.time for c in cuts] == [0.0, 2.0, 4.0, 6.0, 8.0]
    # all on downbeats
    assert all(c.tier == "downbeat" for c in cuts)


def test_every_2_beats():
    r = make_result(8, bpm=120.0)  # 8 beats, every 2 -> cuts on beats 0,2,4,6
    cuts = generate_cut_list(r, every_beats=2)
    assert [c.time for c in cuts] == [0.0, 1.0, 2.0, 3.0]


def test_every_1_beats_is_all_beats():
    r = make_result(8, bpm=120.0)
    cuts = generate_cut_list(r, every_beats=1)
    assert len(cuts) == 8
    # the first cut of every bar is a downbeat
    assert [c.tier for c in cuts[:4]] == ["downbeat", "normal", "normal", "normal"]


# ---------------------------------------------------------------------------
# section filtering
# ---------------------------------------------------------------------------

def test_section_filter_restricts_to_range():
    sections = [
        Section(start=0.0, end=4.0, energy=0.4, label="quiet"),
        Section(start=4.0, end=10.0, energy=1.0, label="peak"),
    ]
    r = make_result(20, bpm=120.0, sections=sections)
    cuts = generate_cut_list(r, every_beats=4, section="peak")
    # only cuts inside 4.0-10.0 s
    assert all(4.0 <= c.time < 10.0 for c in cuts)
    assert all(c.section == "peak" for c in cuts)
    # cuts at 4, 6, 8
    assert [c.time for c in cuts] == [4.0, 6.0, 8.0]


def test_section_peak_picks_loudest_section():
    sections = [
        Section(start=0.0, end=4.0, energy=0.4, label="quiet"),
        Section(start=4.0, end=10.0, energy=0.8, label="high"),
        Section(start=10.0, end=15.0, energy=1.0, label="peak"),
    ]
    r = make_result(30, bpm=120.0, sections=sections)
    cuts = generate_cut_list(r, every_beats=4, section="peak")
    # 'peak' = the section with the highest energy (last one)
    assert all(10.0 <= c.time < 15.0 for c in cuts)


def test_unknown_section_falls_back_to_all():
    r = make_result(20, bpm=120.0, sections=[
        Section(start=0.0, end=10.0, energy=1.0, label="quiet"),
    ])
    cuts = generate_cut_list(r, every_beats=4, section="nonexistent")
    # no match -> don't restrict, return the full cadence
    assert len(cuts) == 5


# ---------------------------------------------------------------------------
# tier filtering
# ---------------------------------------------------------------------------

def test_tier_downbeat_only_bar_starts():
    r = make_result(16, bpm=120.0)
    cuts = generate_cut_list(r, every_beats=1, tier="downbeat")
    # only the 4 downbeats (0,4,8,12)
    assert [c.time for c in cuts] == [0.0, 2.0, 4.0, 6.0]
    assert all(c.tier == "downbeat" for c in cuts)


# ---------------------------------------------------------------------------
# clip windows
# ---------------------------------------------------------------------------

def test_clip_len_produces_windows():
    r = make_result(20, bpm=120.0)
    cuts = generate_cut_list(r, every_beats=4, clip_len=4.0)
    # the first cut (0.0s) is un-truncated: a clean 4 s window
    assert cuts[0].in_time == 0.0
    assert cuts[0].out_time == 4.0
    assert cuts[0].duration == 4.0
    # every cut's window starts on the cut point
    for c in cuts:
        assert c.in_time == c.time


def test_clip_windows_truncated_at_track_end():
    r = make_result(20, bpm=120.0)  # 10 s track
    cuts = generate_cut_list(r, every_beats=4, clip_len=4.0)
    # the last cut at 8.0 s would run to 12.0, but the track ends at 10.0
    last = cuts[-1]
    assert last.out_time <= r.duration + 1e-6


# ---------------------------------------------------------------------------
# no grid / pulseless
# ---------------------------------------------------------------------------

def test_no_grid_returns_empty():
    r = make_result(20)
    r.beat_grid = []
    r.bars = Bars(bars=[], confidence=0.0)
    cuts = generate_cut_list(r, every_beats=4)
    assert cuts == []


def test_empty_result_no_crash():
    r = AnalysisResult(path="x", duration=0.0, sample_rate=44100,
                       bpm=0.0, bpm_confidence=0.0)
    cuts = generate_cut_list(r, every_beats=4)
    assert cuts == []


# ---------------------------------------------------------------------------
# CutList / CSV shape
# ---------------------------------------------------------------------------

def test_cutlist_to_dict_shape():
    r = make_result(20, bpm=120.0)
    cuts = generate_cut_list(r, every_beats=4)
    cl = CutList(cuts=cuts, every_beats=4)
    d = cl.to_dict()
    assert d["everyBeats"] == 4
    assert d["count"] == 5
    assert d["cuts"][0]["time"] == 0.0
    assert "in" in d["cuts"][0] and "out" in d["cuts"][0]


def test_cut_csv_columns_stable():
    from spectrumalyzer.analysis.cutlist import cut_list_csv

    r = make_result(20, bpm=120.0)
    cuts = generate_cut_list(r, every_beats=4, clip_len=4.0)
    text = cut_list_csv(CutList(cuts=cuts, every_beats=4))
    import csv
    import io
    rows = list(csv.DictReader(io.StringIO(text)))
    assert rows, "expected at least one CSV row"
    # stable, documented column order
    assert list(rows[0].keys()) == ["index", "in", "out", "time", "frame",
                                     "tier", "section", "reason"]


def test_cut_dataclass_defaults():
    c = Cut(time=2.0)
    assert c.in_time == 2.0
    assert c.out_time == 2.0
    assert c.tier is None
    assert c.section is None


# ---------------------------------------------------------------------------
# cuts export format
# ---------------------------------------------------------------------------

def test_cuts_format_registered_and_renders():
    from spectrumalyzer.exporters import FORMATS, export

    r = make_result(20, bpm=120.0)
    assert "cuts" in FORMATS
    text = export(r, "cuts")
    import csv
    import io
    rows = list(csv.DictReader(io.StringIO(text)))
    assert rows
    assert list(rows[0].keys()) == ["index", "in", "out", "time", "frame",
                                     "tier", "section", "reason"]
    # every-4-beats default -> 5 cuts for 20 beats
    assert len(rows) == 5


def test_generate_cut_list_public_api():
    from spectrumalyzer import Cut, CutList
    from spectrumalyzer import generate_cut_list as pub_gen

    r = make_result(20, bpm=120.0)
    cuts = pub_gen(r, every_beats=4)
    assert isinstance(cuts[0], Cut)
    cl = CutList(cuts=cuts, every_beats=4)
    assert cl.count == 5
