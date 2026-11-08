"""Deterministic analysis → language. Turns measurements into sentences.

This is the honest bridge between DSP and semantics: every adjective here is
derived from a measured statistic (tempo, centroid, loudness, sections), so
the embedding model tags *real* audio properties, never invented ones.
"""

from __future__ import annotations


def _tempo_word(bpm: float, confidence: float = 1.0) -> str:
    if bpm <= 0 or confidence < 0.3:
        return "free-tempo (no clear pulse)"
    if bpm < 85:
        return "slow"
    if bpm < 115:
        return "mid-tempo"
    if bpm <= 135:
        return "steady"
    return "fast"


def _brightness_word(centroid_mean: float) -> str:
    if centroid_mean <= 0:
        return ""
    if centroid_mean < 800:
        return "dark"
    if centroid_mean < 2500:
        return "warm"
    if centroid_mean <= 5000:
        return "balanced"
    return "bright"


def _energy_word(loudness_mean: float) -> str:
    if loudness_mean < 0.25:
        return "quiet"
    if loudness_mean < 0.6:
        return "moderate"
    return "powerful"


def describe(result) -> dict[str, str]:
    """Build {summary, description, text} from an AnalysisResult.

    ``text`` is the combined string that gets embedded for search/tagging.
    """
    bpm = float(result.bpm)
    tempo = _tempo_word(bpm, float(result.bpm_confidence))

    centroid_mean = (
        sum(result.centroid) / len(result.centroid) if result.centroid else 0.0
    )
    brightness = _brightness_word(centroid_mean)

    loudness_mean = (
        sum(result.loudness) / len(result.loudness) if result.loudness else 0.5
    )
    energy = _energy_word(loudness_mean)

    peak_sections = [s for s in result.sections if s.label == "peak"]
    section_labels = ", ".join(s.label for s in result.sections) or "single-section"

    # measured feature words — the semantic surface the embedder can use
    feature_bits = []
    if result.bands is not None and result.bands.matrix:
        import numpy as np

        mat = np.asarray(result.bands.matrix, dtype=float)
        band_means = mat.mean(axis=0)
        dominant = int(band_means.argmax())
        from spectrumalyzer.model import BAND_NAMES

        feature_bits.append(f"Dominant energy in the {BAND_NAMES[dominant]} frequency range.")
    if result.duration > 0:
        density = len(result.onsets) / result.duration
        if density < 0.8:
            feature_bits.append(f"Sparse transients (~{density:.1f} per second).")
        elif density <= 4.0:
            feature_bits.append(f"Steady transients (~{density:.1f} per second).")
        else:
            feature_bits.append(f"Dense transients (~{density:.1f} per second).")
    if len(result.sections) >= 2:
        energies = [s.energy for s in result.sections]
        if max(energies) - min(energies) >= 0.5:
            feature_bits.append("Clear contrast between sections.")
    feature_sentence = " ".join(feature_bits)

    summary_parts = [f"{tempo} {energy} track"]
    if bpm > 0:
        summary_parts.append(f"at {bpm:.0f} bpm")
    if brightness:
        summary_parts.append(f"{brightness} tone")
    summary_parts.append(f"{result.beat_count} beats across {len(result.sections) or 1} section(s)")
    summary = ", ".join(summary_parts) + "."

    description_bits = [f"Structure: {len(result.sections) or 1} section(s) — {section_labels}."]
    if result.key is not None and result.key.key != "unknown":
        palette = result.key.palette or {}
        desc_key = (
            f"Key: {result.key.key} "
            f"(Camelot {result.key.camelot}, confidence {result.key.confidence:.2f}). "
            f"Creative color grade: {palette.get('label', 'unknown')}."
        )
        description_bits.append(desc_key)
    if peak_sections:
        p = peak_sections[0]
        description_bits.append(
            f"The peak starts at {p.start:.1f}s and carries {p.energy:.0%} relative energy."
        )
    if brightness:
        description_bits.append(f"Overall tonal character reads as {brightness}.")
    if feature_sentence:
        description_bits.append(feature_sentence)
    description = " ".join(description_bits)

    return {
        "summary": summary,
        "description": description,
        "text": f"{summary} {description}",
    }


def feature_vector(result) -> dict[str, float]:
    """Measured track features normalized to 0..1 — the numeric twin of the
    summary text. Used by the tagger so tags track measurements, not just
    embedding noise on thin text.

    Keys: tempo, energy, brightness, bass, density, contrast
    """
    feats: dict[str, float] = {
        "tempo": min(1.0, max(0.0, float(result.bpm) / 200.0)) if result.bpm > 0 else 0.0,
        "energy": 0.5,
        "brightness": 0.5,
        "bass": 0.5,
        "density": 0.5,
        "contrast": 0.5,
    }
    # absolute loudness is the honest energy signal: -48 dBFS -> 0, -6 dBFS -> 1
    if result.loudness_db is not None:
        feats["energy"] = min(1.0, max(0.0, (result.loudness_db + 48.0) / 42.0))
    elif result.loudness:
        feats["energy"] = min(1.0, sum(result.loudness) / len(result.loudness))
    if result.centroid:
        feats["brightness"] = min(1.0, (sum(result.centroid) / len(result.centroid)) / 10000.0)
    if result.bands is not None and result.bands.matrix:
        import numpy as np

        mat = np.asarray(result.bands.matrix, dtype=float)
        feats["bass"] = float(min(1.0, mat[:, 0].mean() + mat[:, 1].mean()))
    if result.duration > 0:
        feats["density"] = min(1.0, (len(result.onsets) / result.duration) / 6.0)
    if len(result.sections) >= 2:
        energies = [s.energy for s in result.sections]
        feats["contrast"] = min(1.0, max(energies) - min(energies))
    return feats


def tagged_text(d: dict, tags: dict, top: int = 2) -> str:
    """Embedding text enriched with the track's distilled tags.

    Tags are feature-profile-anchored (measured), so including them gives the
    search index a stable semantic surface beyond thin summaries.
    """
    parts = [d["text"]]
    for axis in ("mood", "energy", "flavor", "use"):
        names = [t for t, _ in tags.get(axis, [])[:top]]
        if names:
            parts.append(f"{axis}: " + ", ".join(names))
    return " ".join(parts)


def embedding_text(d: dict, tags: dict | None = None) -> str:
    """Compact, boilerplate-free text for the vector index.

    The human-facing description carries structure narrative that is nearly
    identical across tracks; embedding it compresses all cosines into a
    narrow band. Only discriminative semantic content belongs in the vector:
    tempo class, energy, tone, transient density, and the measured tags.
    """
    summary = d["summary"].rstrip(".")
    parts = [summary]
    if tags:
        for axis in ("mood", "energy", "flavor", "use"):
            names = [t for t, _ in tags.get(axis, [])[:2]]
            if names:
                parts.append(", ".join(names))
    return ". ".join(parts)
