---
name: spectrumalyzer
version-note: v0.4.0 — single install; embedding built in; weights auto-pull on first use
description: Audio-reactive analysis toolkit for motion graphics — spectral-flux beat detection, BPM, 6 frequency bands, song sections, and frame-native exports for Remotion, HyperFrames, After Effects, FCPXML and CSV workflows
---
## Skill Overview

spectrumalyzer turns music into animation-ready data: beats, BPM, onsets,
frequency bands, loudness and song sections — exported as frame-native JSON,
React hooks, marker scripts and timeline formats for the tools creatives
actually use.

## Skill Actions

### analyze(audio, options) / CLI `spectrumalyzer analyze`

**Key parameters:**
- `--fps 24|25|30|60` — adds true frame numbers to every export (REQUIRED for remotion/hyperframes/ae/csv/fcpxml)
- `--format a,b,c` — any of: json, remotion, hyperframes, ae, csv, fcpxml
- `--min-bpm/--max-bpm` — tempo search hints for tricky tracks
- `--stdout` — pipe JSON; `--no-bands/--no-sections` — skip heavy analysis
- `--output/-o` — base path; each format appends its suffix

**Returns (JSON / AnalysisResult):**
- `bpm`, `bpmConfidence`, `beats[]` (time + frame + strength), `onsets[]`
- `bands.matrix` — 6 rows×frames (sub/bass/lowMid/mid/highMid/treble, 0..1)
- `sections[]` (quiet/mid/high/peak with energy), `centroid[]`, `loudness[]`
- `durationInFrames`, `beatsInFrames`, `bandsByFrame` (when fps given)

### report(audio) / CLI `spectrumalyzer report`

Self-contained HTML: canvas waveform + beat grid, band heatmap, section strip.

## Example Usage

```bash
spectrumalyzer analyze track.mp3 --fps 30 --format remotion,csv,ae
spectrumalyzer report track.mp3 -o report.html
python3 -c "from spectrumalyzer import analyze; r = analyze('track.mp3', fps=30); print(r.bpm, r.beats_as_frames()[:5])"
```

## Creative Mapping Cheatsheet

- beats (grid) → camera cuts, scale pops, scroll steps (uniform, kick-locked)
- onsets → hit accents, glitch flashes, particle bursts (raw transients)
- bands.sub/bass → camera shake, glow pulses · treble → sparkles
- centroid → blur/color temperature · loudness → opacity/zoom pressure
- sections → narrative pacing, scene grouping

## Dependencies

- Python 3.9+, numpy (auto-installed), system ffmpeg
- No network access needed; all analysis is local and deterministic

## Status (v0.2.0)

- Real DSP engine (v0.1.0's "spectrum" was NOT a real FFT — replaced)
- 44-test suite green; click-track BPM accuracy ±1 (90/120/140 verified)
- 6 exporters verified for frame math, XML validity, JSX balance

## Semantic Hearing (v0.3)

- Single install ships the embedding stack; weights auto-pull on first use.
- `spectrumalyzer model pull` / `model status` — local embedding model at
  ~/.config/spectrumalyzer/embedding (EmbeddingGemma-300m preferred; MiniLM fallback)
- `spectrumalyzer describe AUDIO` — NL description + mood/energy/flavor/use tags
  (hybrid: embedding similarity + measured feature profiles)
- `spectrumalyzer find "query" DIR` — semantic library search (persistent index)
- `analyze --embed` — adds description + tags to JSON
- Honesty gates: pulseless material → bpm 0 + "no clear pulse"; bpmConfidence
  includes onset salience; energy uses absolute dBFS
