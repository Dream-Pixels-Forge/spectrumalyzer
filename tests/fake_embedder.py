"""Deterministic fake embedder for tests — no network, no model files.

Model-faithful behaviour: lexicon words get distinct vectors (real semantic
overlap is reflected); unknown words contribute ~nothing (like OOV tokens in
a real embedder). A text made only of unknown words embeds to (near-)zero,
so similarity collapses to 0 for every descriptor and feature profiles
decide — exactly how a neutral summary should behave.
"""

from __future__ import annotations

import hashlib

import numpy as np

DIM = 64

# small lexicon so overlaps behave like a real embedder
_LEXICON = {"calm", "soft", "quiet", "gentle", "peaceful", "relaxed", "serene", "ambient", "warm", "chill", "laid-back", "easy", "smooth", "mellow", "downtempo", "melancholic", "sad", "emotional", "wistful", "reflective", "slow", "uplifting", "bright", "happy", "hopeful", "positive", "radiant", "soaring", "dark", "brooding", "ominous", "heavy", "menacing", "gritty", "dreamy", "hazy", "floating", "ethereal", "lush", "atmospheric", "tense", "dramatic", "suspense", "driving", "euphoric", "ecstatic", "triumphant", "powerful", "peak", "festival", "nostalgic", "retro", "vintage", "familiar", "fast", "energetic", "loud", "intense", "punchy", "dance", "vigorous", "mid-tempo", "steady", "grooving", "balanced", "minimal", "sparse", "electronic", "synth", "acoustic", "organic", "guitar", "piano", "orchestral", "strings", "film", "hip", "hop", "rap", "rock", "pop", "catchy", "vocals", "background", "underscore", "unobtrusive", "intro", "opening", "drop", "climax", "explosion", "focus", "study", "hypnotic", "montage", "credits", "trailer", "workout", "underlay", "texture"}


_word_vector_cache: dict = {}


def _word_vector(word: str) -> np.ndarray:
    digest = hashlib.md5(word.encode()).digest()
    vec = np.zeros(DIM, dtype=np.float32)
    vec[digest[0] % DIM] += 1.0
    vec[(digest[1] + 7) % DIM] += 0.5
    vec[(digest[2] + 13) % DIM] += 0.25
    return vec


class FakeEmbedder:
    """Drop-in stand-in for EmbeddingBackend with an identical interface."""

    name = "fake-embedder"
    dim = DIM

    def embed(self, texts):
        vectors = np.zeros((len(texts), DIM), dtype=np.float32)
        for i, text in enumerate(texts):
            vectors[i] = self._embed_one(str(text))
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms

    def embed_one(self, text):
        return self.embed([text])[0]

    @classmethod
    def _embed_one(cls, text: str) -> np.ndarray:
        vec = np.zeros(DIM, dtype=np.float32)
        for word in text.lower().replace(",", " ").replace(".", " ").split():
            if word in _LEXICON:
                vec += _word_vector(word)
            # unknown words: contribute nothing (OOV ≈ negligible)
        return vec
