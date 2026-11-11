# GOAL: spectrumalyzer — v1.1.0 precomputed analysis cache pipeline

**Status: active.** Started 2026-11-11. Progress: dev-notes/PROGRESS.md.

## Problem
Every `analyze` / `report` / `cuts` run decodes the file (ffmpeg) and runs
the full DSP. Re-exporting the same track at a different fps, or re-running
a pipeline, re-does all of it. The roadmap's v0.5 item ("precomputed cache
keyed by file hash — instant re-exports at different fps without
re-analysis") is the fix: cache the analysis result, keyed by
mtime + size + package version, under `~/.cache/spectrumalyzer/`.

## Goal (measurable)
1. **Cache layer** (`analysis/cache.py`, pure, testable):
   - [x] `CacheKey.from_file(path, version, sample_rate)` — stable hash of
         (mtime ns, size, version-major, sample_rate)
   - [x] `CacheStore.load(key) / save(key, result)` — JSON on disk under
         `~/.cache/spectrumalyzer/` (overridable via `SPECTRUMALYZER_CACHE_DIR`
         for tests), one file per key, atomic write
   - [x] `AnalysisResult.from_dict()` — reconstruct a full result (beats,
         onsets, sections, bars, key, impact tiers) from JSON
   - [x] Cache hit rule: same mtime+size+version-major+sample_rate; any
         change → miss. Cache does NOT store embedding output (`--embed`
         still runs fresh each time — it's an optional model call).
2. **API**:
   - [x] `analyze_cached(path, ...)` — check cache first, decode+analyze on
         miss and write it back. Returns `(result, cache_hit: bool)`.
3. **CLI**: `analyze` reads the cache by default; `--no-cache` forces
   re-analysis; prints `cache: hit/miss` in the summary
4. **Tests** — TDD:
   - [x] `from_dict` round-trips every model field
   - [x] same key + hit → no ffmpeg, returns cached result
   - [x] file mtime/size change → miss
   - [x] version-major bump → miss (old caches never silently apply)
   - [x] store is atomic + doesn't crash on corrupt cache file (falls back
         to re-analysis)
   - [x] Full suite green (157 + 15 = 172)
5. **Docs**: CHANGELOG v1.1.0, ROADMAP strike the cache item, PROGRESS
6. **Release**: bump, tag v1.1.0, PyPI, three-way gate

## Anti-drift
- Cache is keyed on mtime+size, NOT content hash (cheap; content-hash is a
  v2 refinement if collisions matter in the wild). Document that.
- No new dependencies. The cache is plain JSON + stdlib hashing.
- `analyze_cached` never mutates the cache entry for `--embed` — embeddings
  are model-dependent and re-run.
