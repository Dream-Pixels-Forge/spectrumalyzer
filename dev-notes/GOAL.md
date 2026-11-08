# GOAL: spectrumalyzer — v0.7.0 bars & downbeats pipeline

**Status: active.** Started 2026-11-08. Progress: dev-notes/PROGRESS.md.

## Problem
The beat grid is per-beat. Creative workflows are measure-based: "cut every 4
beats", drop on the downbeat, phrase-level transitions in video edits. Today
consumers have to divide beats by 4 themselves and guess which beat is the
downbeat — and there's no API for it in any exporter.

## Goal (measurable)
Add bar-level structure to the analysis engine and every exporter:

1. **Engine** (`bars` layer on top of the beat grid):
   - [x] Downbeat inference from kick-anchored phase lock: beat 0 of each
         bar aligned to the phase-locked grid origin; confidence flag when the
         kick signal is weak (fall back to bar = every 4 beats from grid start)
   - [x] Bar model: `Bar` list with start time, start frame, beat list,
         downbeat frame; resampled to fps like beats are
   - [x] `bars_in_frames` + `downbeats_in_frames` arrays in the analysis model
2. **Exporters** (all 6, test-verified):
   - [x] JSON: `bars` (times + frames), `downbeats` (times + frames),
         `barCount`, `downbeatConfidence`
   - [x] Remotion: `useBarIndex` / `useBarProgress` / `useIsOnBar` added to
         the `useBeats.ts` hook
   - [x] HyperFrames: bar boundary events (`data-hf-bar` at 1.0 / `0.0`
         transitions) alongside beat events
   - [x] After Effects: bar markers with a distinct name prefix ("BAR 1") and
         downbeat markers ("BAR 1 ↓")
   - [x] CSV: extra columns/rows for bar time, bar index, downbeat flag
   - [x] FCPXML: bar + downbeat markers (rational time)
   - [x] HTML report: bar strip overlaid on the section timeline
3. **API**: `analyze()` returns bars; no breaking change to existing keys
   (bars is additive; legacy `to_legacy_dict()` untouched)
4. **MCP**: `analyze_audio` tool returns bars; docs updated
5. **Tests** — TDD, click-tracks + kick pattern fixtures:
   - [ ] Click track 120 BPM → 4-beat bars land on frames 0, N, 2N…; downbeat
         = every 4th beat; `downbeatConfidence` high
   - [ ] Kick+hat fixture → downbeats align with kicks, not hats
   - [ ] Every exporter: bar keys present and frame math exact (same assertions
         style as beat frame math)
   - [ ] Low-kick fixture → confidence flag set, bars still produced (fallback)
   - [ ] Full suite green (existing 109 + new)
6. **Docs**: README + ROADMAP (strike v0.3 item 1), CHANGELOG v0.7.0
7. **Release**: version bump, tag v0.7.0, PyPI, three-way verification gate

## Verification gates
- [ ] `pytest` all green locally (venv per dev-notes env note)
- [ ] `ruff` clean
- [ ] 6-format end-to-end on a real/synthetic track: bar keys in every output
- [ ] HTML report shows the bar strip
- [ ] Three-way version check: pyproject == git tag == PyPI

## Anti-drift
- Bars ride on the existing beat grid — no new tempo estimation, no new
  segmentation. If bar inference drifts into "chord/metre detection" scope,
  stop and re-check this file.
- No new dependencies (numpy, mcp already there; bars is pure Python on the
  existing grid).
