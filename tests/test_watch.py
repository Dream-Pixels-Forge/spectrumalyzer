"""Tests for watch mode (v1.3): re-analyze + re-export on file change.

Pure stdlib polling — no watchdog/inotify dependency. ``poll()`` compares the
file's (mtime_ns, size) against the last-seen key and re-runs the analysis
(through the v1.1 precomputed cache) only when it changed. The run loop is
clock-injectable so tests never sleep in CI.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from spectrumalyzer.watch import WatchSession, change_key


def _write_wav(path: Path, n_frames: int = 44100) -> Path:
    import wave

    rng = np.random.default_rng(0)
    pcm = (rng.standard_normal(n_frames) * 0.05).astype(np.float32)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes((pcm * 32767).astype(np.int16).tobytes())
    return path


# ---------------------------------------------------------------------------
# change_key
# ---------------------------------------------------------------------------

def test_change_key_reflects_mtime_and_size(tmp_path):
    f = _write_wav(tmp_path / "a.wav")
    k1 = change_key(str(f))
    # same file, immediately: identical key
    assert k1 == change_key(str(f))
    # touch (bump mtime) -> different key
    future = time.time() + 50
    import os

    os.utime(f, (future, future))
    k2 = change_key(str(f))
    assert k1 != k2


def test_change_key_size_change(tmp_path):
    f = _write_wav(tmp_path / "s.wav", n_frames=44100)
    k1 = change_key(str(f))
    _write_wav(f, n_frames=2 * 44100)  # bigger file
    k2 = change_key(str(f))
    assert k1 != k2


# ---------------------------------------------------------------------------
# poll()
# ---------------------------------------------------------------------------

def test_poll_unchanged_returns_false(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_CACHE_DIR", str(tmp_path / "cache"))
    f = _write_wav(tmp_path / "w.wav")
    out = tmp_path / "out.json"
    sess = WatchSession(str(f), str(out))
    # first poll: nothing seen yet -> treat as changed (initial export)
    assert sess.poll() is True
    assert out.exists()
    # second poll, file untouched -> no re-export
    assert sess.poll() is False
    # write count: only the first poll wrote
    assert sess.changes == 1


def test_poll_after_file_change_reexports(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_CACHE_DIR", str(tmp_path / "cache"))
    f = _write_wav(tmp_path / "w2.wav")
    out = tmp_path / "out2.json"
    sess = WatchSession(str(f), str(out))
    sess.poll()  # initial
    assert sess.changes == 1

    # mutate the file (new content -> new mtime+size)
    _write_wav(f, n_frames=2 * 44100)
    assert sess.poll() is True
    assert sess.changes == 2
    assert out.exists()


def test_poll_uses_cache_and_reexports(tmp_path, monkeypatch):
    """A file change triggers re-analysis through the v1.1 cache + re-export.

    The watch engine's job: detect the (mtime, size) change, run
    ``analyze_cached`` (which is a cache *hit* when content is unchanged),
    and re-write the export. The cache layer's hit/miss is asserted directly
    against ``CacheStore`` — the session reports it via ``last_cache_hit``.
    """
    from spectrumalyzer.analysis.cache import CacheKey, CacheStore

    monkeypatch.setenv("SPECTRUMALYZER_CACHE_DIR", str(tmp_path / "cache"))
    f = _write_wav(tmp_path / "hit.wav")
    out = tmp_path / "hit.json"
    sess = WatchSession(str(f), str(out))
    sess.poll()  # initial: computes + writes cache
    assert sess.last_cache_hit is False
    assert sess.changes == 1

    # Verify the cache entry exists under the expected key
    store = CacheStore()
    key = CacheKey.from_file(str(f))
    assert store.has(key), "initial poll must have written a cache entry"

    # Now mutate content (different size) -> new key -> cache miss + re-run
    _write_wav(f, n_frames=2 * 44100)
    assert sess.poll() is True
    assert sess.last_cache_hit is False  # new key, not in cache
    assert sess.changes == 2
    assert out.exists()


def test_on_change_callback_fires(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_CACHE_DIR", str(tmp_path / "cache"))
    f = _write_wav(tmp_path / "cb.wav")
    out = tmp_path / "cb.json"
    fired = []
    sess = WatchSession(str(f), str(out), on_change=lambda r, hit: fired.append(hit))
    sess.poll()
    sess.poll()  # unchanged
    _write_wav(f, n_frames=2 * 44100)
    sess.poll()
    # fired only on actual changes (2 of the 3 polls)
    assert len(fired) == 2


# ---------------------------------------------------------------------------
# run() with an injectable clock (no real sleeps in tests)
# ---------------------------------------------------------------------------

def test_run_with_fake_clock_and_stop_event(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_CACHE_DIR", str(tmp_path / "cache"))
    f = _write_wav(tmp_path / "run.wav")
    out = tmp_path / "run.json"

    # fake clock: advance 1 s per "poll", stop after 4 ticks
    clock = {"t": 0.0}

    def fake_sleep(s: float) -> None:
        clock["t"] += s

    sess = WatchSession(str(f), str(out), sleep_fn=fake_sleep)
    # stop after 4 polls
    import threading

    stop = threading.Event()
    n = sess.run(interval=1.0, max_polls=4, stop_event=stop)
    # initial poll + 3 = 4 polls; 1 change (initial) counted
    assert n == 1
    assert out.exists()


def test_run_stops_on_event(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_CACHE_DIR", str(tmp_path / "cache"))
    f = _write_wav(tmp_path / "stop.wav")
    out = tmp_path / "stop.json"

    import threading

    stop = threading.Event()
    clock_calls = {"n": 0}

    def fake_sleep(s: float) -> None:
        clock_calls["n"] += 1
        stop.set()  # stop after the first sleep

    sess = WatchSession(str(f), str(out), sleep_fn=fake_sleep)
    n = sess.run(interval=1.0, stop_event=stop)
    assert n == 1  # initial poll only
    assert clock_calls["n"] == 1


def test_run_reexports_on_change_within_loop(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_CACHE_DIR", str(tmp_path / "cache"))
    f = _write_wav(tmp_path / "loop.wav")
    out = tmp_path / "loop.json"

    import threading

    stop = threading.Event()
    poll_count = {"n": 0}

    def fake_sleep(s: float) -> None:
        poll_count["n"] += 1
        # on the 2nd poll, mutate the file so the 3rd sees a change
        if poll_count["n"] == 2:
            _write_wav(f, n_frames=2 * 44100)
        if poll_count["n"] >= 4:
            stop.set()

    sess = WatchSession(str(f), str(out), sleep_fn=fake_sleep)
    n = sess.run(interval=0.1, stop_event=stop)
    # initial change + the mid-loop mutation = 2 re-exports
    assert n == 2
    assert out.exists()


# ---------------------------------------------------------------------------
# CLI wiring (non-blocking: just verify the subcommand parses + dry path)
# ---------------------------------------------------------------------------

def test_watch_cli_subcommand_parses(tmp_path):
    from spectrumalyzer.cli import build_parser

    p = build_parser()
    f = _write_wav(tmp_path / "cli.wav")
    args = p.parse_args(
        ["watch", str(f), "--interval", "0.5", "--format", "json", "--fps", "30"]
    )
    assert args.command == "watch"
    assert args.interval == 0.5
    assert args.fps == 30
