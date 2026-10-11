"""Shared test fixtures: synthetic audio with known ground truth.

Generated with numpy + stdlib `wave` (no ffmpeg needed to *create* fixtures;
ffmpeg is only needed to *decode* them, and the analyze pipeline does that).
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

SR = 44100


def write_wav(path: Path, samples: np.ndarray, sample_rate: int = SR) -> Path:
    """Write float samples in [-1, 1] as a 16-bit PCM wav."""
    clipped = np.clip(samples, -1.0, 1.0)
    pcm16 = (clipped * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm16.tobytes())
    return path


def click_track(
    bpm: float,
    duration_s: float = 24.0,
    sample_rate: int = SR,
    seed: int = 7,
) -> np.ndarray:
    """Metronome-like track: sharp clicks exactly on the beat + low noise bed."""
    rng = np.random.default_rng(seed)
    n = int(duration_s * sample_rate)
    audio = (rng.standard_normal(n) * 0.01).astype(np.float64)

    period = 60.0 / bpm
    click_len = int(0.03 * sample_rate)  # 30 ms
    t = np.arange(click_len) / sample_rate
    click = np.sin(2 * np.pi * 1000.0 * t) * np.exp(-t * 120.0)

    beat_time = 0.5  # start half a second in
    while beat_time < duration_s - 0.1:
        start = int(beat_time * sample_rate)
        end = min(start + click_len, n)
        audio[start:end] += click[: end - start] * 0.9
        beat_time += period
    return audio.astype(np.float32)


def sine_track(freq_hz: float, duration_s: float = 3.0, sample_rate: int = SR,
               amplitude: float = 0.5) -> np.ndarray:
    t = np.arange(int(duration_s * sample_rate)) / sample_rate
    return (amplitude * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


def two_section_track(sample_rate: int = SR, seed: int = 3) -> np.ndarray:
    """30 s quiet noise then 30 s loud noise — two obvious sections."""
    rng = np.random.default_rng(seed)
    quiet = rng.standard_normal(int(30 * sample_rate)) * 0.02
    loud = rng.standard_normal(int(30 * sample_rate)) * 0.45
    return np.concatenate([quiet, loud]).astype(np.float32)


@pytest.fixture(scope="session")
def click_120(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("audio") / "click_120.wav"
    return write_wav(p, click_track(120.0))


@pytest.fixture(scope="session")
def click_90(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("audio") / "click_90.wav"
    return write_wav(p, click_track(90.0))


@pytest.fixture(scope="session")
def click_140(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("audio") / "click_140.wav"
    return write_wav(p, click_track(140.0))


@pytest.fixture(scope="session")
def bass_sine(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("audio") / "bass_100hz.wav"
    return write_wav(p, sine_track(100.0))


@pytest.fixture(scope="session")
def treble_sine(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("audio") / "treble_8000hz.wav"
    return write_wav(p, sine_track(8000.0))


@pytest.fixture(scope="session")
def two_sections(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("audio") / "two_sections.wav"
    return write_wav(p, two_section_track())


@pytest.fixture
def fake_embedder():
    from fake_embedder import FakeEmbedder

    return FakeEmbedder()


@pytest.fixture(scope="session")
def pulseless_pad(tmp_path_factory) -> Path:
    """Sustained soft tones — no pulse whatsoever (ambient material)."""
    p = tmp_path_factory.mktemp("audio") / "pad.wav"
    t = np.arange(int(12 * SR)) / SR
    audio = 0.12 * np.sin(2 * np.pi * 220 * t) + 0.08 * np.sin(2 * np.pi * 330 * t)
    audio *= 0.5 + 0.5 * np.sin(2 * np.pi * 0.2 * t)
    return write_wav(p, audio.astype(np.float32))
