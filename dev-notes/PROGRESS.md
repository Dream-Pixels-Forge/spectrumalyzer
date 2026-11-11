# Pipeline Progress — spectrumalyzer

## Current State
- Project: spectrumalyzer (Dev/cli)
- Branch: `main`
- Started: 2026-10-11
- Current Phase: 3 (Engineer)
- Status: **shipped** — v1.4.0 DAW project stubs, live on PyPI (2026-11-11)

## v1.4.0 DAW Project Stubs (2026-11-11)
- [x] `exporters/daw.py` — `export_reaper()` (minimal openable `.RPP`: tempo =
      detected BPM, PPQ 480, audio item at t=0, BAR/SECTION markers from the
      v0.7 bar grid) + `export_ableton()` (minimal `.als`: tempoMap entry,
      audio clip, marker track). Pure text, no DAW dependency.
- [x] `bpm is None` / no bars → 120.0 tempo fallback (documented)
- [x] FLP deliberately NOT shipped (binary/proprietary — documented in
      ROADMAP); DaVinci Resolve scripting deferred to v1.5 (needs a running
      Resolve instance)
- [x] CLI `spectrumalyzer daw AUDIO --da reaper|ableton [-o OUT]`
- [x] Package-root exports: `export_reaper`, `export_ableton`
- [x] 11 new tests (202 total green, ruff clean)
- [x] End-to-end: generated `.RPP` + `.als` from a real 120-BPM track
      (9 bars, 4 sections, tempo/marker structure verified by eye)
- [x] Release v1.4.0 (tag v1.4.0 → trusted-publishing workflow → PyPI live
      2026-11-11; three-way check: pyproject == tag == release == PyPI == 1.4.0)

## v1.3.0 Watch Mode (2026-11-11)
- [x] `watch.py` — `change_key(path) -> (mtime_ns, size)` +
      `WatchSession(path, out, *, formats, fps, on_change, sleep_fn)`:
      `.poll()` re-analyzes (via v1.1 `analyze_cached`) + re-exports only when
      the key changes; `.run(interval, max_polls, stop_event)` blocking loop
      with an injectable clock (no sleeps in tests)
- [x] Polling, not inotify (documented: portable, no `watchdog` dep; inotify
      is a v2 refinement)
- [x] CLI `spectrumalyzer watch AUDIO [--interval S] [--format X,Y] [--fps N]
      [-o OUT]` — one line per change to stderr, Ctrl-C to stop
- [x] MCP tool `watch_file` — non-blocking single poll per call (in-process
      per-path session state), returns `{"changed", "bpm", "beats", "cacheHit",
      "output"}`
- [x] Package-root exports: `WatchSession`, `change_key`
- [x] 10 new watch tests + 1 MCP test (191 total green, ruff clean)
- [x] Release v1.3.0 (tag v1.3.0 → trusted-publishing workflow → PyPI live
      2026-11-11; three-way check: pyproject == tag == release == PyPI == 1.3.0)

## v1.2.0 DSP Performance (2026-11-11)
- [x] scipy/pocketfft speedup **measured and rejected** — `scipy.fft.rfft`
      is slower-or-equal to `np.fft.rfft` at our transform sizes (both use
      pocketfft; numpy ≥ 2.x ships it). No scipy dependency added. Documented
      in CHANGELOG.
- [x] **Shared-STFT cache** — `compute_stft(cache=...)` memoizes each
      `(n_fft, hop)` transform into a caller-supplied dict (`new_stft_cache()`);
      `analyze()` threads one cache through `detect_beats` / `compute_bands` /
      `detect_key` so each FFT set is computed once per call (previously
      twice). No module-level global state.
- [x] **FFT plan routing** — `_rfft` routes through numpy's private
      `_pocketfft._raw_fft` planned worker when available, falling back to
      public `np.fft.rfft`. No new dependency.
- [x] **FFT-based autocorrelation** — `estimate_tempo` replaced the O(n²)
      `np.correlate(env, env, mode="full")` with an O(n log n) FFT-based
      `_autocorr_lags` over the needed lag range. BPM unchanged within ±1 on
      the 90/120/140 click fixtures.
- [x] **Vectorized phase refinement** — `detect_beats`'s local fractional
      refinement now indexes the envelope directly around the candidate window
      instead of 9 `np.interp` scans over the full envelope.
- [x] `onset_envelope`, `lowband_envelope`, `estimate_tempo`, `detect_beats`,
      `compute_bands`, `chromagram`, `detect_key` accept an optional
      `stft_cache` kwarg (default `None`).
- [x] 9 new perf tests (181 total green, ruff clean): STFT memoization
      (recompute-once, two param sets, fresh without cache), `_rfft` vs
      `np.fft.rfft`, FFT autocorr vs `np.correlate`, soft wall-clock gate.
- [x] End-to-end: full `analyze()` on a 30 s 120-BPM click track ≈ **240 ms**.
- [x] Release v1.2.0 (tag v1.2.0 → trusted-publishing workflow → PyPI live
      2026-11-11; three-way check: pyproject == tag == PyPI == 1.2.0)

## v1.1.0 Precomputed Analysis Cache (2026-11-11)
- [x] `analysis/cache.py` — `CacheKey` (sha1 of `mtime_ns:size:major:sr`),
      `CacheStore` (atomic JSON under `~/.cache/spectrumalyzer/` or
      `$SPECTRUMALYZER_CACHE_DIR`), `analyze_cached()` → `(result, cache_hit)`
- [x] `AnalysisResult.from_dict()` — full inverse of `to_dict()`; a cache hit
      rebuilds the complete result (beats, onsets, sections, bars, key,
      impact tiers, bands, centroid, loudness, waveform_peaks) without
      re-decoding or re-running DSP
- [x] Cache key invalidation: mtime or size change → miss; package-major
      version bump → miss; sample-rate change → miss; corrupt cache file →
      miss (never crash)
- [x] `--embed` output is never cached (model-dependent); `CacheStore.save()`
      injects the source path into `metadata` so a hit can restore
      `result.path`
- [x] `cmd_analyze` now calls `analyze_cached` (cache on by default);
      new `--no-cache` flag forces a fresh run; `cache: hit/miss` line
      printed to stderr (suppressed by `-q`)
- [x] Package-root exports: `CacheKey`, `CacheStore`, `analyze_cached`
- [x] 15 new cache tests + 2 new CLI tests (172 total green, ruff clean)
- [x] Release v1.1.0 (tag v1.1.0 → trusted-publishing workflow → PyPI live
      2026-11-11; three-way check: pyproject == tag == PyPI == 1.1.0)

## v1.0.0 Cut-List Generator (2026-11-08)
- [x] `analysis/cutlist.py` — `generate_cut_list(result, every_beats,
      section, tier, clip_len, fps) -> list[Cut]` + `CutList.to_dict()` +
      `cut_list_csv()`. Pure selection logic, no ffmpeg, no new DSP.
- [x] `Cut` / `CutList` dataclasses (time, in, out, frame, tier, section,
      energy, reason); clip windows truncated at the track end
- [x] `section="peak"` falls back to the loudest section; unknown labels
      fall back to the full cadence (no accidental empty result)
- [x] `tier` filter rides the v0.9 impact tiers; pulseless track → []
- [x] New `cuts` export format (stable EDL CSV: index, in, out, time,
      frame, tier, section, reason)
- [x] CLI `spectrumalyzer cuts AUDIO [--every N] [--section L]
      [--tier T] [--clip-len S] [--fps N] [-o cuts.csv] [--json]`
- [x] MCP tool `generate_cut_list` (JSON payload, no file writes)
- [x] Package-root exports: `generate_cut_list`, `Cut`, `CutList`
- [x] 16 new tests (157 total green, ruff clean)
- [x] End-to-end verified on a beat-locked 120 BPM track: 6 cuts every 4
      beats, `--every 2 --tier downbeat` → 3 cuts, `--json` stable shape

## v0.9.0 Beat Impact Tiers (2026-11-08)
- [x] `impact_tiers(beat_grid, bars, accent_quantile)` in `analysis/beats.py`
      — labels each beat `downbeat` (bar start), `accent` (top-strength
      non-downbeats at the quantile threshold), `normal`
- [x] `Beat.tier` field + `ImpactTiers` summary (accent quantile + counts)
      on the model; `ImpactTiers.to_dict()` → `impactTiers`
- [x] `analyze(accent_quantile=0.75)` + CLI `--accent-q`; pulseless tracks
      keep `tier=None`
- [x] All 6 exporters carry tiers (JSON `beatTiers`/`impactTiers`,
      Remotion `beatTiers`, CSV `tier` column, AE/FCPXML/HyperFrames labels)
- [x] 9 new tests (141 total green, ruff clean)
- [x] Release v0.9.0 (tag v0.9.0 → PyPI live 2026-11-08; three-way check
      CODE == TAG == REL == PYPI == 0.9.0)

## v0.8.0 Key Detection (2026-11-08)
- [x] `analysis/harmony.py` — chromagram (numpy STFT + log-spaced pitch-class
      binned, harmonic-band weighting) + 24 Krumhansl-Schmuckler templates
- [x] `detect_key(pcm, sr) -> KeyResult` — best-fit key, 0..1 confidence
      (K-S gap normalized), salience gate returns "unknown"/0 on flat chroma
- [x] `key_to_camelot(pc, mode)` — full 24-key Camelot table
- [x] `palette_for_key(key, camelot)` — deterministic color-grade suggestion
      (mood + 3 hex + label) from Camelot slot
- [x] `KeyResult` model (root, key, confidence, chroma, camelot, palette)
- [x] `analyze(key=True)` default → `AnalysisResult.key`
- [x] JSON nested under `key`, flat keys in remotion/hyperframes, marker
      comment in AE/FCPXML, `key` row in CSV
- [x] CLI `--no-key` opt-out + key/palette in summary + Key stat in report
- [x] MCP `analyze_audio` payload includes key; `describe()` mentions
      key + palette (richer semantic search)
- [x] 10 new tests (132 total green, ruff clean)
- [x] Release v0.8.0 (tag v0.8.0 → PyPI live 2026-11-08; three-way check
      CODE == TAG == REL == PYPI == 0.8.0, wheel contains harmony.py)

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
- [x] Release v0.7.0 (tag v0.7.0 → trusted-publishing workflow → PyPI live
      2026-11-08; three-way check: pyproject == tag == PyPI == 0.7.0, wheel
      artifact verified)

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
