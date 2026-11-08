# ROADMAP — spectrumalyzer investigation & future

> Deep-investigation notes from the v0.2.0 rebuild (2026-10-11): what was
> broken, what was added for creative users, and where the tool goes next.

## 1. What the v0.1.0 audit found

| Finding | Severity | Detail |
|---|---|---|
| Fake spectrum | critical | Output "spectrum" was RMS energy sliced into 128 time-chunks with fabricated frequency labels (`fft_transform` existed but was never called) |
| Dead `min_interval` | critical | Hardcoded to `max(0.1, 2.0)` = 2.0 s → only 12 beats / "23 BPM" detected on a 53 s music track |
| Dead `--format` flag | major | Both JSON files were always written regardless of the flag |
| Seconds-only output | major | Creative tools (Remotion/AE/Resolve) work in frames |
| No tests, no package | major | Loose modules on PyPI via `py_modules`; `gui_report.py` was an empty stub; `build_script.py` wrote a stray copy to `$HOME` |
| O(n) pure-Python loops | major | Every sample visited in Python; minutes of CPU on real tracks |

## 2. What v0.2.0 added (the creative-toolkit layer)

- **Real DSP**: STFT (Hann, DC-removed), rectified spectral-flux onsets,
  autocorrelation tempo with octave disambiguation + parabolic refinement,
  **kick-anchored phase lock** (low-band envelope — fixes grids locking onto
  off-beat hats), 6-band power with per-band adaptive normalization,
  spectral centroid, loudness envelope, waveform peaks.
- **Frame-native exports** at any `--fps`, verified by tests for the exact
  frame math (`time_to_frame`, `resample_to_fps`).
- **6 formats**: rich JSON, Remotion (+`useBeats.ts` hook with `useBeatIndex`,
  `useBeatProgress`, `useIsOnBeat`, `useBeatPop` springs), HyperFrames
  (timeline events + `hf-seek` snippet), After Effects JSX comp markers,
  marker CSV, FCPXML.
- **HTML report**: single self-contained file (canvas waveform, beat grid,
  band heatmap, section strip) — no server, no assets.
- **Engineering**: src layout, PEP 621, console script, public `analyze()`
  API, 44-test suite with ground-truth fixtures (90/120/140 BPM click tracks,
  band-separation sines, kick+hat drum pattern), CI workflow.

## 3. Verified ecosystem fit

- **Remotion**: `beatsInFrames[]` + hook → zero runtime math in components;
  `bandsByFrame` rows align 1:1 with `useCurrentFrame()`.
- **HyperFrames**: events → `data-hf-*` timing attributes / `hf-seek` detail.
- **After Effects**: `comp.markerProperty.setValueAtTime()` inside an
  undo group — snap layers/keyframes to beats.
- **FCPXML 1.8**: rational-time markers (`15/30s`) open in FCP & Resolve.
- **CSV**: Premiere/Resolve marker-import extensions + spreadsheets.

## 4. Next features (ranked for creative value)

> Scoping note: the v0.3/v0.4/v0.5 labels below are the *original* feature scoping
> from the v0.2.0 rebuild. v0.3.0–v0.5.2 have since shipped with different content
> (semantic hearing layer, single install, MCP server — see CHANGELOG.md); none of
> the items below shipped in those releases. They remain the v1.x backlog.

### v0.3 — musical intelligence
- [x] **Downbeat/bar detection** — kick-anchored phase gives the beat; add
      bar (4/4) grouping → exporters gain `barsInFrames` for measure-level
      cuts ("cut every 4 beats" workflows). **Shipped in v0.7.0**: `bars`
      layer on the beat grid with `useBarIndex`/`useBarProgress`/`useIsOnBar`
      Remotion helpers, BAR markers in AE/FCPXML/CSV, bar events in
      HyperFrames, bar strip in the HTML report. Confidence flag for
      weak-kick tracks.
- [x] **Musical key detection** (chroma profile → key) — creative mapping:
      Camelot wheel → palette/color-grade suggestion. **Shipped in v0.8.0**:
      `detect_key()` (Krumhansl-Schmuckler over a numpy chromagram, no ML,
      no new deps), `KeyResult` (root/key/confidence/chroma/camelot/palette),
      `key_to_camelot()` (24-key Camelot table), `palette_for_key()`
      (deterministic color-grade from the Camelot slot). Key + Camelot +
      palette in all 6 exporters, JSON, MCP, CLI summary, HTML report;
      "unknown" (confidence 0) on pulseless/ambient material.
- [x] **Beat-strength quantiles → "impact tiers"** — pre-label beats as
      normal/accent/downbeat-adjacent for automatic edit emphasis.
      **Shipped in v0.9.0**: `impact_tiers()` labels each beat
      `downbeat` / `accent` / `normal` from the bar grid + beat strength,
      with a configurable `--accent-q` quantile; tier labels in all 6
      exporters, JSON `beatTiers`/`impactTiers`, CSV `tier` column.

### v0.4 — workflow integration
- [ ] **Cut-list generator** — `spectrumalyzer cuts track.mp3 --every 4beats
      --section peak` → edit-decision CSV/JSON for Premiere/Resolve scripting.
- [ ] **Ableton Live / FLP / REAPER project stubs** — markers as tempo-warped
      project items for composers syncing visuals to music.
- [ ] **DaVinci Resolve scripting** (DaVinci API) — direct timeline marker
      injection, no CSV middleman.
- [ ] **Watch mode** — re-analyze on file change for iterative edit sessions.

### v0.5 — performance & reach
- [ ] **Streaming/CLI speed**: ffmpeg pipe decode already streams; move STFT
      to `scipy.fft` (pocketfft) when scipy present — ~2× on long tracks.
- [ ] **GPU path** (optional `cupy` extra) for hour-long sets.
- [ ] **Web/WASM build** (Pyodide) — in-browser analysis for web-based editors
      (Remotion Studio plugins, HyperFrames Studio).
- [ ] **Precomputed cache** (`.spectralyzer-cache.json`) keyed by file hash —
      instant re-exports at different fps without re-analysis.

### v1.0 — polish
- [ ] Confidence-based warnings ("low confidence — try --min-bpm hints")
- [ ] Multi-language READMEs, docs site, GIF demo in README
- [ ] macOS Notarized binary via PyInstaller for non-Python editors

## 5. Known tradeoffs (honesty ledger)

- Octave errors: strongly syncopated 8th-note-heavy music may report double
  or half tempo within default 60–200 range; `--min-bpm/--max-bpm` hints fix it.
- Phase lock prefers the kick; tracks without low-frequency pulse fall back to
  onset circular mean (accurate to ~1 analysis frame ≈ 12 ms).
- Sections are energy-novelty based — structural, not harmonic (no chord
  awareness yet; see v0.3 key detection).
- FCPXML uses integer fps for rational time; 29.97 fps DF timecode is not
  represented (drops are rare for marker workflows).

## 6. Embedding layer status (v0.3, 2026-10-11)

Shipped: model lifecycle at ~/.config/spectrumalyzer/embedding (EmbeddingGemma-300m
preferred, MiniLM fallback), describe/tag/find/--embed, feature-profile-anchored
tags, honest tempo gating (bpm=0 when onset salience is low), absolute dBFS
loudness.

Calibration backlog (needs a labeled real-music validation set):
- [ ] Tag bank profiles are coarse — real mastered music clusters tightly
      (energy 0.75-0.95, density 0.3-0.5), so most tracks read "aggressive /
      moderate". Calibrate profiles against genre-labeled real tracks.
- [ ] Search discrimination on sonically similar tracks is weak (cosines
      0.3-0.6). Add query-side feature parsing (embed the query against the
      descriptor bank to infer a feature vector, then hybrid-score).
- [ ] Matryoshka truncation (embeddinggemma 768→128/64) for smaller indices.
- [ ] CLAP-style audio encoder for true audio↔text shared space (the current
      layer is text↔text with measurement-anchored text).
