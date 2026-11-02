# spectrumalyzer

![spectrumalyzer banner](assets/Spectrumalyzer%20Audio%20Intelligence%20Banner.png)

[![PyPI version](https://img.shields.io/pypi/v/spectrumalyzer)](https://pypi.org/project/spectrumalyzer/)
[![PyPI downloads](https://img.shields.io/pypi/dm/spectrumalyzer)](https://pypi.org/project/spectrumalyzer/)
[![Python](https://img.shields.io/pypi/pyversions/spectrumalyzer)](https://pypi.org/project/spectrumalyzer/)
[![License: MIT](https://img.shields.io/github/license/Dream-Pixels-Forge/spectrumalyzer)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/Dream-Pixels-Forge/spectrumalyzer/ci.yml?label=ci)](.github/workflows/ci.yml)

**Turn any song into animation-ready data** — beats, BPM, onsets, frequency bands, song sections and loudness, in the exact format your creative tool speaks: Remotion, HyperFrames, After Effects, Final Cut / DaVinci Resolve, spreadsheets, or plain JSON. No subscriptions, no uploads, no cloud: Python + ffmpeg, fully local.

## Install

```bash
brew install ffmpeg            # macOS (or: apt / winget install ffmpeg)
pip install spectrumalyzer
```

## Quick start

```bash
# 1. Analyze a track for a 30 fps project, in three formats at once
spectrumalyzer analyze song.mp3 --fps 30 --format remotion,csv,ae

# 2. Open a self-contained visual report
spectrumalyzer report song.mp3 -o song.html

# 3. Semantic hearing: describe & find by meaning (local embedding model)
spectrumalyzer find "calm warm bed for a documentary intro" ./my-library
```

## Docs

- **[Docs site](https://dream-pixels-forge.github.io/spectrumalyzer/)** — home, CLI, Python API, export formats, signal → animation recipes, semantic hearing, MCP & agents
- **[Changelog](https://dream-pixels-forge.github.io/spectrumalyzer/changelog.html)** · **[Roadmap](https://dream-pixels-forge.github.io/spectrumalyzer/roadmap.html)**
- [CHANGELOG.md](CHANGELOG.md) · [ROADMAP](docs/ROADMAP.md) · [Agent skill](skills/spectrumalyzer/SKILL.md)

## Development

```bash
pip install -e ".[dev]"    # pytest + ruff
pytest                     # synthetic fixtures, fully offline
ruff check src tests
```

MIT License — built by [Dream-Pixels-Forge](https://github.com/Dream-Pixels-Forge).
