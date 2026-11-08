# Pipeline Progress — spectrumalyzer

## Current State
- Project: spectrumalyzer (Dev/cli)
- Branch: `main`
- Started: 2026-10-11
- Current Phase: 3 (Engineer)
- Status: **shipped** — v0.7.0 bars & downbeats (2026-11-08)

## v0.7.0 Bars & Downbeats (2026-11-08)
- [x] `detect_bars()` in `analysis/beats.py` — 4/4 grouping on the beat grid,
      downbeat = first beat of each bar; confidence flag when kick anchor weak
- [x] `Bar`/`Bars` dataclasses in `model.py` (index, beat_indices,
      downbeat_time, frame/end_frame/downbeat_frame)
- [x] `AnalysisResult.bars: Bars | None` wired through `analyze()`
- [x] JSON export: `bars`, `downbeats`, `barCount`, `downbeatConfidence`
- [x] Remotion: `barsInFrames`, `downbeatsInFrames`, `barPeriodInFrames`,
      `useBarIndex`/`useBarProgress`/`useIsOnBar` in `useBeats.ts` hook
- [x] HyperFrames: `bar` + `downbeat` timeline events
- [x] After Effects: `BAR N` + `BAR N ↓` comp markers
- [x] CSV: `bar` and `downbeat` row types
- [x] FCPXML: `BAR N` + `BAR N ↓` markers
- [x] HTML report: bar strip panel with downbeat ticks
- [x] MCP `analyze_audio` lean payload includes bars
- [x] CLI `analyze` prints bar count + first bars
- [x] 13 new tests (122 total green, ruff clean); end-to-end verified on
      synthetic 120 BPM kick+hat track (30 bars, downbeats on kicks)
- [ ] Release v0.7.0 (version bump + tag + PyPI, on user's go)

## v0.6.0 Trimmer (2026-11-02, shipped)
- [x] `spectrumalyzer trim AUDIO_OR_VIDEO --length N [-o] [--crossfade] [--preview]`
- [x] Window selection: loudness + onset density + section energy, cuts snapped to beat grid
      (`src/spectrumalyzer/trimmer.py` — pure logic, ffmpeg cut separate)
- [x] Video support: mp4 source cut to the same window (audio + video)
- [x] No-op notice when the track is already short enough
- [x] Python API `trim()` + MCP tool `trim_audio`
- [x] 15 new tests (109 total green, ruff clean); end-to-end verified on a 90 s track
      (30 s target → chorus window 44.8–74.7 s) and an mp4
- [x] Version bump 0.6.0 (pyproject + _version.py + CHANGELOG finalized, 2026-11-02)
- [x] PyPI release of v0.6.0 (tag v0.6.0 → trusted-publishing workflow, green 2026-11-02)

## v0.7.0 Bars & downbeats (2026-11-08)
- [x] `detect_bars(beat_grid, bpm, confidence, fps)` in `analysis/beats.py` —
      4/4 grouping of the kick-anchored beat grid; downbeat = bar start
- [x] `Bar` + `Bars` model in `model.py` (frame math mirrors beat grid)
- [x] `AnalysisResult.bars` populated by `analyze()` — additive, no breaking
      change to existing keys
- [x] All 6 exporters: bars/downbeats in json (barCount, downbeats,
      downbeatConfidence), remotion (+useBarIndex/useBarProgress/useIsOnBar
      in the hook), hyperframes (bar + downbeat events), ae (BAR N / BAR N ↓
      markers), csv (bar/downbeat rows), fcpxml (BAR markers)
- [x] HTML report bar strip (canvas, downbeat ticks)
- [x] MCP `analyze_audio` lean payload gains `bars`/`downbeats`
- [x] CLI `analyze` prints bar count + first bars
- [x] 13 new tests (122 total green, ruff clean)
- [x] End-to-end verified on synthetic 120 BPM kick+hat track: bars land on
      accent downbeats, all 6 formats emit bar data
- [ ] Release v0.7.0 (version bump + tag + PyPI, on user's go)

## Shipped Milestones
- **v0.2.0** — "Creative Toolkit": real STFT/spectral-flux engine, 6 exporters, HTML report,
  TDD cycles (see log below)
- **v0.3.0** — semantic hearing: embedding layer (`describe`, `find`, `model pull/status`),
  FakeEmbedder tests, real-model smoke test skipped in CI
- **v0.4.0** — single install: embedding stack ships in the base package
- **v0.5.0** — MCP server (FastMCP, stdio): analyze_audio, describe_audio, find_music,
  export_beats, render_report, model_status; 93 tests green, wire test passed
- **v0.5.1/0.5.2** — default branch `master` → `main`, canonical skill-install URL
  (`npx skills add owner/repo/subpath` — verified live against 13 agent platforms)

## Phase Completion (v0.2.0 pipeline)
- [x] Phase 0: Bootstrap — GOAL.md with measurable gates (dev-notes/GOAL.md)
- [x] Phase 1: Brainstorm/Investigation — code audit findings (fake spectrum,
      dead params, stub files) + creative-user feature research
- [x] Phase 2: Governance/Spec — GOAL.md verification gates set
- [x] Phase 3: Engineer
    - [x] Worker A: package skeleton + pyproject (PEP 621, src layout)
    - [x] Worker B: model.py + audio.py (dataclasses, ffmpeg decode)
    - [x] Worker C: analysis engine — TDD RED (14 failing) → GREEN (21 pass)
    - [x] Worker D: exporters ×6 — TDD RED (collect error) → GREEN (13 pass)
    - [x] Worker E: report + CLI — TDD RED (5 failing) → GREEN (43 pass)
    - [x] Worker F: docs (README, ROADMAP, CHANGELOG, SKILL.md) + ci.yml
    - [x] Gate: full suite green + real-audio end-to-end + lint

## Verification Gates (current, v0.5.2)
- [x] `pytest` — 93 passed, ruff clean (per release commit; CI green on main 2026-10-11)
- [x] 6-format end-to-end on real audio (json, csv, remotion, ae, fcpxml, hyperframes + report)
- [x] HTML report opens with canvas + embedded payload (120 KB, verified at v0.2.0 gates)
- [x] Click-track BPM within ±3 (90/120/140 all pass)
- [x] v0.1.0 dead code removed (build_script.py, gui_report.py, root spectrumalyzer.py)
- [x] No open issues or PRs on GitHub

## TDD Cycles Log (v0.2.0)
| Cycle | RED | GREEN |
|-------|-----|-------|
| beats/tempo | 4 fail (module missing → impl) | estimate_tempo ±3 BPM on 90/120/140 click tracks |
| beat grid | empty grid (duration=0 bug) | derive duration; phase = weighted circular mean of onsets |
| bands | 100 Hz bled into sub band (43 Hz bins) | n_fft 4096 → 10.8 Hz/bin separation |
| exporters | 6 collection errors | 6 formats, frame math verified |
| filename idempotency | -o beats.json → .json.json | final-extension rule + regression test |

## Decisions Made
- numpy is a required dependency (real FFT/STFT is impossible in reasonable pure-Python time;
  the v0.1.0 "no dependencies" claim came from the broken implementation, not a real constraint)
- ffmpeg/ffprobe stay the only system dependency
- Beat grid is phase-ambiguous modulo the period — tests assert "clicks land on grid",
  not "grid starts at first click"
- Breaking change in 0.2.0: fake `spectrum` key replaced by real `bands`;
  legacy `to_legacy_dict()` keeps bpm/beats/beatTimes consumers alive
- v0.4.0: embedding stack in base package (single install) — `mcp` joined in v0.5.0;
  `mcp<2` pinned (2.x renamed FastMCP to MCPServer — CI caught the skew)
- Default branch renamed to `main` (v0.5.1); canonical install URL uses
  `npx skills add owner/repo/subpath` (tree/ syntax unsupported)

## Blockers
- none

## Environment Note (dev machine, 2026-11-02)
- `pip3` on this machine resolves to a pipx-managed pip venv, so `python3 -m pytest`
  cannot import the package locally (93 tests verified via CI instead). For local runs,
  create a project venv: `python3 -m venv .venv && .venv/bin/pip install -e .[dev]`.
