"""Local embedding layer — semantic understanding on top of the DSP engine.

What it adds (honestly): the DSP engine measures; the embedding model gives
those measurements *language* — natural-language descriptions, mood/genre
tags, and semantic search over an audio library ("find something calm and
warm for the intro").

The model lives under ~/.config/spectrumalyzer/embedding/ and is pulled on
demand; nothing about the core DSP analysis depends on it.
"""
