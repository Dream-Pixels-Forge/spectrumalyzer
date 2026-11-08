# GOAL: spectrumalyzer — v0.9.0 beat impact tiers pipeline

**Status: active.** Started 2026-11-08. Progress: dev-notes/PROGRESS.md.

## Problem
Beats come out of the engine with a single `strength` (0..1 onset energy)
but no *creative* classification. Video editors want "drop the cut on the
heavy beat, use a normal beat for a subtle pulse" — they have to eyeball
the strength values themselves. The roadmap's "beat-strength quantiles →
impact tiers" item (pre-label beats as normal/accent/downbeat-adjacent for
automatic edit emphasis) is the gap.

## Goal (measurable)
Add a tier layer on top of the existing beat grid:

1. **Tiers** (`impact_tiers` on the model / `Bar`-free, ride the grid):
   - [x] Three tiers: `downbeat` (bar start), `accent` (upper strength
         quantile, non-downbeat beats), `normal` (everything else)
   - [x] `tier` field on each `Beat` (string: "downbeat" | "accent" |
         "normal" | None when no bars); quantile threshold exposed
         (`accent_quantile`, default 0.75 — top quarter of non-downbeat
         beats)
   - [x] `accent_quantile` configurable: `analyze(accent_quantile=0.75)`,
         CLI `--accent-q 0.75`
   - [x] No bars / pulseless track → tiers stay None, no invented emphasis
2. **Exporters** (all 6, test-verified):
   - [x] JSON: `tier` inside each beat dict; `impactTiers` summary
         (counts + threshold)
   - [x] Remotion: `beatTiers[]` (string per beat) + `impactTiers` summary
   - [x] CSV: `tier` column
   - [x] AE / FCPXML / HyperFrames: tier reflected in marker labels
3. **MCP** `analyze_audio` payload includes tiers; **CLI** summary prints
   tier counts
4. **Tests** — TDD:
   - [x] Synthetic track: downbeats = bar starts labeled "downbeat";
         strongest non-downbeats labeled "accent"; rest "normal"
   - [x] `accent_quantile=0.5` → more accents than 0.9
   - [x] Pulseless track (no grid) → tier None everywhere, counts 0
   - [x] Exporter payloads contain tiers
   - [x] Full suite green (141 = 132 + 9 new)
5. **Docs**: CHANGELOG v0.9.0, ROADMAP strike item, PROGRESS update
6. **Release**: bump, tag v0.9.0, PyPI, three-way gate — DONE 2026-11-08 (three-way: pyproject == tag == PyPI == 0.9.0, wheel verified)

## Anti-drift
- Tiers ride the existing bar grid + beat strength — no new DSP.
- "accent" = statistical (quantile), not a claim of musical loudness.
  Document that.
