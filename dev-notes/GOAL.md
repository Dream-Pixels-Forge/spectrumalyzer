# GOAL: spectrumalyzer v0.2.0 — Creative Toolkit Upgrade

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
