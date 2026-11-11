"""Precomputed analysis cache — instant re-exports without re-analysis.

The cache stores the full AnalysisResult (as ``to_dict`` JSON) under
``~/.cache/spectrumalyzer/`` (or ``$SPECTRUMALYZER_CACHE_DIR`` for tests),
keyed by a stable hash of the source file's ``(mtime_ns, size)`` plus the
package's major version and the decode sample rate.

Key design (documented, not a content hash):
- mtime + size: cheap to compute, and any real edit to the file bumps one.
  A content-hash (sha256 of bytes) is a v2 refinement if mtime/size
  collisions ever matter in the wild; for analysis re-exports this is
  sufficient and far cheaper on large files.
- major version: a release that changes the analysis contract (new engine,
  new model fields) bumps the major version, which invalidates every older
  cache entry so stale results never silently apply.
- sample rate: analysis is resampled internally; caching per decode rate
  keeps the entry accurate.

The cache never stores embedding output (``--embed``). Embeddings are
model-dependent and are re-run on every invocation; only the deterministic
DSP result is cached.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spectrumalyzer._version import __version__
from spectrumalyzer.model import AnalysisResult


def cache_root() -> Path:
    """Directory for cache files — env override first, then XDG default."""
    override = os.environ.get("SPECTRUMALYZER_CACHE_DIR")
    if override:
        p = Path(override)
        p.mkdir(parents=True, exist_ok=True)
        return p
    p = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "spectrumalyzer"
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass(frozen=True)
class CacheKey:
    """A stable, hashable cache identity for one (file, version, sr)."""

    digest: str

    def __str__(self) -> str:
        return self.digest

    @classmethod
    def from_file(cls, path: str, version: str | None = None,
                  sample_rate: int = 44100) -> CacheKey:
        st = os.stat(path)
        # major version only: a minor bump (new optional fields) keeps the
        # cache valid; a major bump (contract change) invalidates it.
        major = (version or __version__).split(".")[0]
        raw = f"{st.st_mtime_ns}:{st.st_size}:{major}:{sample_rate}"
        digest = hashlib.sha1(raw.encode()).hexdigest()[:16]
        return cls(digest)


class CacheStore:
    """JSON-on-disk cache of analysis results under ``cache_root()``."""

    @property
    def dir(self) -> Path:
        return cache_root()

    def _path(self, key: CacheKey) -> Path:
        return self.dir / f"{key.digest}.json"

    def has(self, key: CacheKey) -> bool:
        return self._path(key).exists()

    def load(self, key: CacheKey) -> AnalysisResult | None:
        """Load a cached result, or None when absent / corrupt (caller re-analyzes)."""
        p = self._path(key)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return AnalysisResult.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            # Corrupt or an older incompatible entry: fall back to re-analysis
            # rather than crash.
            return None

    def save(self, key: CacheKey, result: AnalysisResult) -> None:
        """Atomically write a result (temp file + rename) so a crash never
        leaves a half-written cache entry."""
        p = self._path(key)
        # Ensure the source path is preserved in metadata so a cache hit
        # can reconstruct result.path (to_dict does not emit path directly).
        data = result.to_dict()
        data.setdefault("metadata", {})["path"] = result.path
        fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".cache-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            os.replace(tmp, p)  # atomic on POSIX
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def clear(self) -> int:
        """Remove all cache files; returns the number deleted."""
        n = 0
        for f in self.dir.glob("*.json"):
            f.unlink()
            n += 1
        return n


def analyze_cached(
    path: str,
    version: str | None = None,
    sample_rate: int = 44100,
    *,
    use_cache: bool = True,
    analyze_fn: Any | None = None,
    **analyze_kwargs: Any,
) -> tuple[AnalysisResult, bool]:
    """Analyze ``path``, returning ``(result, cache_hit)``.

    On a cache hit the stored result is returned and no ffmpeg decode or DSP
    runs. On a miss (or with ``use_cache=False``) it calls ``analyze_fn``
    (default: the real :func:`spectrumalyzer.api.analyze`), writes the result
    back, and returns ``(result, False)``.

    A corrupt cache file is treated as a miss (re-analysis), never a crash.
    """
    if analyze_fn is None:
        from spectrumalyzer.api import analyze

        analyze_fn = analyze

    store = CacheStore()
    key = CacheKey.from_file(path, version=version, sample_rate=sample_rate)

    if use_cache:
        cached = store.load(key)
        if cached is not None:
            return cached, True

    result = analyze_fn(path, sample_rate=sample_rate, **analyze_kwargs)
    if use_cache:
        store.save(key, result)
    return result, False
