# GOAL: spectrumalyzer — v0.2.0 → v0.5.x pipeline (SHIPPED)

**Status: complete.** All gates below shipped (v0.2.0 creative toolkit, v0.3.0 semantic
hearing, v0.4.0 single install, v0.5.x MCP server). Latest release: **v0.5.2** (2026-10-11).
Next goals: see docs/ROADMAP.md. Progress history: dev-notes/PROGRESS.md.

## Problem
v0.1.0 shipped with: fake "spectrum" (RMS time-slices labeled as frequencies, dead FFT code),
a dead `min_interval` parameter (hardcoded 2.0s → 23 BPM on real music), seconds-only output
(creative tools need frames), 2 exporters, no tests, no package structure.

## Goal (measurable)
Transform spectrumalyzer into a real audio-reactive toolkit for creative users:

1. **Real analysis engine** (numpy-based):
   - [x] STFT + spectral-flux onset detection (replaces energy-diff hack)
   - [x] Tempo estimation via onset-envelope autocorrelation, ±3 BPM accuracy on click tracks 60–180 BPM
   - [x] Beat grid (uniform, phase-aligned) + raw onset "hits"
   - [x] 6 real frequency bands (sub/bass/lowMid/mid/highMid/treble) per analysis frame, resampled to video fps
   - [x] Spectral centroid + loudness envelope + waveform peaks
   - [x] Song sections (energy-novelty segmentation with relative energy labels)
2. **Frame-native export** — [x] `--fps` converts every timestamp to frame numbers at 24/25/30/60 fps
3. **6 exporters, each test-verified** — [x] json (rich), remotion (+TS hook), hyperframes (+snippet),
   aftereffects (.jsx marker script), csv (Premiere/Resolve/spreadsheet), fcpxml (FCP/Resolve)
4. **HTML visual report** — [x] self-contained canvas waveform + beat markers + band heatmap + section timeline
5. **Clean package** — [x] src layout, PEP 621 pyproject, console script, public `analyze()` API
6. **Tests** — [x] pytest suite green, synthetic fixtures (click tracks at known BPM) assert BPM within ±3
7. **CI** — [x] ci.yml (pytest) alongside existing release.yml
8. **Docs** — [x] README rewrite, docs/ROADMAP.md (investigation findings + future features), SKILL.md update

## Verification gates
- [x] `pytest` — all green (93 as of v0.5.2; CI green on main 2026-10-11)
- [x] `spectrumalyzer analyze <fixture> --fps 30 --format json,csv,remotion,ae,fcpxml,hyperframes` — all 6 files written
- [x] `spectrumalyzer report <fixture> -o report.html` — opens, contains canvas + beat data
- [x] Click-track test: detected BPM within ±3 of 120
- [x] No dead code from v0.1.0 remains (build_script.py, gui_report.py stub, root spectrumalyzer.py removed)

## v0.3.0 addition: semantic hearing layer — SHIPPED
- [x] Embedding model lives at ~/.config/spectrumalyzer/embedding/ (XDG + SPECTRUMALYZER_HOME override)
- [x] Default model google/embeddinggemma-300m (current small Gemma; gated → needs HF token), auto-fallback all-MiniLM-L6-v2 (non-gated, works out of the box)
- [x] `model pull` / `model status` commands
- [x] `describe AUDIO` → natural-language description + mood/energy/genre/use tags
- [x] `find "query" DIR` → semantic search over an audio library (cached in store)
- [x] `analyze --embed` adds description + tags to JSON
- [x] All tests run on a deterministic FakeEmbedder (no network in CI); real-model smoke test skipped when absent
- [x] Honest scoping: embeddings add semantic UNDERSTANDING (describe/tag/search); beat accuracy stays with the DSP engine

## v0.4.0 addition: single install — SHIPPED
- [x] Embedding stack ships in the base package (no separate install)

## v0.5.0 addition: MCP server — SHIPPED
- [x] `spectrumalyzer mcp` — stdio MCP server (FastMCP), discoverable by any MCP client
- [x] Tools: analyze_audio, describe_audio, find_music, export_beats, render_report, model_status
- [x] Reuses embedding auto-pull lifecycle (shared with CLI, no duplication)
- [x] Lean payloads (no huge matrices unless requested)
- [x] `mcp` SDK becomes a base dependency (single-install policy); requires-python >=3.10
- [x] Tests call tools via FastMCP.call_tool (real protocol layer, no mocking the protocol)
- [x] Release v0.5.0 + MANDATORY three-way verification

## v0.5.1/0.5.2 addition: docs & canonical URLs — SHIPPED
- [x] Default branch `master` → `main`; PyPI project links updated
- [x] Skill-install command verified live: `npx skills add owner/repo/subpath` (tree/ syntax unsupported)
