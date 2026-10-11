# GOAL: spectrumalyzer v0.3.0 — Local Embedding Layer ("the tool can hear")

## Problem
v0.1.0 shipped with: fake "spectrum" (RMS time-slices labeled as frequencies, dead FFT code),
a dead `min_interval` parameter (hardcoded 2.0s → 23 BPM on real music), seconds-only output
(creative tools need frames), 2 exporters, no tests, no package structure.

## Goal (measurable)
Transform spectrumalyzer into a real audio-reactive toolkit for creative users:

1. **Real analysis engine** (numpy-based):
   - [ ] STFT + spectral-flux onset detection (replaces energy-diff hack)
   - [ ] Tempo estimation via onset-envelope autocorrelation, ±3 BPM accuracy on click tracks 60–180 BPM
   - [ ] Beat grid (uniform, phase-aligned) + raw onset "hits"
   - [ ] 6 real frequency bands (sub/bass/lowMid/mid/highMid/treble) per analysis frame, resampled to video fps
   - [ ] Spectral centroid + loudness envelope + waveform peaks
   - [ ] Song sections (energy-novelty segmentation with relative energy labels)
2. **Frame-native export** — `--fps` converts every timestamp to frame numbers at 24/25/30/60 fps
3. **6 exporters, each test-verified**: json (rich), remotion (+TS hook), hyperframes (+snippet),
   aftereffects (.jsx marker script), csv (Premiere/Resolve/spreadsheet), fcpxml (FCP/Resolve)
4. **HTML visual report** — self-contained canvas waveform + beat markers + band heatmap + section timeline
5. **Clean package**: src layout, PEP 621 pyproject, console script, public `analyze()` API
6. **Tests**: pytest suite green, synthetic fixtures (click tracks at known BPM) assert BPM within ±3
7. **CI**: ci.yml (pytest) alongside existing release.yml
8. **Docs**: README rewrite, docs/ROADMAP.md (investigation findings + future features), SKILL.md update

## Verification gates
- [ ] `pytest` — all green
- [ ] `spectrumalyzer analyze <fixture> --fps 30 --format json,csv,remotion,ae,fcpxml,hyperframes` — all 6 files written
- [ ] `spectrumalyzer report <fixture> -o report.html` — opens, contains canvas + beat data
- [ ] Click-track test: detected BPM within ±3 of 120
- [ ] No dead code from v0.1.0 remains (build_script.py, gui_report.py stub, root spectrumalyzer.py removed)

## v0.3.0 addition (2026-10-11): semantic hearing layer
- [ ] Embedding model lives at ~/.config/spectrumalyzer/embedding/ (XDG + SPECTRUMALYZER_HOME override)
- [ ] Default model google/embeddinggemma-300m (current small Gemma; gated → needs HF token), auto-fallback all-MiniLM-L6-v2 (non-gated, works out of the box)
- [ ] `model pull` / `model status` commands
- [ ] `describe AUDIO` → natural-language description + mood/energy/genre/use tags
- [ ] `find "query" DIR` → semantic search over an audio library (cached in store)
- [ ] `analyze --embed` adds description + tags to JSON
- [ ] All tests run on a deterministic FakeEmbedder (no network in CI); real-model smoke test skipped when absent
- [ ] Honest scoping: embeddings add semantic UNDERSTANDING (describe/tag/search); beat accuracy stays with the DSP engine
