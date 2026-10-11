"""Embedding model backend — local model lifecycle under the config dir.

Model home: ~/.config/spectrumalyzer/embedding/  (XDG_CONFIG_HOME respected,
SPECTRUMALYZER_HOME overrides the whole root — used by tests).

Preferred model: google/embeddinggemma-300m (the current small Gemma embedding
model — 300M params, Matryoshka 768→128 dims). It is license-gated on
Hugging Face (`gated: manual`): to use it, accept the Gemma license on the
model page and authenticate (`huggingface-cli login` or HF_TOKEN env var).
When it is unavailable, pull() transparently falls back to the non-gated
sentence-transformers/all-MiniLM-L6-v2 so the feature works for everyone.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

PREFERRED_MODEL = "google/embeddinggemma-300m"
FALLBACK_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class EmbeddingNotAvailable(RuntimeError):
    """Raised when no embedding model is available locally and pull is needed."""


def spectrumalyzer_home() -> Path:
    """The spectrumalyzer config directory (contains embedding/).

    SPECTRUMALYZER_HOME overrides it entirely (used by tests); otherwise
    XDG_CONFIG_HOME/spectrumalyzer, falling back to ~/.config/spectrumalyzer.
    """
    env = os.environ.get("SPECTRUMALYZER_HOME")
    if env:
        return Path(env)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "spectrumalyzer"


def default_model_dir() -> Path:
    """The directory the embedding model lives in."""
    return spectrumalyzer_home() / "embedding"


class EmbeddingBackend:
    """Loads a local sentence-transformers model and embeds text."""

    def __init__(self, model, name: str, dim: int):
        self._model = model
        self.name = name
        self.dim = dim

    # ---- lifecycle -------------------------------------------------------
    @classmethod
    def model_dir(cls) -> Path:
        return default_model_dir()

    @classmethod
    def is_downloaded(cls) -> bool:
        d = cls.model_dir()
        return (d / "model.json").exists() and (d / "config.json").exists()

    @classmethod
    def downloaded_name(cls) -> str | None:
        meta = cls.model_dir() / "model.json"
        if meta.exists():
            try:
                return json.loads(meta.read_text()).get("model")
            except (json.JSONDecodeError, OSError):
                return None
        return None

    @classmethod
    def load(cls) -> EmbeddingBackend:
        """Load the locally downloaded model. Raises EmbeddingNotAvailable."""
        from sentence_transformers import SentenceTransformer

        d = cls.model_dir()
        if not (d / "config.json").exists():
            raise EmbeddingNotAvailable(
                f"No embedding model at {d} — run: spectrumalyzer model pull"
            )
        model = SentenceTransformer(str(d))
        name = cls.downloaded_name() or "local"
        dim_fn = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
        return cls(model, name, int(dim_fn()))

    @classmethod
    def pull(cls) -> str:
        """Download the preferred model (falls back when gated/unreachable).

        Returns the repo id that was installed.
        """
        from huggingface_hub import snapshot_download
        from sentence_transformers import SentenceTransformer

        d = cls.model_dir()
        d.mkdir(parents=True, exist_ok=True)
        token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        chosen = None
        for repo in (PREFERRED_MODEL, FALLBACK_MODEL):
            try:
                snapshot_download(
                    repo_id=repo,
                    local_dir=str(d),
                    token=token,
                    ignore_patterns=["*.pt", "*.h5", "*.msgpack", "*.tflite"],
                )
                chosen = repo
                break
            except Exception as exc:  # noqa: BLE001 — gated/offline/no-token all fall through
                print(f"  {repo} unavailable ({exc.__class__.__name__}) — trying fallback")
        if chosen is None:
            raise EmbeddingNotAvailable("Could not download any embedding model (offline?)")
        (d / "model.json").write_text(json.dumps({
            "model": chosen,
            "pulled_at": datetime.now(timezone.utc).isoformat(),
        }, indent=2))
        # warm-load to verify the artifact
        SentenceTransformer(str(d))
        return chosen

    # ---- inference -------------------------------------------------------
    def embed(self, texts: list[str]) -> np.ndarray:
        vecs = self._model.encode(
            [str(t) for t in texts],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return np.asarray(vecs, dtype=np.float32)

    def embed_one(self, text: str) -> np.ndarray:
        return self.embed([text])[0]
