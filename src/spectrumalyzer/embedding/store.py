"""Embedding store — persistent semantic index for an audio library.

Lives next to the model at ~/.config/spectrumalyzer/embedding/index.json.
Each entry: file path -> {size, mtime, duration, bpm, summary, tags,
embedding[]}. Entries are reused while (size, mtime) are unchanged, so
re-running `find` on a library is instant after the first pass.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from spectrumalyzer.embedding.backend import default_model_dir, spectrumalyzer_home

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus", ".wma"}


def _store_path() -> Path:
    return default_model_dir() / "index.json"


class EmbeddingStore:
    """JSON-backed vector index with file-stat freshness checks."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else spectrumalyzer_home()
        self.model_dir = self.root / "embedding"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = _store_path()
        self.entries: dict[str, dict[str, Any]] = {}
        self.model_name: str = ""
        self._load()

    # ---- persistence -------------------------------------------------------
    def _load(self) -> None:
        if not self.index_path.exists():
            return
        try:
            data = json.loads(self.index_path.read_text())
            self.entries = data.get("entries", {})
            self.model_name = data.get("model", "")
        except (json.JSONDecodeError, OSError):
            self.entries = {}  # corrupt index -> start clean, never crash

    def save(self) -> None:
        payload = {"model": self.model_name, "entries": self.entries}
        self.index_path.write_text(json.dumps(payload))

    # ---- entries ------------------------------------------------------------
    @staticmethod
    def _stat_of(path) -> tuple[int, float]:
        st = Path(path).stat()
        return st.st_size, st.st_mtime

    def upsert_entry(self, path, summary: str, embedding: list[float],
                     tags: dict[str, Any] | None = None, bpm: float | None = None,
                     duration: float | None = None, stat: tuple[int, float] | None = None) -> None:
        if stat is not None:
            size, mtime = stat
        else:
            try:
                size, mtime = self._stat_of(path)
            except OSError:
                size, mtime = 0, 0.0  # path not on disk right now (moved/lib entry)
        self.entries[str(path)] = {
            "size": size,
            "mtime": mtime,
            "summary": summary,
            "tags": tags or {},
            "embedding": embedding,
            "bpm": bpm,
            "duration": duration,
        }

    # backwards-compatible alias used by early call sites
    def put(self, path, summary: str, embedding: list[float],
            tags: dict[str, Any] | None = None, stat: tuple[int, float] | None = None) -> None:
        self.upsert_entry(path, summary=summary, embedding=embedding, tags=tags, stat=stat)

    def get(self, path, stat: tuple[int, float]) -> dict[str, Any] | None:
        entry = self.entries.get(str(path))
        if entry and entry.get("size") == stat[0] and entry.get("mtime") == stat[1]:
            return entry
        return None

    # ---- search ------------------------------------------------------------
    def search(self, query: str, embedder, k: int = 10) -> list[dict[str, Any]]:
        if not self.entries:
            return []
        q = np.asarray(embedder.embed_one(query), dtype=np.float32)
        paths = list(self.entries.keys())
        matrix = np.asarray(
            [self.entries[p].get("embedding", [0.0]) for p in paths], dtype=np.float32
        )
        # guard against non-normalized legacy vectors
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        matrix = matrix / norms
        scores = matrix @ q
        order = np.argsort(-scores)[: max(0, k)]
        return [
            {
                "path": paths[i],
                "score": round(float(scores[i]), 4),
                "summary": self.entries[paths[i]].get("summary", ""),
                "bpm": self.entries[paths[i]].get("bpm"),
                "tags": self.entries[paths[i]].get("tags", {}),
            }
            for i in order
        ]

    # ---- library walking ------------------------------------------------------
    @staticmethod
    def audio_files(directory) -> list[Path]:
        directory = Path(directory)
        if not directory.exists():
            return []
        return sorted(
            p for p in directory.rglob("*")
            if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
        )
