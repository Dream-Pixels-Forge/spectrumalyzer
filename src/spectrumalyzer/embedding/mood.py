"""Mood / energy / flavor / use-case tagging — hybrid, measurement-anchored.

Two signals per descriptor:
  1. text similarity: the track's measured summary vs the descriptor phrase
     (both embedded — one space, one model)
  2. feature-profile match: each descriptor carries an optional numeric
     profile over measured features (tempo/energy/brightness/bass/density/
     contrast); distance in feature space is a deterministic, honest signal
     that keeps tags anchored to what the DSP actually measured.

Small embedding models are noisy on thin text — the feature profile is what
makes tags trustworthy. Scores are a 50/50 blend (text-only when no features
are supplied, e.g. in tests with the FakeEmbedder).
"""

from __future__ import annotations

# (axis, tag, descriptor phrase, feature profile or None)
# profile keys: tempo, energy, brightness, bass, density, contrast (0..1)
MOOD_BANK: list[tuple[str, str, str, dict[str, float] | None]] = [
    # ---- mood ------------------------------------------------------------
    ("mood", "calm", "calm soft quiet gentle peaceful relaxed serene ambient warm",
     {"energy": 0.2, "density": 0.15, "contrast": 0.2, "tempo": 0.2}),
    ("mood", "chill", "chill laid-back relaxed easy smooth mellow downtempo",
     {"energy": 0.3, "tempo": 0.3, "density": 0.3}),
    ("mood", "melancholic", "melancholic sad emotional wistful sorrowful reflective slow",
     {"energy": 0.35, "brightness": 0.3, "tempo": 0.3}),
    ("mood", "uplifting", "uplifting bright happy hopeful positive radiant soaring",
     {"brightness": 0.75, "energy": 0.6}),
    ("mood", "dark", "dark brooding ominous tense heavy menacing gritty",
     {"brightness": 0.15, "bass": 0.65}),
    ("mood", "dreamy", "dreamy hazy floating ethereal lush atmospheric soft",
     {"density": 0.15, "energy": 0.3, "contrast": 0.2}),
    ("mood", "tense", "tense nervous dramatic suspense urgent restless driving",
     {"contrast": 0.6, "energy": 0.6}),
    ("mood", "euphoric", "euphoric blissful ecstatic triumphant powerful peak festival",
     {"energy": 0.85, "contrast": 0.7, "tempo": 0.7}),
    ("mood", "nostalgic", "nostalgic retro vintage warm familiar mellow",
     {"brightness": 0.4, "energy": 0.4}),
    ("mood", "hopeful", "hopeful optimistic gentle rising warm open",
     {"brightness": 0.65, "energy": 0.45}),
    ("mood", "aggressive", "aggressive angry hard hitting fierce brutal distortion intense",
     {"energy": 0.9, "density": 0.7, "bass": 0.7, "tempo": 0.75}),
    ("mood", "playful", "playful fun quirky bouncy light cheerful whimsical",
     {"tempo": 0.55, "energy": 0.55, "brightness": 0.7}),
    ("mood", "romantic", "romantic loving tender intimate warm close emotional",
     {"energy": 0.35, "brightness": 0.45, "density": 0.3}),
    ("mood", "epic", "epic heroic grand sweeping massive majestic adventure",
     {"energy": 0.8, "contrast": 0.75, "bass": 0.6}),
    # ---- energy ------------------------------------------------------------
    ("energy", "high energy", "fast energetic loud intense powerful driving punchy dance vigorous",
     {"energy": 0.85, "tempo": 0.75, "density": 0.6}),
    ("energy", "moderate energy", "mid-tempo moderate steady grooving balanced consistent",
     {"energy": 0.5, "tempo": 0.5, "density": 0.45}),
    ("energy", "low energy", "slow quiet soft calm minimal sparse gentle mellow",
     {"energy": 0.2, "tempo": 0.2, "density": 0.2}),
    # ---- flavor (genre-adjacent) -------------------------------------------
    ("flavor", "electronic", "electronic synth digital programmed drums machine dance beats",
     {"density": 0.6, "tempo": 0.65}),
    ("flavor", "acoustic", "acoustic organic guitar piano live natural warm strings",
     {"density": 0.35, "brightness": 0.5}),
    ("flavor", "orchestral", "orchestral cinematic strings brass epic score film dramatic",
     {"contrast": 0.7, "energy": 0.6}),
    ("flavor", "hip hop", "hip hop rap beats boom bap urban groove swing",
     {"bass": 0.7, "tempo": 0.5}),
    ("flavor", "ambient", "ambient atmospheric drone texture space background pad evolving",
     {"density": 0.12, "energy": 0.3, "contrast": 0.2}),
    ("flavor", "rock", "rock guitars drums band riff raw loud",
     {"energy": 0.75, "brightness": 0.65}),
    ("flavor", "pop", "pop catchy melodic vocals hooks radio bright",
     {"brightness": 0.7, "tempo": 0.55}),
    # ---- use-case ------------------------------------------------------------
    ("use", "bed music", "bed music background underscore quiet supportive unobtrusive loopable",
     {"energy": 0.3, "contrast": 0.15, "density": 0.3}),
    ("use", "intro", "intro opening establishing beginning sets the scene rising",
     {"contrast": 0.4, "energy": 0.4}),
    ("use", "outro", "outro closing ending fade resolution",
     {"energy": 0.3, "density": 0.3}),
    ("use", "drop", "drop climax peak explosion moment impact",
     {"energy": 0.95, "contrast": 0.9}),
    ("use", "focus", "focus concentration study minimal steady hypnotic repetitive",
     {"density": 0.3, "energy": 0.35, "contrast": 0.1}),
    ("use", "montage", "montage sequence highlights progression compilation",
     {"contrast": 0.55, "tempo": 0.6}),
    ("use", "credits", "credits end titles resolution reflective closing",
     {"energy": 0.35, "tempo": 0.35}),
    ("use", "trailer", "trailer cinematic impactful hits braams tension build",
     {"contrast": 0.8, "energy": 0.85, "bass": 0.7}),
    ("use", "workout", "workout gym intense driving relentless motivational energy",
     {"energy": 0.9, "tempo": 0.8, "density": 0.65}),
    ("use", "underlay", "underlay subtle texture under dialogue quiet bed padding",
     {"energy": 0.2, "contrast": 0.1, "density": 0.25}),
]

_AXES = ("mood", "energy", "flavor", "use")
_FEATURE_KEYS = ("tempo", "energy", "brightness", "bass", "density", "contrast")
_TEXT_WEIGHT = 0.5
_phrase_cache: dict[str, dict[str, object]] = {}


def _bank_embeddings(backend) -> dict[str, object]:
    key = getattr(backend, "name", "unknown")
    if key not in _phrase_cache:
        phrases = [p for _, _, p, _ in MOOD_BANK]
        vecs = backend.embed(phrases)
        _phrase_cache[key] = {"phrases": phrases, "vecs": vecs}
    return _phrase_cache[key]


def _profile_match(profile: dict[str, float] | None,
                   features: dict[str, float] | None) -> float | None:
    """1.0 = perfect feature match; None when either side lacks a profile."""
    if not profile or not features:
        return None
    dists = [abs(features[k] - profile[k]) for k in profile if k in features]
    if not dists:
        return None
    return 1.0 - (sum(dists) / len(dists))


def tag_track(backend, summary_text: str, features: dict[str, float] | None = None,
              top_k: int = 3) -> dict[str, list[tuple[str, float]]]:
    """Nearest descriptors per axis: blended text similarity + feature match."""
    import numpy as np

    bank = _bank_embeddings(backend)
    bank["phrases"]  # type: ignore[assignment]
    vecs: np.ndarray = bank["vecs"]  # type: ignore[assignment]
    query = backend.embed_one(summary_text)
    text_scores = vecs @ query  # both L2-normalized → cosine
    # Baseline-shift: unrelated texts have a model-dependent similarity floor;
    # only the DEVIATION from the bank mean carries semantic signal.
    text_scores = (text_scores - text_scores.mean()) / 0.25
    text_component = np.clip(text_scores, -1.0, 1.0)

    tags: dict[str, list[tuple[str, float]]] = {axis: [] for axis in _AXES}
    for i, (axis, tag, _phrase, profile) in enumerate(MOOD_BANK):
        text_part = float(text_component[i])
        feat_score = _profile_match(profile, features)
        if feat_score is None:
            score = text_part
        else:
            score = _TEXT_WEIGHT * text_part + (1 - _TEXT_WEIGHT) * feat_score
        tags[axis].append((tag, score))
    for axis in tags:
        tags[axis] = sorted(tags[axis], key=lambda t: -t[1])[:top_k]
    return tags
