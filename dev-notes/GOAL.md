# GOAL: spectrumalyzer — v0.8.0 musical key detection pipeline

**Status: active.** Started 2026-11-08. Progress: dev-notes/PROGRESS.md.

## Problem
Sections are energy-novelty (structural), not harmonic. Creative workflows
want to know the *key* of a track/section to drive color grades, palette
choices, and "what chords fit" — currently the tool says nothing about
harmony. The roadmap's v0.3 item 2 ("musical key detection — chroma profile
→ key, Camelot wheel → palette/color-grade suggestion") is the gap.

## Goal (measurable)
Add a harmonic layer: detect the musical key from the chromagram and map it
to a creative color/palette suggestion.

1. **Chroma extraction** (`analysis/harmony.py`, pure numpy, no new deps):
   - [x] Per-pitch-class energy (12 bins C..B) via log-spaced harmonic
         binning of the magnitude spectrum, weighted toward the harmonic
         (low-mid) range and away from the percussive high band
   - [x] Aggregate to a single 12-dim chroma vector over the whole track,
         and optionally per section (section keys)
2. **Key detection** (Krumhansl–Schmuckler):
   - [x] 24 K-S profiles (12 major + 12 minor)
   - [x] Cross-correlate chroma against all 24; best-fit wins
   - [x] `key` (e.g. "E minor"), `key_confidence` (0..1 sharpness: gap
         between best and 2nd best, plus profile salience gate)
   - [x] **Honesty gate**: near-flat / noise-floor chroma → key "unknown",
         confidence 0 (no invented harmony on pulseless/ambient material)
3. **Creative mapping** (the point of the feature):
   - [x] `camelot` (wheel position, e.g. "10A") from detected key
   - [x] `palette` suggestion — a small dict (mood + 3 hex anchors + a
         color-grade label) derived from the Camelot position
         (minor = cool/desaturated, major = warm/lifted, high wheel # =
         energetic/saturated, low = calm). Deterministic, no LLM.
   - [x] `key`/`camelot`/`palette` in the model + JSON export + MCP
         `analyze_audio` lean payload
4. **API**: `detect_key(pcm, sr)` public; `analyze(key=True)` opt-in
   default ON (cheap), results on `AnalysisResult.key: KeyResult | None`
5. **Tests** — TDD with deterministic synthetic fixtures (no ML):
   - [x] A-minor / C-major chord fixtures → correct key within confidence
   - [x] White noise / flat chroma → key "unknown", confidence 0
   - [x] Camelot mapping table correctness (spot-check a few keys)
   - [x] Palette suggestion present + well-formed for a detected key
   - [x] JSON + MCP payload contain key/camelot/palette
   - [x] Full suite green (existing 122 + new)
6. **Docs**: README + ROADMAP (strike v0.3 item 2), CHANGELOG v0.8.0
7. **Release**: version bump, tag v0.8.0, PyPI, three-way verification gate

## Verification gates
- [x] `pytest` all green (132 = 122 + 10 new key tests)
- [x] `ruff` clean
- [x] End-to-end on synthetic C-major / A-minor / noise tracks: key detected
      correctly (C major conf 0.64, A minor conf 0.37), noise → "unknown";
      all 6 exporters + JSON + MCP carry key/camelot/palette
- [ ] Three-way version check: pyproject == git tag == PyPI (on release)

## Anti-drift
- Pure numpy + the existing STFT — **no new dependencies, no ML models.**
  If this drifts toward neural chord-recognition or per-chord segmentation,
  stop and re-check this file. This release is *whole-track / section* key,
  not chord transcription.
- The palette mapping is an opinionated creative default, not a claim of
  "the right" color. Document it as such.
- Honest confidence: if the harmonic content is weak, say so (key unknown),
  don't force a key.
