"""Audio decoding via ffmpeg/ffprobe (system tools), PCM into numpy.

Design: keep the system dependency surface at exactly ffmpeg/ffprobe — the
universal media swiss army knife — so every codec ffmpeg supports "just works"
(mp3, wav, flac, ogg, m4a, aac, opus, video containers with audio tracks, ...).
"""

from __future__ import annotations

import shutil
import subprocess
import sys

import numpy as np

DEFAULT_SAMPLE_RATE = 44100


class FFmpegMissingError(RuntimeError):
    """Raised when ffmpeg/ffprobe are not on PATH."""


def _require(binary: str) -> None:
    if shutil.which(binary) is None:
        raise FFmpegMissingError(
            f"'{binary}' not found on PATH. Install ffmpeg (e.g. apt install ffmpeg / brew install ffmpeg)."
        )


def probe_duration(path: str) -> float:
    """Duration of the file in seconds (0.0 when it cannot be determined)."""
    _require("ffprobe")
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True, text=True, check=True,
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as exc:
        print(f"warning: could not probe duration of {path}: {exc}", file=sys.stderr)
        return 0.0


def probe_sample_rate(path: str) -> int:
    """Native sample rate of the first audio stream (fallback 44100)."""
    _require("ffprobe")
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=sample_rate",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True, text=True, check=True,
        )
        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return DEFAULT_SAMPLE_RATE


def decode_pcm(path: str, sample_rate: int = DEFAULT_SAMPLE_RATE) -> np.ndarray:
    """Decode to mono float32 PCM in [-1, 1] at ``sample_rate``.

    Raises FFmpegMissingError when ffmpeg is absent, and RuntimeError when the
    file has no decodable audio.
    """
    _require("ffmpeg")
    cmd = [
        "ffmpeg", "-v", "error",
        "-i", path,
        "-vn",                     # drop video streams
        "-ac", "1",                # mono
        "-ar", str(sample_rate),   # resample
        "-f", "f32le",             # 32-bit float little-endian
        "-",
    ]
    result = subprocess.run(cmd, check=False, capture_output=True)
    if result.returncode != 0 or len(result.stdout) == 0:
        stderr = result.stderr.decode("utf-8", "replace")[:400]
        raise RuntimeError(f"ffmpeg could not decode audio from {path}: {stderr}")
    return np.frombuffer(result.stdout, dtype=np.float32).copy()


def load(path: str, sample_rate: int = DEFAULT_SAMPLE_RATE) -> tuple[np.ndarray, float, int]:
    """Convenience: returns (pcm, duration_seconds, sample_rate)."""
    pcm = decode_pcm(path, sample_rate)
    duration = probe_duration(path)
    if duration <= 0.0:
        duration = len(pcm) / sample_rate
    return pcm, float(duration), sample_rate


def which_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")
