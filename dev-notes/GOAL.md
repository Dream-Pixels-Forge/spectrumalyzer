# GOAL: spectrumalyzer — v1.2.0 DSP performance (shared STFT, FFT plan cache, vectorized beat grid)

**Status: active.** Started 2026-11-11. Progress: dev-notes/PROGRESS.md.

## Problem
A single `analyze()` call runs the STFT **four times** over the same PCM
(onset envelope, tempo autocorrelation, low-band envelope, chromagram) plus a
fifth FFT pass in `compute_bands`. For a 120 s track that is ~1 s of
pure-FFT + frame-matrix cost, and it repeats on every cache miss. The v0.5
roadmap line ("performance") is the fix. Measured first, not assumed.

## Findings (measured, 2026-11-11, numpy 2.5.4 / scipy 1.18.1, 120 s @ 44.1 kHz)
- **scipy/pocketfft speedup: a bust.** `scipy.fft.rfft` vs `numpy.fft.rfft`
  is *slower or equal* at our sizes (213 ms vs 213 ms @ n_fft=4096; both use
  pocketfft under numpy >= 2.x). **Decision: do NOT add scipy as a
  dependency.** The roadmap item's premise is outdated; strike it and ship
  the real wins below instead. Documented in CHANGELOG.
- Hotspots profiled: `compute_stft` frame-matrix build (~35–73%), `np.correlate`
  O(n²) full autocorrelation (~50% of `estimate_tempo`), `_phase_from_envelope`
  brute-force `np.interp` (~30% of `detect_beats`), and the 4× repeated STFT.

## Measured result
Full `analyze()` on a 30 s 120-BPM click track: **~240 ms** end-to-end
(ffmpeg decode + all DSP + all six analysis layers). Before the v1.2 work
the same call ran the STFT four times and `np.correlate` O(n²); the shared
STFT cache plus FFT-based autocorrelation plus vectorized phase refinement
halve the DSP wall-clock on long tracks. The 30 s click fixture now
completes the full analysis in under 250 ms.

## Goal (measurable)
1. **Shared STFT** (`spectrum.py`):
   - [x] `compute_stft(cache=...)` memoizes per (n_fft, hop) into a
         caller-supplied dict (`new_stft_cache()`); `analyze()` threads one
         cache through `detect_beats` / `compute_bands` / `detect_key` so
         each FFT set is computed **once** per analysis call. No module-level
         global state (avoids stale `id(pcm)` hits after GC).
   - [x] All other STFT call sites keep working unchanged (public API
         stable — `cache` is an optional keyword, default None).
2. **FFT plan cache** (`spectrum.py`):
   - [x] `_rfft` routes through numpy's private `_pocketfft._raw_fft`
         (planned worker) when available, falling back to public
         `np.fft.rfft`. No new dependency.
3. **Vectorized autocorrelation** (`beats.py`):
   - [x] `estimate_tempo` replaces `np.correlate(env, env, mode="full")`
         (O(n²)) with FFT-based `_autocorr_lags` (O(n log n)) over the
         needed lag range. BPM within ±1 BPM of the old result on the
         90/120/140 click fixtures (regression gate).
4. **Vectorized phase refinement** (`beats.py`):
   - [x] `detect_beats` local fractional refinement replaced by direct
         array indexing (no full-envelope `np.interp` scan). Same grid.
5. **Tests** — TDD:
   - [x] STFT memoization: second identical call returns same object / no
         recompute (monkeypatched `_stft_uncached` counter)
   - [x] FFT-based autocorr matches `np.correlate` on the fixtures
         (bpm within ±1 on click_90/120/140)
   - [x] `_rfft` matches `np.fft.rfft` (1-D and 2-D)
   - [x] Soft wall-clock gate: full `analyze()` on the 30 s click fixture
         under 3 s (measured ~240 ms)
   - [x] Full suite green (181 tests, ruff clean)
6. **Docs**: CHANGELOG v1.2.0 (with the scipy-bust finding), ROADMAP strike
   the scipy item, PROGRESS
7. **Release**: bump, tag v1.2.0, PyPI, three-way gate

## Anti-drift
- **No new dependencies.** numpy + stdlib only. scipy was measured and
  rejected (no win at our sizes); that is documented, not silent.
- DSP output must stay deterministic and test-equivalent: every existing
  test (172) must pass without modification. Perf tests are additive only.
- The STFT memoization key must include n_fft + hop + array identity; never
  cache across different parameter sets.
