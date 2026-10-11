# Changelog

All notable changes to spectrumalyzer are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [Semantic Versioning](https://semver.org/).

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
