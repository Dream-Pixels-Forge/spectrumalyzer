"""Tests for the precomputed analysis cache (v1.1).

The cache keys on (mtime, size, version-major, sample_rate) — cheap, no
content hashing. On a hit, analyze_cached returns the stored result without
decoding the file (no ffmpeg). On a miss it re-analyzes and writes back.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np

from spectrumalyzer._version import __version__
from spectrumalyzer.analysis.cache import (
    CacheKey,
    CacheStore,
    analyze_cached,
)
from spectrumalyzer.model import AnalysisResult, Bar, Bars, Beat, ImpactTiers, KeyResult, Section

# ---------------------------------------------------------------------------
# AnalysisResult.from_dict round-trip
# ---------------------------------------------------------------------------

def _rich_result() -> AnalysisResult:
    beats = [
        Beat(time=0.0, strength=0.9, frame=0, tier="downbeat"),
        Beat(time=0.5, strength=0.5, frame=15, tier="normal"),
        Beat(time=1.0, strength=0.7, frame=30, tier="accent"),
        Beat(time=1.5, strength=0.4, frame=45, tier="normal"),
    ]
    bars = Bars(
        bars=[Bar(index=0, beat_indices=[0, 1, 2, 3], downbeat_time=0.0,
                  start_time=0.0, end_time=2.0, downbeat_frame=0, frame=0, end_frame=60)],
        confidence=0.9,
    )
    key = KeyResult(root=0, key="C major", confidence=0.6,
                    camelot="1B", palette={"mood": "calm", "label": "warm airy",
                                            "hexes": ["#111111", "#222222", "#333333"]},
                    chroma=[0.1] * 12)
    return AnalysisResult(
        path="song.mp3",
        duration=4.5,
        sample_rate=44100,
        bpm=120.0,
        bpm_confidence=0.9,
        beat_grid=beats,
        onsets=[Beat(time=0.12, strength=1.0)],
        sections=[Section(start=0.0, end=2.0, energy=0.4, label="quiet"),
                   Section(start=2.0, end=4.5, energy=1.0, label="peak")],
        bars=bars,
        key=key,
        impact_tiers=ImpactTiers(accent_quantile=0.75,
                                 counts={"downbeat": 1, "accent": 1, "normal": 2}),
        fps=30.0,
        metadata={"version": "1.1.0", "analyzer": "spectrumalyzer"},
    )


def test_from_dict_roundtrip():
    r = _rich_result()
    r2 = AnalysisResult.from_dict(r.to_dict(fps=30.0))
    assert r2.bpm == r.bpm
    assert r2.beat_count == r.beat_count
    assert r2.beat_grid[0].tier == "downbeat"
    assert r2.beat_grid[2].tier == "accent"
    assert r2.bars is not None and len(r2.bars.bars) == 1
    assert r2.key.key == "C major"
    assert r2.key.camelot == "1B"
    assert r2.impact_tiers.counts == {"downbeat": 1, "accent": 1, "normal": 2}
    assert len(r2.sections) == 2
    assert len(r2.onsets) == 1


# ---------------------------------------------------------------------------
# CacheKey + CacheStore
# ---------------------------------------------------------------------------

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


def test_cache_key_stable_for_same_file(tmp_path):
    f = _write_wav(tmp_path / "a.wav")
    k1 = CacheKey.from_file(str(f), version="1.1.0", sample_rate=44100)
    k2 = CacheKey.from_file(str(f), version="1.1.0", sample_rate=44100)
    assert k1 == k2


def test_cache_key_changes_when_mtime_changes(tmp_path, monkeypatch):
    f = _write_wav(tmp_path / "a.wav")
    k1 = CacheKey.from_file(str(f), version="1.1.0", sample_rate=44100)
    # touch the file (bump mtime into the future)
    future = time.time() + 100
    os.utime(f, (future, future))
    k2 = CacheKey.from_file(str(f), version="1.1.0", sample_rate=44100)
    assert k1 != k2


def test_cache_key_changes_with_version(tmp_path):
    f = _write_wav(tmp_path / "a.wav")
    k1 = CacheKey.from_file(str(f), version="1.1.0", sample_rate=44100)
    k2 = CacheKey.from_file(str(f), version="2.0.0", sample_rate=44100)
    assert k1 != k2  # major bump invalidates old caches


def test_cache_key_ignores_minor_version(tmp_path):
    f = _write_wav(tmp_path / "a.wav")
    k1 = CacheKey.from_file(str(f), version="1.1.0", sample_rate=44100)
    k2 = CacheKey.from_file(str(f), version="1.9.0", sample_rate=44100)
    # same major (1) -> same key (cache still valid within a major)
    assert k1 == k2


def test_cache_key_changes_with_sample_rate(tmp_path):
    f = _write_wav(tmp_path / "a.wav")
    k1 = CacheKey.from_file(str(f), version="1.1.0", sample_rate=44100)
    k2 = CacheKey.from_file(str(f), version="1.1.0", sample_rate=48000)
    assert k1 != k2


def test_store_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_CACHE_DIR", str(tmp_path / "cache"))
    store = CacheStore()
    r = _rich_result()
    key = CacheKey("abc123")
    store.save(key, r)
    assert store.has(key)
    loaded = store.load(key)
    assert loaded.bpm == r.bpm
    assert loaded.beat_grid[0].tier == "downbeat"
    assert loaded.key.key == r.key.key


def test_store_load_corrupt_file_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_CACHE_DIR", str(tmp_path / "cache"))
    store = CacheStore()
    key = CacheKey("corrupt")
    (store.dir / f"{key}.json").write_text("{not valid json", encoding="utf-8")
    assert store.load(key) is None


def test_store_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_CACHE_DIR", str(tmp_path / "cache"))
    store = CacheStore()
    assert store.load(CacheKey("never-saved")) is None


# ---------------------------------------------------------------------------
# analyze_cached hit / miss
# ---------------------------------------------------------------------------

def test_analyze_cached_miss_then_hit(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_CACHE_DIR", str(tmp_path / "cache"))
    f = _write_wav(tmp_path / "hit.wav")

    calls = {"n": 0}

    def fake_analyze(path, sample_rate=44100, **_kw):
        calls["n"] += 1
        return _rich_result()

    r1, hit1 = analyze_cached(str(f), analyze_fn=fake_analyze)
    assert hit1 is False and calls["n"] == 1
    # second call must be served from cache — no extra analyzer call
    r2, hit2 = analyze_cached(str(f), analyze_fn=fake_analyze)
    assert hit2 is True and calls["n"] == 1
    # the hit returned the same reconstructed result
    assert r2.bpm == r1.bpm and r2.key.key == r1.key.key


def test_analyze_cached_file_change_is_miss(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_CACHE_DIR", str(tmp_path / "cache"))
    f = _write_wav(tmp_path / "mm.wav")
    calls = {"n": 0}

    def fake_analyze(path, sample_rate=44100, **_kw):
        calls["n"] += 1
        return _rich_result()

    analyze_cached(str(f), analyze_fn=fake_analyze)
    # mutate the file (bigger size + new mtime) -> new cache key -> miss
    _write_wav(f, n_frames=2 * 44100)
    analyze_cached(str(f), analyze_fn=fake_analyze)
    assert calls["n"] == 2


def test_analyze_cached_corrupt_falls_back(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_CACHE_DIR", str(tmp_path / "cache"))
    f = _write_wav(tmp_path / "corrupt.wav")

    def fake_analyze(path, sample_rate=44100, **_kw):
        return _rich_result()

    # first, a real entry
    analyze_cached(str(f), analyze_fn=fake_analyze)
    key = CacheKey.from_file(str(f), version=__version__, sample_rate=44100)
    # clobber it with corrupt JSON
    (CacheStore().dir / f"{key}.json").write_text("{broken", encoding="utf-8")
    calls = {"n": 0}

    def counting(path, sample_rate=44100, **_kw):
        calls["n"] += 1
        return _rich_result()

    _, hit = analyze_cached(str(f), analyze_fn=counting)
    # corrupt cache treated as a miss — re-analyzed, not a crash
    assert hit is False and calls["n"] == 1


def test_analyze_cached_use_cache_false_never_reads(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_CACHE_DIR", str(tmp_path / "cache"))
    f = _write_wav(tmp_path / "nocache.wav")
    calls = {"n": 0}

    def fake_analyze(path, sample_rate=44100, **_kw):
        calls["n"] += 1
        return _rich_result()

    # with use_cache off, every call re-analyzes (and writes nothing)
    _, h1 = analyze_cached(str(f), analyze_fn=fake_analyze, use_cache=False)
    _, h2 = analyze_cached(str(f), analyze_fn=fake_analyze, use_cache=False)
    assert h1 is False and h2 is False
    assert calls["n"] == 2
