"""CLI tests for the embedding commands — model, describe, find, analyze --embed."""

from __future__ import annotations

import json

import pytest
from fake_embedder import FakeEmbedder

from spectrumalyzer import cli


@pytest.fixture
def fake_backend(monkeypatch):
    """Patch the backend loader used by CLI commands."""
    emb = FakeEmbedder()
    monkeypatch.setattr(cli, "_load_backend", lambda: emb)
    return emb


def test_model_status_reports(fake_backend, capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_HOME", str(tmp_path))
    rc = cli.main(["model", "status"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "embeddinggemma" in out or "minilm" in out.lower()


def test_describe_command(click_120, capsys, fake_backend, tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_HOME", str(tmp_path))
    rc = cli.main(["describe", str(click_120)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "bpm" in out.lower()
    assert "mood" in out.lower() or "energy" in out.lower()


def test_find_ranks_library(click_120, two_sections, capsys, fake_backend, tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_HOME", str(tmp_path))
    lib = tmp_path / "lib"
    lib.mkdir()
    # two library files with pre-seeded store entries (fresh stats)
    a = lib / "calm_bed.mp3"; a.write_bytes(b"a" * 50)
    b = lib / "banger.mp3"; b.write_bytes(b"b" * 70)
    emb = fake_backend
    from spectrumalyzer.embedding.store import EmbeddingStore
    store = EmbeddingStore()
    store.upsert_entry(str(a), summary="calm soft quiet ambient warm slow bed track",
                       embedding=emb.embed_one("calm soft quiet ambient warm slow bed track").tolist(),
                       bpm=70.0)
    store.upsert_entry(str(b), summary="fast energetic loud intense punchy dance peak track",
                       embedding=emb.embed_one("fast energetic loud intense punchy dance peak track").tolist(),
                       bpm=150.0)
    store.save()
    for f in (a, b):
        st = f.stat()
        store.get  # noqa: B018 - entries seeded with matching stat below
        store.entries[str(f)]["size"] = st.st_size
        store.entries[str(f)]["mtime"] = st.st_mtime
    store.save()

    rc = cli.main(["find", "calm quiet ambient bed", str(lib), "--limit", "2"])
    assert rc == 0
    out = capsys.readouterr().out
    [l for l in out.splitlines() if l.strip() and not l.startswith(("Index", "Searching"))]
    assert "calm_bed.mp3" in out
    # calm result should be listed before the banger
    assert out.index("calm_bed.mp3") < out.index("banger.mp3")


def test_analyze_embed_adds_description_and_tags(click_120, tmp_path, capsys,
                                                 fake_backend, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_HOME", str(tmp_path))
    out = tmp_path / "e.json"
    rc = cli.main(["analyze", str(click_120), "-o", str(out), "--embed", "--quiet"])
    assert rc == 0
    data = json.loads(out.read_text())
    assert "description" in data and "summary" in data["description"]
    assert "tags" in data and "mood" in data["tags"]


def test_analyze_without_embed_stays_clean(click_120, tmp_path):
    out = tmp_path / "plain.json"
    rc = cli.main(["analyze", str(click_120), "-o", str(out), "--quiet"])
    assert rc == 0
    data = json.loads(out.read_text())
    assert "description" not in data and "tags" not in data
