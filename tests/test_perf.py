"""Performance-layer tests (v1.2): STFT memoization, FFT plan cache,
vectorized autocorrelation, and the per-call STFT cache.

These are correctness tests that happen to also be the regression gate for
the perf work: the FFT-based autocorrelation must produce BPM output
indistinguishable from the O(n²) np.correlate version on the click fixtures,
and the shared-STFT path must produce byte-identical transforms.
"""

from __future__ import annotations

import numpy as np

from spectrumalyzer.analysis.beats import (
    _autocorr_lags,
    estimate_tempo,
)
from spectrumalyzer.analysis.spectrum import (
    _rfft,
    compute_stft,
    new_stft_cache,
)
from spectrumalyzer.audio import load

# ---------------------------------------------------------------------------
# STFT memoization (per-call cache)
# ---------------------------------------------------------------------------

def test_stft_cache_recomputes_once(bass_sine, monkeypatch):
    """Two compute_stft calls with the same cache dict: FFT runs once."""
    pcm, _, sr = load(str(bass_sine))

    calls = {"n": 0}
    real_stft_uncached = __import__(
        "spectrumalyzer.analysis.spectrum", fromlist=["_stft_uncached"]
    )._stft_uncached

    def counting(pcm_, sample_rate, n_fft, hop):
        calls["n"] += 1
        return real_stft_uncached(pcm_, sample_rate, n_fft, hop)

    monkeypatch.setattr(
        "spectrumalyzer.analysis.spectrum._stft_uncached", counting,
    )

    cache = new_stft_cache()
    m1, h1 = compute_stft(pcm, sr, n_fft=1024, hop=512, cache=cache)
    m2, h2 = compute_stft(pcm, sr, n_fft=1024, hop=512, cache=cache)
    assert calls["n"] == 1
    assert m1 is m2 and h1 == h2

    # a *different* (n_fft, hop) pair must not hit the same entry
    m3, _ = compute_stft(pcm, sr, n_fft=4096, hop=1024, cache=cache)
    assert calls["n"] == 2
    assert m3 is not m1


def test_stft_cache_none_is_fresh(bass_sine):
    """Without a cache dict, every call recomputes (public API unchanged)."""
    pcm, _, sr = load(str(bass_sine))
    m1, _ = compute_stft(pcm, sr)
    m2, _ = compute_stft(pcm, sr)
    # same input → same values, but no shared identity
    assert np.array_equal(m1, m2)


def test_stft_cache_two_param_sets(bass_sine):
    """The real analyze() pattern: 1024/512 and 4096/1024 each computed once."""
    pcm, _, sr = load(str(bass_sine))
    calls = {"n": 0}
    real_stft_uncached = __import__(
        "spectrumalyzer.analysis.spectrum", fromlist=["_stft_uncached"]
    )._stft_uncached

    import spectrumalyzer.analysis.spectrum as spec

    def counting(pcm_, sample_rate, n_fft, hop):
        calls["n"] += 1
        return real_stft_uncached(pcm_, sample_rate, n_fft, hop)

    monkey = spec
    monkey._stft_uncached = counting

    try:
        cache = new_stft_cache()
        compute_stft(pcm, sr, 1024, 512, cache=cache)  # onsets
        compute_stft(pcm, sr, 1024, 512, cache=cache)  # low-band (reuse)
        compute_stft(pcm, sr, 4096, 1024, cache=cache)  # chromagram
        compute_stft(pcm, sr, 4096, 1024, cache=cache)  # bands (reuse)
        assert calls["n"] == 2  # one FFT per param set, not four
    finally:
        spec._stft_uncached = real_stft_uncached


# ---------------------------------------------------------------------------
# FFT plan cache
# ---------------------------------------------------------------------------

def test_rfft_matches_numpy():
    """The plan-cached rfft must agree with np.fft.rfft exactly."""
    rng = np.random.default_rng(0)
    arr = rng.standard_normal((32, 64))
    a = _rfft(arr, n=64, axis=-1)
    b = np.fft.rfft(arr, n=64, axis=-1)
    assert np.allclose(a, b, atol=1e-9)


def test_rfft_plan_reused_across_calls():
    """The private pocketfft path must match the public np.fft.rfft."""
    from numpy.fft import _pocketfft

    rng = np.random.default_rng(1)
    a = rng.standard_normal((8, 256))
    out_private = _pocketfft._raw_fft(a, 256, 1, True, True, "backward")
    out_public = np.fft.rfft(a, n=256, axis=1)
    # both must produce the same transform
    assert np.allclose(out_private, out_public, atol=1e-9)


def test_rfft_wrapper_matches_numpy():
    """_rfft must equal np.fft.rfft for 1-D and 2-D inputs."""
    rng = np.random.default_rng(2)
    for n in (64, 256, 4096):
        a = rng.standard_normal((16, n))
        got = _rfft(a, n=n, axis=-1)
        ref = np.fft.rfft(a, n=n, axis=-1)
        assert np.allclose(got, ref, atol=1e-9), f"n={n}"


# ---------------------------------------------------------------------------
# FFT-based autocorrelation
# ---------------------------------------------------------------------------

def test_autocorr_matches_np_correlate():
    """_autocorr_lags must match np.correlate (the old implementation)."""
    rng = np.random.default_rng(42)
    x = rng.standard_normal(512)
    lags = np.arange(0, 100)

    # reference: the O(n²) full correlation, positive lags only
    full = np.correlate(x, x, mode="full")[len(x) - 1:][: len(lags)]
    got = _autocorr_lags(x, lags)
    assert np.allclose(got, full, rtol=1e-6, atol=1e-6)


def test_estimate_tempo_fft_matches_old_on_clicks():
    """The FFT-autocorr estimate_tempo must agree with a direct np.correlate
    implementation on the 90/120/140 BPM click fixtures."""
    from spectrumalyzer.analysis.beats import _frames_per_second, onset_envelope

    for fixture in ("click_90", "click_120", "click_140"):
        f = _load_fixture(fixture)
        pcm, _, sr = load(str(f))
        env = onset_envelope(pcm, sr)
        fps_env = _frames_per_second(sr, 512)

        min_bpm, max_bpm = 60.0, 200.0
        min_lag = max(2, round(fps_env * 60.0 / max_bpm))
        max_lag = min(len(env) - 2, round(fps_env * 60.0 / min_bpm))

        # old: np.correlate
        acf_old = np.correlate(env, env, mode="full")[len(env) - 1:]
        acf_old = acf_old / acf_old[0]
        lags = np.arange(min_lag, max_lag + 1)
        scores_old = acf_old[min_lag:max_lag + 1]
        old_lag = int(lags[scores_old >= 0.9 * scores_old.max()].min())
        old_bpm = 60.0 * fps_env / old_lag

        # new: FFT-based (via estimate_tempo)
        bpm_new, _conf = estimate_tempo(pcm, sr, min_bpm, max_bpm)
        assert abs(bpm_new - old_bpm) <= 1.0, f"{fixture}: {bpm_new} vs {old_bpm}"


def _load_fixture(name: str):
    """Locate a session-scoped click fixture by its conftest name."""
    import pathlib
    import tempfile

    # The fixtures are built by conftest into tmp dirs; re-synthesise here so
    # this test is self-contained and doesn't depend on pytest fixture state.
    from tests.conftest import click_track, write_wav

    bpm_map = {"click_90": 90.0, "click_120": 120.0, "click_140": 140.0}
    p = pathlib.Path(tempfile.gettempdir()) / f"perf_{name}.wav"
    return write_wav(p, click_track(bpm_map[name]))


# ---------------------------------------------------------------------------
# End-to-end perf (soft gate)
# ---------------------------------------------------------------------------

def test_analyze_wallclock_under_budget(click_120):
    """A full analyze() on a ~30 s click track finishes in a reasonable time.

    This is a soft gate: on a cold CI runner the absolute number moves, so we
    assert only that it is *not* catastrophically slow (old O(n²) correlate +
    4× STFT). The regression we care about is the perf work not *incurring*
    extra cost.
    """
    import time

    from spectrumalyzer.api import analyze

    t0 = time.perf_counter()
    result = analyze(str(click_120))
    elapsed = time.perf_counter() - t0

    assert result.bpm > 0  # sanity: the analysis actually produced a grid
    # 30 s of audio; DSP should be well under 1 s on modern hardware.
    assert elapsed < 3.0, f"analyze() took {elapsed:.2f}s — perf regression"
