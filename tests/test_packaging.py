"""Packaging contract tests — guard the dependency policy in pyproject.toml.

The embedding capability ships IN the base install (user decision, v0.4.0):
one `pip install spectrumalyzer` must be enough. These tests fail if anyone
accidentally re-splits the install or drops the dependency.
"""

from __future__ import annotations

from pathlib import Path

import tomllib

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _load() -> dict:
    with open(PYPROJECT, "rb") as f:
        return tomllib.load(f)


def test_sentence_transformers_is_a_base_dependency():
    deps = _load()["project"]["dependencies"]
    assert any(d.startswith("sentence-transformers") for d in deps), (
        "sentence-transformers must be a base dependency — one install policy"
    )
    assert any(d.startswith("numpy") for d in deps)


def test_no_embedding_extra_exists():
    extras = _load()["project"].get("optional-dependencies", {})
    assert "embedding" not in extras, (
        "the [embedding] extra was merged into the base install (v0.4.0) — "
        "do not reintroduce a second installation path"
    )


def test_dev_extra_only_has_tooling():
    extras = _load()["project"].get("optional-dependencies", {}).get("dev", [])
    assert any(r.startswith("pytest") for r in extras)
    assert any(r.startswith("ruff") for r in extras)
    assert all("sentence" not in r for r in extras)
