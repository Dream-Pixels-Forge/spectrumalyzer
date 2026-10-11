"""Embedding model lifecycle shared by the CLI and the MCP server.

Single policy: the library ships with the package (single install); the
weights download on demand the first time a semantic feature is used.
"""

from __future__ import annotations

import sys

from spectrumalyzer.embedding.backend import EmbeddingBackend, EmbeddingNotAvailable


def ensure_backend(quiet: bool = False):
    """Load the embedding backend, auto-pulling weights on first use.

    Raises the underlying error when offline / download impossible.
    """
    try:
        return EmbeddingBackend.load()
    except EmbeddingNotAvailable:
        if not quiet:
            print(
                "First run: downloading the embedding model (one-time, ~90 MB) …",
                file=sys.stderr,
            )
        chosen = EmbeddingBackend.pull()
        if not quiet:
            print(f"Model ready: {chosen}", file=sys.stderr)
        return EmbeddingBackend.load()
