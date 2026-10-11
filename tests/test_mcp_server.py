"""MCP server tests — exercise the REAL protocol layer via FastMCP.

No protocol mocking: tools are invoked through ``server.call_tool`` exactly as
an MCP client would, so serialization and schema behavior are covered too.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

mcp_sdk = pytest.importorskip("mcp", reason="mcp SDK required for server tests")

from spectrumalyzer.mcp_server import TOOL_NAMES, create_server


@pytest.fixture
def server():
    return create_server()


def test_tool_names_registered(server):
    tools = __import__("asyncio").run(server.list_tools())
    names = {t.name for t in tools}
    assert set(TOOL_NAMES) <= names
    for t in tools:
        assert t.description  # every tool documents itself


def test_analyze_audio_returns_lean_payload(click_120, server):
    result, _meta = __import__("asyncio").run(
        server.call_tool("analyze_audio", {"path": str(click_120), "fps": 30})
    )
    data = json.loads(result[0].text)
    assert 117 <= data["bpm"] <= 123
    assert data["beats"] and data["beats"][0]["frame"] >= 0
    assert "bands" not in data  # lean by default — no huge matrices
    assert "duration" in data and "sections" in data


def test_analyze_audio_include_analysis(click_120, server):
    result, _meta = __import__("asyncio").run(
        server.call_tool(
            "analyze_audio", {"path": str(click_120), "include_analysis": True}
        )
    )
    data = json.loads(result[0].text)
    assert "bands" in data and "centroid" in data


def test_analyze_audio_missing_file(server):
    result, _meta = __import__("asyncio").run(
        server.call_tool("analyze_audio", {"path": "/nope/missing.mp3"})
    )
    data = json.loads(result[0].text)
    assert data["error"] == "file_not_found"


def test_describe_audio(fake_embedder, monkeypatch, tmp_path, click_120, server):
    monkeypatch.setenv("SPECTRUMALYZER_HOME", str(tmp_path))
    from spectrumalyzer.embedding import backend as backend_module

    monkeypatch.setattr(backend_module.EmbeddingBackend, "load", staticmethod(lambda: fake_embedder))
    result, _meta = __import__("asyncio").run(
        server.call_tool("describe_audio", {"path": str(click_120)})
    )
    data = json.loads(result[0].text)
    assert "summary" in data and "tags" in data
    assert "mood" in data["tags"]


def test_find_music_ranked(fake_embedder, monkeypatch, tmp_path, capsys, click_120, server):
    monkeypatch.setenv("SPECTRUMALYZER_HOME", str(tmp_path))
    from spectrumalyzer.embedding import backend as backend_module

    monkeypatch.setattr(backend_module.EmbeddingBackend, "load", staticmethod(lambda: fake_embedder))
    lib = tmp_path / "lib"
    lib.mkdir()
    track = lib / "one.wav"
    track.write_bytes(b"x" * 40)

    # seed the store so find does not need to re-analyze with the fake
    from spectrumalyzer.embedding.store import EmbeddingStore

    store = EmbeddingStore()
    stat = EmbeddingStore._stat_of(track)
    store.upsert_entry(
        str(track),
        summary="calm soft quiet ambient warm slow bed track",
        embedding=fake_embedder.embed_one("calm soft quiet ambient warm slow bed track").tolist(),
        bpm=70.0,
        stat=stat,
    )
    store.save()

    result, _meta = __import__("asyncio").run(
        server.call_tool("find_music", {"query": "calm quiet bed", "directory": str(lib)})
    )
    data = json.loads(result[0].text)
    assert data["hits"][0]["path"].endswith("one.wav")
    assert data["hits"][0]["score"] >= data["hits"][0]["score"]


def test_export_beats_writes_files(click_120, server, tmp_path):
    out = tmp_path / "beats"
    result, _meta = __import__("asyncio").run(
        server.call_tool(
            "export_beats",
            {"path": str(click_120), "format": "json,csv", "fps": 30, "output": str(out)},
        )
    )
    data = json.loads(result[0].text)
    assert data["written"], data
    import os

    for p in data["written"]:
        assert os.path.exists(p), p


def test_export_beats_invalid_format(click_120, server):
    result, _meta = __import__("asyncio").run(
        server.call_tool("export_beats", {"path": str(click_120), "format": "wav"})
    )
    data = json.loads(result[0].text)
    assert "error" in data and "format" in data["error"]


def test_render_report(click_120, server, tmp_path):
    out = tmp_path / "r.html"
    result, _meta = __import__("asyncio").run(
        server.call_tool("render_report", {"path": str(click_120), "output": str(out)})
    )
    data = json.loads(result[0].text)
    import os

    assert os.path.exists(data["report"])
    html = Path(data["report"]).read_text()
    assert "<canvas" in html


def test_model_status(server, tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_HOME", str(tmp_path))
    result, _meta = __import__("asyncio").run(server.call_tool("model_status", {}))
    data = json.loads(result[0].text)
    assert "preferred" in data and "installed" in data


def test_formats_resource(server):
    resources = __import__("asyncio").run(server.list_resources())
    uris = [str(r.uri) for r in resources]
    assert any("formats" in u for u in uris)
