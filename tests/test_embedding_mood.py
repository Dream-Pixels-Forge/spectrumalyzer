"""Tests for mood/energy/genre tagging via the descriptor bank."""

from __future__ import annotations

from spectrumalyzer.embedding.mood import MOOD_BANK, tag_track


def test_mood_bank_structure():
    assert len(MOOD_BANK) >= 30
    for axis, tag, phrase, profile in MOOD_BANK:
        assert axis in {"mood", "energy", "flavor", "use"}
        assert tag and phrase
        if profile is not None:
            for k, v in profile.items():
                assert k in {"tempo", "energy", "brightness", "bass", "density", "contrast"}
                assert 0.0 <= v <= 1.0


def test_calm_track_tags_calm_first(fake_embedder):
    # a summary whose language is "calm" must rank the calm tag top-1 in its axis
    summary = "slow calm ambient track, soft and quiet with a dark warm tone, gentle intro"
    tags = tag_track(fake_embedder, summary)
    mood_tags = [t for t in tags["mood"]]
    assert mood_tags[0][0] == "calm", f"got {mood_tags[:3]}"


def test_energetic_track_tags_energetic_first(fake_embedder):
    summary = "fast energetic powerful driving track, loud punchy bright peak, intense dance"
    tags = tag_track(fake_embedder, summary)
    assert tags["energy"][0][0] == "high energy"


def test_tags_scores_bounded(fake_embedder):
    tags = tag_track(fake_embedder, "mid-tempo warm track with steady beat")
    for scored in tags.values():
        for tag, score in scored:
            assert -1.0 <= score <= 1.0


def test_topk_per_axis(fake_embedder):
    tags = tag_track(fake_embedder, "some track", top_k=3)
    for scored in tags.values():
        assert len(scored) <= 3


def test_all_axes_present(fake_embedder):
    tags = tag_track(fake_embedder, "anything")
    assert set(tags.keys()) == {"mood", "energy", "flavor", "use"}


BANGER_FEATURES = {"tempo": 0.8, "energy": 0.95, "brightness": 0.6,
                   "bass": 0.8, "density": 0.7, "contrast": 0.4}
PAD_FEATURES = {"tempo": 0.0, "energy": 0.15, "brightness": 0.3,
                "bass": 0.25, "density": 0.08, "contrast": 0.1}


def test_aggressive_features_beat_neutral_text(fake_embedder):
    """Feature profiles anchor tags to measurements even with neutral text."""
    tags = tag_track(fake_embedder, "instrumental track", features=BANGER_FEATURES)
    assert tags["energy"][0][0] == "high energy"
    assert tags["mood"][0][0] in {"aggressive", "euphoric", "epic"}


def test_pad_features_tag_calm(fake_embedder):
    tags = tag_track(fake_embedder, "instrumental track", features=PAD_FEATURES)
    assert tags["energy"][0][0] == "low energy"
    assert tags["mood"][0][0] in {"calm", "chill", "dreamy"}
    assert "bed music" in [t for t, _ in tags["use"][:2]] or \
        "underlay" in [t for t, _ in tags["use"][:2]]


def test_text_still_matters_without_features(fake_embedder):
    """No features supplied → pure text similarity (back-compat path)."""
    summary = "calm soft quiet ambient track"
    tags = tag_track(fake_embedder, summary, features=None)
    assert tags["mood"][0][0] == "calm"
