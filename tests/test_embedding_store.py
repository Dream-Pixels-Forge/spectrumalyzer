"""Tests for the embedding store (index persistence + semantic search)."""

from __future__ import annotations

import json

from fake_embedder import FakeEmbedder

from spectrumalyzer.embedding.store import EmbeddingStore, default_model_dir


def test_store_persists_to_config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_HOME", str(tmp_path))
    store = EmbeddingStore()
    assert store.root == tmp_path
    assert (tmp_path / "embedding").exists()


def test_put_get_and_freshness(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_HOME", str(tmp_path))
    store = EmbeddingStore()
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x" * 100)

    store.put(audio, summary="calm slow track", tags={"mood": [["calm", 0.9]]},
              embedding=[0.1] * 8, stat=(100, 12345.0))
    store.save()

    reloaded = EmbeddingStore()
    entry = reloaded.get(audio, stat=(100, 12345.0))
    assert entry and entry["summary"] == "calm slow track"
    # file changed (different size) -> stale
    assert reloaded.get(audio, stat=(200, 12345.0)) is None
    assert reloaded.get(audio, stat=(100, 99999.0)) is None


def test_search_ranks_by_cosine(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_HOME", str(tmp_path))
    emb = FakeEmbedder()
    store = EmbeddingStore()
    calm_vec = emb.embed_one("calm soft quiet ambient warm track")
    loud_vec = emb.embed_one("loud aggressive energetic intense punchy dance track")

    store.upsert_entry("calm_song.mp3", summary="calm soft quiet ambient warm track",
                       embedding=calm_vec.tolist())
    store.upsert_entry("banger.mp3", summary="loud aggressive energetic intense punchy dance track",
                       embedding=loud_vec.tolist())
    store.save()

    hits = store.search("find something calm and quiet", embedder=emb, k=2)
    assert hits[0]["path"] == "calm_song.mp3"
    assert hits[0]["score"] > hits[1]["score"]


def test_search_k_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_HOME", str(tmp_path))
    emb = FakeEmbedder()
    store = EmbeddingStore()
    for i in range(5):
        store.upsert_entry(f"t{i}.mp3", summary=f"track {i}",
                           embedding=emb.embed_one(f"track {i}").tolist())
    assert len(store.search("track", embedder=emb, k=3)) == 3


def test_default_model_dir_under_config():
    d = default_model_dir()
    assert ".config" in str(d) and "spectrumalyzer" in str(d) and "embedding" in str(d)


def test_index_json_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECTRUMALYZER_HOME", str(tmp_path))
    emb = FakeEmbedder()
    store = EmbeddingStore()
    store.upsert_entry("x.mp3", summary="hello", embedding=emb.embed_one("hello").tolist())
    store.save()
    data = json.loads((tmp_path / "embedding" / "index.json").read_text())
    assert data["entries"]["x.mp3"]["summary"] == "hello"
    assert len(data["entries"]["x.mp3"]["embedding"]) == FakeEmbedder.dim
