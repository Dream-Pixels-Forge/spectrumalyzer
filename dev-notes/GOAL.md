# GOAL: spectrumalyzer — v1.3.0 watch mode pipeline

**Status: complete (2026-11-11, released).** Progress: dev-notes/PROGRESS.md.

## Problem
Iterative edit sessions (trimming a video bed, auditioning cuts, exporting at
different fps) re-run `analyze` / `cuts` / `report` by hand every time the
source changes. The roadmap's v0.4 item ("Watch mode — re-analyze on file
change") is the fix: watch a file, and when its mtime + size change, re-run
the analysis and re-export — no re-decode-and-DSP if nothing actually changed
(the v1.1 cache already makes a no-op re-export instant).

## Design (decision, documented)
- **Polling, not inotify.** `WatchSession.poll()` compares the file's
  `(st_mtime_ns, st_size)` against the last-seen key. On change it re-analyzes
  (through the v1.1 precomputed cache, so unchanged content is a free hit) and
  re-exports to the same output path. Polling is portable (Windows/macOS/Linux,
  no `watchdog` dependency) and is the right tool for a CLI loop that the user
  Ctrl-C's.
- **No new dependencies.** Pure stdlib polling; reuses `analyze_cached` (v1.1)
  so a file that only touched mtime but not content is still a cache hit.
- **Callback seam.** `WatchSession` takes an optional `on_change(result, hit)`
  hook so the same engine drives the CLI loop, an MCP tool, and tests without
  importing any CLI/printing code.

## Goal (measurable)
1. **Watch engine** (`watch.py`, pure, testable):
   - [x] `WatchSession(path, out_path, *, fps=None, formats=("json",), ...)`
   - [x] `.poll() -> bool` — returns True when the file changed and was
         re-exported; False when unchanged.
   - [x] `.run(interval=1.0, max_polls=None, stop_event=None)` — the blocking
         loop; returns the number of re-analyses performed.
   - [x] `change_key(path) -> (mtime_ns, size)` — the comparison tuple,
         exported for tests and the cache-key parity check.
2. **CLI** `watch`: `spectrumalyzer watch AUDIO [--interval S] [--format X,Y]
   [--fps N] [-o OUT]` — re-analyze + re-export on every change, one line per
   change to stderr, Ctrl-C to stop.
3. **MCP tool** `watch_file` — poll-based (one poll per call, non-blocking) so
   an agent can drive it: returns `{"changed": bool, "cacheHit": bool, ...}`.
4. **Tests** — TDD:
   - [x] `change_key` reflects mtime + size
   - [x] `poll()` unchanged → False, no re-export
   - [x] `poll()` after file change → True, re-export written
   - [x] `run()` with a stop_event + fake clock does the right number of polls
         (injectable `sleep_fn`, no sleep-dependence in CI)
   - [x] `on_change` callback fires exactly on changes
   - [x] Full suite green (191 total), ruff clean
5. **Docs**: [x] CHANGELOG v1.3.0, [x] ROADMAP watch item struck, [x] PROGRESS
6. **Release**: bump, tag v1.3.0, PyPI, three-way gate

## Anti-drift
- No new dependencies (no watchdog / inotify). Polling is the documented
  choice; inotify is a v2 refinement if latency matters.
- Watch reuses the v1.1 `analyze_cached` path: a touch that bumps mtime but
  leaves content identical is still a cache hit (instant).
- `run()` must be injectable with a fake clock so tests don't sleep in CI.
