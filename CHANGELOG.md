# Changelog

All notable changes to spectrumalyzer are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [Semantic Versioning](https://semver.org/).

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
