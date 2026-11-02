---
name: spectrumalyzer
description: Audio-reactive analysis toolkit for motion graphics — spectral-flux beat detection, BPM, 6 frequency bands, song sections, mood/genre tags, semantic library search, best-window trimming (short versions for video), and frame-native exports for Remotion, HyperFrames, After Effects, FCPXML and CSV. Includes an MCP server so AI agents can use it as native tools. Use when syncing animation to music, analyzing audio for video projects, shortening long tracks for video, finding music by mood, or exporting beat data for creative tools.
version: 0.6.0
author: Dream-Pixels-Forge
license: MIT
metadata:
  homepage: https://github.com/Dream-Pixels-Forge/spectrumalyzer
  pypi: https://pypi.org/project/spectrumalyzer/
---

# spectrumalyzer

Audio-reactive analysis toolkit for motion graphics. Give it music — get
beats, BPM, onsets, frequency bands, song sections, loudness and mood tags,
exported as frame-native data for the tools creatives animate in.

## Install

```bash
# system dependency (any one package manager)
brew install ffmpeg        # macOS
sudo apt install ffmpeg    # Debian/Ubuntu/Mint

# the tool — one install, everything included (DSP + semantic hearing + MCP)
pip install spectrumalyzer
```

The embedding model weights (~90 MB) auto-download on first semantic use, or
run `spectrumalyzer model pull` upfront. Model lives at
`~/.config/spectrumalyzer/embedding/`.

## CLI

```bash
spectrumalyzer analyze track.mp3 --fps 30 --format remotion,csv,ae   # beat data for a 30 fps project
spectrumalyzer report track.mp3 -o report.html                       # visual HTML report
spectrumalyzer trim song.mp3 --length 90 -o bed.mp3                   # best 90s window for video (cuts to beat grid)
spectrumalyzer describe track.mp3                                    # NL description + mood/energy/genre tags
spectrumalyzer find "calm warm bed for a documentary intro" ./lib    # semantic library search
spectrumalyzer formats                                                # list export formats
```

## Trimming a long track for video

`trim` picks the most worthwhile window of a target length (loudness + onset
density + section energy, cuts snapped to the beat grid) and cuts the source
(audio **or video**) with ffmpeg:

```bash
spectrumalyzer trim song.mp3 --length 90 --preview   # just show the chosen window
spectrumalyzer trim song.mp3 --length 90 -o bed.mp3  # cut it
```

When a full song is too long for a video: trim to the target length, then
`analyze` the short version with `--fps` for your composition. If the track
is already short enough, `trim` says so and writes nothing.

## MCP server (for AI agents)

```bash
spectrumalyzer mcp    # stdio server, blocking
```

Register with any MCP client:

```json
{"command": "spectrumalyzer", "args": ["mcp"]}
```

Tools: `analyze_audio`, `describe_audio`, `find_music`, `export_beats`,
`render_report`, `model_status`, `trim_audio` + `spectrumalyzer://formats` resource.
Structured `{error: ...}` responses — agents can react gracefully.

## Python API

```python
from spectrumalyzer import analyze

result = analyze("track.mp3", fps=30)
result.bpm                  # 128.32
result.beats_as_frames()    # [15, 53, 91, ...] at 30 fps
result.band_rows_at_fps()   # [sub, bass, lowMid, mid, highMid, treble] per video frame
result.sections             # [Section(start, end, energy, label), ...]
result.to_dict()            # JSON-ready
```

## The signals — creative mapping

| Signal | Use for |
|---|---|
| beats (grid) | camera cuts, scale pops, scroll steps — uniform, kick-locked |
| onsets (hits) | glitch flashes, particle bursts, impact frames |
| bands.sub/bass | camera shake, glow pulses |
| bands.treble | sparkles, glints, particle twinkles |
| centroid | blur amount, color temperature |
| loudness | opacity rides, zoom pressure |
| sections | narrative pacing, scene grouping |

## Export formats

`json` (rich) · `remotion` (frame-native + useBeats.ts React hook) ·
`hyperframes` (timeline events + data-hf snippet) · `ae` (After Effects
comp-marker script) · `csv` (Premiere/Resolve markers) · `fcpxml` (Final
Cut/Resolve). Frame-based formats need `--fps`.

## Honesty guarantees

- Pulseless material (ambient/pads) reports `bpm: 0` + "no clear pulse" —
  never an invented tempo
- `bpmConfidence` folds in onset salience (noise ≈ 0.01, click tracks ≈ 0.96)
- Tags blend embedding similarity with measured feature profiles (tempo,
  dBFS energy, brightness, bass, transient density, section contrast)
- Beat grid is phase-locked to the kick drum, not to generic loudness spikes

## Links

- Repo: https://github.com/Dream-Pixels-Forge/spectrumalyzer
- PyPI: https://pypi.org/project/spectrumalyzer/
- Roadmap: docs/ROADMAP.md in the repo
