# GOAL: spectrumalyzer — v1.0.0 cut-list generator pipeline

**Status: active.** Started 2026-11-08. Progress: dev-notes/PROGRESS.md.

## Problem
Creative users want an edit-decision list, not raw markers: "give me the
cut points for a 4-beat montage on the downbeats" or "the loudest section,
cut every 4 beats." Today they have to divide the beat grid themselves and
eyeball the sections. Now that bars, impact tiers, and section energy all
exist, a cut-list generator is trivial pure logic — and it's the
v0.4 roadmap item ("Cut-list generator — `spectrumalyzer cuts track.mp3
--every 4beats --section peak` → edit-decision CSV/JSON for Premiere/Resolve
scripting").

## Goal (measurable)
A `cuts` command + pure-logic module that turns an analysis into a
deterministic, exportable edit-decision list.

1. **Cut-list engine** (`analysis/cutlist.py`, pure, testable without ffmpeg):
   - [x] `Cut` dataclass: `time` (s), `frame` (optional), `in_time`/`out_time`
         (a clip window), `label`, `tier`, `section`, `energy`, `reason`
   - [x] `generate_cut_list(result, every_beats=4, section=None, tier=None,
         clip_len=4.0, fps=None) -> list[Cut]`
     - every-N-beats cadence snapped to the beat grid
     - `section="peak"` restricts cuts to that section's time range
     - `tier="downbeat"` restricts to downbeat beats (4/4 every = bar starts)
     - optional clip windows (`clip_len`) for montage-style "hold this segment"
   - [x] `CutList` dataclass with `to_dict()` → JSON export
2. **New `cuts` export format** — edit-decision CSV (Premiere/Resolve
   marker-injector + spreadsheet columns: index, in, out, time, frame, tier,
   section, reason)
3. **CLI** — `spectrumalyzer cuts AUDIO [--every N] [--section LABEL]
   [--tier downbeat] [--clip-len S] [--fps N] [-o cuts.csv]`
4. **API** — `generate_cut_list` + `CutList`/`Cut` public at package root
5. **MCP** — `generate_cut_list` tool (returns JSON, no file writes unless
   requested)
6. **Tests** — TDD, deterministic synthetic beat-locked track:
   - [x] `--every 4` on a 120 BPM track → cuts on bar starts, count = beats/4
   - [x] `section="peak"` restricts to the loud section's range
   - [x] `tier="downbeat"` → exactly the bar-start beats
   - [x] `clip_len` produces in/out windows of the requested length
   - [x] no grid (pulseless) → empty list, no crash
   - [x] `to_dict`/CSV shape stable (column order asserted)
   - [x] Full suite green (141 + new)
7. **Docs**: CHANGELOG v1.0.0 + ROADMAP strike + PROGRESS — DONE
8. **Release**: v1.0.0 bump, tag, PyPI, three-way gate — DONE 2026-11-08
   (three-way: pyproject == tag == PyPI == 1.0.0, wheel verified)

## Anti-drift
- Cut-list is pure selection logic over existing analysis outputs — no new
  DSP, no new dependencies. If this drifts into actual media cutting /
  scripting automation for a specific NLE, stop and re-check. The output is
  data (CSV/JSON) that NLEs can consume, not NLE-specific code generation.
