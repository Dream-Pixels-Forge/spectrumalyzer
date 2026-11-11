# GOAL: spectrumalyzer — v1.4.0 DAW project stubs pipeline

**Status: complete (2026-11-11, released).** Progress: dev-notes/PROGRESS.md.

## Problem
Composers and motion designers sync visuals to music in a DAW. The v1.0.0
cut-list (CSV/JSON) is data-only: a human re-types times into the DAW.
Roadmap v0.4 item: "Ableton Live / FLP / REAPER project stubs — markers as
tempo-warped project items." The fix: generate openable project stubs with
markers pre-embedded from the analysis (bars, sections, key, BPM) — no CSV
middleman for the DAW round-trip.

## Design (decisions, documented)
- **Pure text generators, no DAW dependency.** REAPER's `.RPP` and Ableton's
  `.als` are text formats; we emit minimal valid project files with an audio
  item (source path) + markers on a track. Testable without a DAW install.
- **FLP is binary + proprietary schema** — skipped, documented why (stays a
  later item with a real test vector).
- **DaVinci Resolve scripting** — deferred to v1.5 (needs a running Resolve
  instance; cannot be exercised headlessly here).
- **Markers land on the v0.7 bar grid** (downbeats, labeled `BAR N`), plus
  section markers (`SECTION <label>`). No bars (pulseless) → 0 markers.
- **`bpm is None` / no bars → 120.0 tempo fallback** (documented in `daw.py`
  and docs).

## Goal (measurable) — all shipped
1. **`exporters/daw.py`**:
   - [x] `export_reaper(result, source_path, out_path)` → `.RPP` with tempo =
         detected BPM, PPQ 480, audio item at t=0, BAR/SECTION markers, valid
         `<REAPER_PROJECT>` structure
   - [x] `export_ableton(result, source_path, out_path)` → `.als` with
         tempoMap entry, audio clip (source path), marker track; documented
         minimal subset
   - [x] Both return the written `Path`; raise `FileNotFoundError` on bad input
2. **CLI**: [x] `spectrumalyzer daw AUDIO --da reaper|ableton [-o OUT]`
3. **Tests** — TDD:
   - [x] 11 new tests (structure, tempo, marker count, media item, pulseless
         fallback, section markers, error case, CLI parsing, package exports)
   - [x] Full suite green (202 total), ruff clean
4. **Docs**: [x] CHANGELOG v1.4.0, [x] ROADMAP DAW stub item struck (shipped
   note), [x] PROGRESS, [x] GOAL
5. **Release**: [x] bump 1.4.0, tag v1.4.0, PyPI, three-way gate + wheel
   verify (`daw.py` present)

## Anti-drift
- No new dependencies (pure stdlib text emit; numpy only for any math).
- FLP and Resolve scripting are documented deferrals, not silent skips.
- Markers come from the v0.7 bar grid (downbeats); pulseless → 0 markers.
- BPM None → 120.0 fallback.
- Tests assert on file structure, no DAW install required.

## Verification
1. `PYTHONPATH=".pydeps:src:tests" python3 -m pytest tests/` → 202 green
2. `PYTHONPATH=".pydeps:src" python3 -m ruff check src/ tests/` → clean
3. Generated real `.RPP` + `.als` from a 120-BPM track, inspected by eye
4. Bump 1.4.0 → tag → release → three-way gate + wheel check

## Estimated Effort
~1 hour: 2 exporters + CLI + 11 tests + release cycle. **Shipped 2026-11-11.**
