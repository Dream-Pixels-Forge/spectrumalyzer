# Changelog

All notable changes to spectrumalyzer are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [Semantic Versioning](https://semver.org/).

## [1.4.0] — 2026-11-11

### Added
- **DAW project stubs** (`exporters/daw.py`) — `export_reaper(result,
  source_path, out_path)` writes a minimal openable REAPER `.RPP` (project
  tempo = detected BPM, PPQ 480, one audio item at t=0, BAR/SECTION markers
  on the v0.7 bar grid); `export_ableton(...)` writes a minimal Ableton Live
  `.als` (tempoMap entry at the detected BPM, one audio clip referencing the
  source, marker track with `BAR N` / `SECTION <label>` entries). Pure text
  generators — no DAW install needed to produce or open them.
- **CLI** `spectrumalyzer daw AUDIO --da reaper|ableton [-o OUT]` — analyze
  (or reuse) then emit the target DAW stub in one command.
- **11 new tests** (`tests/test_daw.py`) — structure, tempo, marker count,
  media item, pulseless fallback (120.0 BPM), section markers, error on
  missing source, CLI parsing, package-root exports. 202 total green,
  ruff clean.

### Notes
- `bpm is None` / no bars → 120.0 tempo fallback (documented in `daw.py`).
- **FLP is NOT shipped** (binary, proprietary — needs a real test vector);
  **DaVinci Resolve scripting** is a separate v1.5 item (requires a running
  Resolve instance). Both documented in ROADMAP.
- `export_reaper`, `export_ableton` are exported from the package root.

## [1.3.0] — 2026-11-11

### Added
- **Watch mode** (`watch.py`) — `WatchSession` polls a source file's
  `(mtime_ns, size)` and re-analyzes + re-exports only when it changes.
  Re-analyzes through the v1.1 `analyze_cached` path, so a touch that bumps
  mtime but not content is an instant cache hit. Pure stdlib polling — no
  `watchdog`/inotify dependency (portable; inotify is a v2 refinement).
- **CLI** `spectrumalyzer watch AUDIO [--interval S] [--format X,Y]
  [--fps N] [-o OUT]` — re-export on every change, one line per change to
  stderr, Ctrl-C to stop.
- **MCP tool** `watch_file` — non-blocking single poll per call (the engine's
  `poll()` is exactly that shape), per-path in-process session state; returns
  `{"changed", "bpm", "beats", "cacheHit", "output"}`.
- **10 new tests** (`tests/test_watch.py`) — `change_key`, poll
  unchanged/changed, cache-hit re-export, `run()` with an injectable fake
  clock + stop event, `on_change` callback, CLI subcommand parsing; plus the
  `watch_file` tool in the MCP test. 191 total green, ruff clean.

### Notes
- `WatchSession` and `change_key` are exported from the package root.
- `WatchSession.run(interval, max_polls=None, stop_event=None)` accepts an
  injectable `sleep_fn` so tests never sleep in CI.

## [1.2.0] — 2026-11-11

### Added
- **Shared-STFT cache** (`analysis/spectrum.py`): `compute_stft(cache=...)`
  now memoizes each `(n_fft, hop)` transform into a caller-supplied dict
  (`new_stft_cache()`). A single `analyze()` call needs the STFT at two
  parameter sets (1024/512 for onsets/tempo/low-band, 4096/1024 for
  bands/chromagram) — previously each set was FFT-transformed **twice**.
  `analyze()` now threads one cache through `detect_beats`, `compute_bands`
  and `detect_key`, so each set is computed exactly once. No module-level
  global state (avoids stale `id(pcm)` hits after garbage collection).
- **FFT plan routing** (`_rfft`): routes the STFT transform through
  numpy's private `_pocketfft._raw_fft` planned worker when available,
  falling back to the public `np.fft.rfft` — amortizes planning overhead
  on repeated same-size transforms. No new dependency.
- **9 new tests** (`tests/test_perf.py`): STFT memoization (recompute-once,
  two param sets, fresh without cache), `_rfft` vs `np.fft.rfft` (1-D and
  2-D), FFT-based autocorrelation vs `np.correlate`, and a soft wall-clock
  gate. 181 total green, ruff clean.

### Changed
- `estimate_tempo` now computes the onset-envelope autocorrelation with an
  FFT-based O(n log n) routine (`_autocorr_lags`) instead of the O(n²)
  `np.correlate(env, env, mode="full")` over the whole envelope. BPM output
  is unchanged within ±1 on the 90/120/140 BPM click fixtures.
- `detect_beats`'s local fractional phase refinement now indexes the
  envelope directly around the candidate window instead of 9 `np.interp`
  scans over the full envelope. Beat grid is unchanged.
- `onset_envelope`, `lowband_envelope`, `estimate_tempo`, `detect_beats`,
  `compute_bands`, `chromagram`, `detect_key` accept an optional
  `stft_cache` kwarg (default `None` = no memoization) so callers can share
  one STFT across a single analysis.

### Notes
- **scipy/pocketfft speedup: measured and rejected.** `scipy.fft.rfft` is
  *slower or equal* to `np.fft.rfft` at our transform sizes (both use
  pocketfft; numpy ≥ 2.x already ships it). No dependency was added. The
  v0.5 roadmap item's premise is outdated — the real wins came from the
  shared-STFT cache + FFT autocorrelation above. A full `analyze()` on a
  30 s click track now runs in ~240 ms end-to-end.

## [1.1.0] — 2026-11-11

### Added
- **Precomputed analysis cache** — the roadmap v0.5 item: re-exports and
  re-runs of the same file skip the full DSP on a cache hit:
  - `analysis/cache.py` — `CacheKey` (stable hash of
    `(mtime_ns, size, major-version, sample_rate)`), `CacheStore`
    (atomic JSON-on-disk writes under `~/.cache/spectrumalyzer/` or
    `$SPECTRUMALYZER_CACHE_DIR`), `analyze_cached()` returning
    `(result, cache_hit: bool)`.
  - `AnalysisResult.from_dict()` — full inverse of `to_dict()`; a cache
    hit rebuilds the complete result (beats, bars, key, tiers, sections,
    bands, centroid, loudness, waveform) without re-decoding or
    re-running DSP.
  - `CacheKey.from_file` invalidates on any mtime or size change, on
    package-major-version bump, or sample-rate change; a corrupt cache
    file is treated as a miss (never a crash).
  - `--embed` output is never cached (model-dependent, re-run each time).
  - Package-root exports: `CacheKey`, `CacheStore`, `analyze_cached`.
- **CLI** `analyze` reads the cache by default; `--no-cache` forces a
  full re-analysis and skips the cache entirely. A `cache: hit/miss`
  line is printed to stderr when not quiet.

### Changed
- `cmd_analyze` now calls `analyze_cached` instead of `analyze` directly;
  cached runs are instant (no ffmpeg decode, no DSP) while the result is
  byte-identical to a fresh analysis.

- 15 new cache tests + 2 new CLI tests (172 total green, ruff clean).
  Cache key stability (mtime/size/version/sample-rate), round-trip,
  corrupt-file fallback, `use_cache=False`, `analyze_cached`
  hit/miss/file-change, and the CLI `--no-cache` path are all covered.

## [1.0.0] — 2026-11-08

### Added
- **Cut-list generator** — the roadmap v0.4 item: an edit-decision list from
  the analysis, not raw markers. Pure selection logic, no new DSP, no new
  dependencies:
  - `generate_cut_list(result, every_beats, section, tier, clip_len, fps)`
    in `analysis/cutlist.py` — cuts every N beats on the beat grid,
    optionally restricted to a section (`section="peak"` picks the loudest
    region) and/or an impact tier (`"downbeat"`/`"accent"`/`"normal"`), with
    optional montage-style clip windows (truncated at the track end).
    Pulseless tracks return an empty list, no crash, no invented cuts.
  - `Cut` / `CutList` models (`Cut.time`/`in`/`out`/`frame`/`tier`/`section`
    /`energy`/`reason`, `CutList.to_dict()`).
  - New **`cuts` export format** — a stable edit-decision CSV
    (`index, in, out, time, frame, tier, section, reason`) for NLE
    EDL / marker import or spreadsheet review.
  - CLI: `spectrumalyzer cuts AUDIO [--every N] [--section LABEL]
    [--tier downbeat] [--clip-len S] [--fps N] [-o cuts.csv] [--json]`.
  - API: `generate_cut_list`, `Cut`, `CutList` at the package root.
  - MCP tool `generate_cut_list` (returns JSON, no file writes).
- 16 new tests (157 total green, ruff clean): cadence, section filter,
  tier filter, clip-window truncation, no-grid no-crash, stable CSV columns,
  the `cuts` format, public-API exposure.

## [0.9.0] — 2026-11-08

### Added
- **Beat impact tiers** — pre-labelled emphasis on the existing beat grid
  (rides the bar grid + beat strength, no new DSP):
  - `impact_tiers(beat_grid, bars, accent_quantile=0.75)` in
    `analysis/beats.py` labels each beat `downbeat` (bar start), `accent`
    (top-strength non-downbeats at the quantile threshold) or `normal`
  - `Beat.tier` field + `ImpactTiers` summary (accent quantile + counts);
    `ImpactTiers.to_dict()` → `impactTiers`
  - `analyze(accent_quantile=0.75)` + CLI `--accent-q`; pulseless tracks
    keep `tier=None` (no invented emphasis)
  - All 6 exporters carry tiers (JSON `beatTiers`/`impactTiers`,
    Remotion `beatTiers`, CSV `tier` column, AE/FCPXML/HyperFrames labels)
  - 9 new tests (141 total green, ruff clean)

## [0.8.0] — 2026-11-08

### Added
- **Musical key detection** (Krumhansl-Schmuckler over a numpy chromagram —
  no ML, no new dependencies):
  - `detect_key(pcm, sr)` in `analysis/harmony.py` — chroma extraction with
    harmonic-range weighting, 24 K-S key templates, goodness-of-fit
    confidence, and a salience gate that returns `key="unknown"` (confidence
    0) for pulseless/ambient material instead of inventing harmony.
  - `KeyResult` model: `root` (pitch class), `key` (e.g. "A minor"),
    `confidence`, `chroma` (12-dim), `camelot`, `palette`.
  - **Creative mapping**: `key_to_camelot()` (standard DJ Camelot wheel,
    all 24 keys) and `palette_for_key()` — a deterministic color-grade
    suggestion (mood + 3 hex anchors + a label) derived from the Camelot
    slot (minor = cool, major = warm; wheel position = energy/saturation).
  - Wired into `analyze(key=True)` → `AnalysisResult.key`; exposed at the
    package root (`detect_key`, `KeyResult`).
  - All 6 exporters carry key data (JSON nested, flat keys in
    remotion/hyperframes, a marker comment in AE/FCPXML, a `key` row in CSV).
  - CLI `analyze --no-key` opt-out + key/palette in the summary; HTML report
    gains a Key stat; MCP `analyze_audio` payload includes key; the
    semantic layer (`describe`) now mentions key + palette for richer search.
- 11 new tests (132 total green, ruff clean): A-minor / C-major chord
  fixtures → correct root, noise → "unknown" (confidence 0), Camelot table
  spot-checks, palette shape, exporter + MCP key payloads.

## [0.7.0] — 2026-11-08

### Added
- **Bars & downbeats** — measure-level structure on top of the beat grid:
  - `detect_bars()` — groups the beat grid into 4/4 bars; downbeat = first
    beat of each bar. Confidence flag (0.0 when the kick anchor is weak,
    meaning the downbeat phase is off-by-one-beat ambiguous).
  - `AnalysisResult.bars: Bars | None` with `Bar` model (index,
    beat_indices, downbeat_time/start_time/end_time, frame/end_frame/
    downbeat_frame) — frame math mirrors the beat-grid convention.
  - JSON export: `bars` (time + frames), `downbeats`, `barCount`,
    `downbeatConfidence`.
  - Remotion: `barsInFrames`, `downbeatsInFrames`, `barPeriodInFrames`,
    `barCount`, `downbeatConfidence` in the data; `useBarIndex()`,
    `useBarProgress()`, `useIsOnBar()` in the `useBeats.ts` hook.
  - HyperFrames: `bar` + `downbeat` timeline events.
  - After Effects: `BAR N` + `BAR N ↓` comp markers.
  - CSV: `bar` and `downbeat` row types.
  - FCPXML: `BAR N` + `BAR N ↓` markers.
  - HTML report: bar strip panel with downbeat ticks.
- MCP `analyze_audio` lean payload now includes `bars`/`downbeats`
  (cheap, always-on).
- CLI `analyze` prints the bar count and first bars.
- 13 new tests (bar grouping, confidence fallback, per-exporter bar
  presence + frame math, end-to-end on a synthetic 120 BPM kick+hat track).

## [0.2.0] — 2026-10-11

### Added
- Real spectral analysis engine (numpy STFT, rectified spectral flux)
- BPM estimation: autocorrelation + octave disambiguation + parabolic
  refinement, with `--min-bpm/--max-bpm` hints; click-track accuracy ±1 BPM
- Beat grid phase-locked to the **kick drum** (low-band envelope), with
  onset-circular-mean fallback for low-free tracks
- Raw onset ("hit") detection with adaptive thresholds and strengths
- 6 frequency bands (sub/bass/lowMid/mid/highMid/treble) per analysis frame,
  resamplable to any video fps
- Spectral centroid, loudness envelope, waveform peaks
- Song-structure sections with relative energy labels (quiet/mid/high/peak)
- Exporters: `json`, `remotion` (+ `useBeats.ts` React hook),
  `hyperframes` (+ data-hf snippet), `ae` (After Effects JSX comp markers),
  `csv` (Premiere/Resolve markers), `fcpxml` (FCP/Resolve)
- `--fps` flag: every export gains true frame numbers
- `spectrumalyzer report`: self-contained interactive HTML report
- `spectrumalyzer formats` and `analyze --stdout`
- Python API: `from spectrumalyzer import analyze` (typed dataclasses)
- 44-test pytest suite with ground-truth synthetic fixtures
- GitHub Actions CI (pytest + ruff)

### Changed
- **Breaking**: replaced the fake `spectrum` key (RMS time-slices with
  synthetic frequency labels) with the real `bands` matrix; legacy consumers
  can use `to_legacy_dict()` (bpm/beats/beatTimes unchanged)
- **Breaking**: `numpy>=1.24` is now a dependency (real FFT is not feasible
  in acceptable pure-Python time)
- Package rebuilt on src layout + PEP 621 `pyproject.toml`

### Removed
- `build_script.py` (dev artifact that copied the CLI into `$HOME`)
- empty `gui_report.py` stub (replaced by `spectrumalyzer report`)

### Fixed
- `min_interval` parameter was ignored (hardcoded 2.0 s → 12 beats on real
  music); beat spacing is now derived from detected tempo
- `--format` flag was ignored; multi-format selection now honored

## [0.1.0] — 2026-10-11

- Initial PyPI release: energy-based beat detection, median-interval BPM,
  JSON + Remotion output (superseded by 0.2.0's real DSP engine)

## [0.3.0] — 2026-10-11

### Added
- **Local embedding layer** — semantic hearing on top of the DSP engine:
  - Model home `~/.config/spectrumalyzer/embedding/` (XDG + `SPECTRUMALYZER_HOME` override)
  - Preferred model `google/embeddinggemma-300m` (current small Gemma; HF-gated —
    accept the Gemma license + HF_TOKEN); automatic fallback to the non-gated
    `sentence-transformers/all-MiniLM-L6-v2` so it works out of the box
  - `spectrumalyzer model pull | status`
  - `spectrumalyzer describe AUDIO` — natural-language description + mood /
    energy / flavor / use-case tags, hybrid-scored: embedding similarity +
    measured feature profiles (tempo, dBFS energy, brightness, bass, transient
    density, section contrast)
  - `spectrumalyzer find "query" DIR` — semantic search over an audio library
    with a persistent embedding index (mtime/size-fresh cache)
  - `analyze --embed` — adds `description` + `tags` to JSON output
- Optional dependency extra: `pip install "spectrumalyzer[embedding]"`
- Honest tempo gating: pulseless material (ambient/pads/noise) now reports
  `bpm: 0` instead of an invented tempo; `bpmConfidence` now folds in onset
  salience (noise ≈ 0.01, click tracks ≈ 0.96) — it was near 1.0 for noise before
- Absolute loudness (`loudnessDb`, dBFS) added to analysis + exports: per-track
  normalization had erased the quiet-master vs loud-master distinction
- 15 new tests (fake embedder — deterministic, no network); 74 total

### Fixed
- Beat grid no longer locks to off-beat hi-hats on low-pulse tracks (kick-anchored
  phase refinement extended)

## [0.4.0] — 2026-10-11

### Changed
- **Single install**: sentence-transformers moved into the base dependencies —
  `pip install spectrumalyzer` now includes the full semantic-hearing stack.
  The `[embedding]` extra is gone (it was never actually declared in v0.3.0's
  packaging metadata — caught by the new packaging contract tests).
- Model *weights* still download on demand: `describe` / `find` /
  `analyze --embed` now auto-pull on first use (one-time ~90 MB), or run
  `spectrumalyzer model pull` upfront.
### Added
- Packaging contract tests that pin the one-install policy.

## [0.5.0] — 2026-10-11

### Added
- **MCP server** (`spectrumalyzer mcp`, stdio) — spectrumalyzer as native
  tools for AI agents: analyze_audio, describe_audio, find_music,
  export_beats, render_report, model_status + a spectrumalyzer://formats
  resource. Structured error payloads; lean payloads by default.
- Shared embedding lifecycle (CLI + MCP auto-pull weights identically).
- `mcp>=1.2` joins the base dependencies (single-install policy);
  requires-python bumped to >=3.10 (MCP SDK floor).
- Protocol-layer tests via FastMCP.call_tool/list_tools + a real stdio
  JSON-RPC wire test. 93 tests total.

## [0.5.1] — 2026-10-11

### Changed
- Default branch renamed `master` → `main` (modern convention; keeps the
  documented skill-install URL working: `npx skills add
  github.com/Dream-Pixels-Forge/spectrumalyzer/tree/main/skills/`)
- Agent-skill installation documented in the README (MCP client registration
  for Claude Desktop / pi + `npx skills add` for skill-aware agents)
- PyPI project links updated to the `main` branch

## [0.5.2] — 2026-10-11

### Fixed
- README skill-install command: the skills CLI takes `owner/repo/subpath`,
  not GitHub's `tree/<branch>/` URL syntax (verified live — found + installed
  the skill to 13 agent platforms).

## [0.6.0] — 2026-11-02

### Added
- **Trimmer** — make a short version of a long track for video use:
  - `spectrumalyzer trim AUDIO_OR_VIDEO [--length 90] [-o out.mp3]
    [--crossfade 0.5] [--preview]` — picks the most worthwhile window
    (loudness + onset density + section energy), snaps the cuts to the beat
    grid, and cuts the source with ffmpeg (short crossfades, no clicks).
  - Works on video files: the video is cut to the same window.
  - No-op with an honest notice when the track is already short enough.
- Python API: `spectrumalyzer.trim(path, target_seconds, output, crossfade)`
  plus `select_trim_window` / `trim_audio` / `TrimSelection` (pure window
  selection is unit-testable without ffmpeg).
- MCP tool `trim_audio` (structured window + reasons + written file).
- 15 new tests (window-selection logic + real ffmpeg cuts).
