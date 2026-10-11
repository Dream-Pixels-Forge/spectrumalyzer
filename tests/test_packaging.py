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


def test_mcp_sdk_is_a_base_dependency():
    deps = _load()["project"]["dependencies"]
    assert any(d.startswith("mcp") for d in deps), "MCP server ships in the single install"


def test_python_floor_covers_mcp_sdk():
    assert _load()["project"]["requires-python"] == ">=3.10", (
        "the MCP SDK requires Python 3.10+ — keep the floor in sync"
    )


def test_mcp_sdk_pinned_to_v1_api():
    """mcp 2.x renamed FastMCP to MCPServer — the pin guards the API we use."""
    deps = _load()["project"]["dependencies"]
    mcp_pin = next(d for d in deps if d.startswith("mcp"))
    assert "<2" in mcp_pin, f"mcp must be pinned <2 (FastMCP API): got {mcp_pin}"
