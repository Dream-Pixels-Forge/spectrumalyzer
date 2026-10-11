# spectrumalyzer

**Audio-reactive analysis toolkit for motion graphics.** Point it at music, get
beats, BPM, frequency bands, song sections and loudness — exported as
frame-native data for the tools you actually animate in.

```bash
pip install spectrumalyzer          # + system ffmpeg
spectrumalyzer analyze track.mp3 --fps 30 --format remotion,csv,ae
spectrumalyzer report   track.mp3 -o track.html
```

## Why it exists

Editors and animators think in **frames**, not seconds. spectrumalyzer
analyzes once and speaks every dialect: Remotion components, HyperFrames
timelines, After Effects markers, FCPXML (Final Cut / Resolve), CSV, or plain
JSON — all with beat numbers **pre-converted to your project's frame rate**.

## What you get

| Signal | What it is | Creative use |
|---|---|---|
| **BPM + confidence** | autocorrelation tempo, octave-disambiguated, low-band (kick) anchored | pace the edit, loop animations |
| **Beat grid** | uniform, phase-locked to the kick drum | camera cuts, scale pops, scroll steps |
| **Onsets / hits** | raw transients (spectral flux) | hit accents, glitch flashes, particle bursts |
| **6 frequency bands** | sub · bass · lowMid · mid · highMid · treble, per video frame | bass→glow, treble→sparkle, sub→camera shake |
| **Spectral centroid** | brightness over time | color temperature, blur amount |
| **Loudness envelope** | normalized RMS | opacity rides, zoom pressure |
| **Sections** | quiet/mid/high/peak regions | narrative pacing, scene grouping |

## Install

```bash
pip install spectrumalyzer        # Python 3.9+, numpy included as dependency
# system dependency: ffmpeg  (apt install ffmpeg / brew install ffmpeg)
```

From source:

```bash
git clone https://github.com/Dream-Pixels-Forge/spectrumalyzer
cd spectrumalyzer && pip install -e .
```

## CLI

```bash
# analyze + export (comma-separate any of: json,remotion,hyperframes,ae,csv,fcpxml)
spectrumalyzer analyze track.mp3 --fps 30 --format remotion,csv,ae

# frame numbers at 24 fps, tempo hints for tricky tracks
spectrumalyzer analyze track.mp3 --fps 24 --min-bpm 70 --max-bpm 180

# everything to stdout (pipeable)
spectrumalyzer analyze track.mp3 --stdout

# visual HTML report (waveform + beats + band heatmap + sections)
spectrumalyzer report track.mp3 -o report.html

# list formats
spectrumalyzer formats
```

Output files for `analyze song.mp3 -o out --format json,remotion,ae`:

```
out.json                rich JSON (everything)
out.remotion.json       frame-native + out.useBeats.ts React hook
out.markers.jsx         After Effects comp-marker script
```

## Python API

```python
from spectrumalyzer import analyze

result = analyze("track.mp3", fps=30)

result.bpm                     # 128.32
result.beats_as_frames()       # [0, 56, 112, ...] at 30 fps
result.band_rows_at_fps()      # [[sub,bass,lowMid,mid,highMid,treble] x every frame]
result.sections                # [Section(start, end, energy, label), ...]
result.to_dict()               # JSON-ready
```

## Using it in your tool

**Remotion** — import the generated hook:

```tsx
import { useBeatPop } from "./song.useBeats";
const scale = useBeatPop(0.15);        // retriggers every beat
```

**HyperFrames** — the `.hyperframes.json` timeline maps 1:1 onto `data-hf-*`
attributes and `hf-seek` listeners (snippet included in the export).

**After Effects** — File → Scripts → Run Script File… on the `.markers.jsx`:
every beat, hit and section becomes a named comp marker.

**Final Cut / Resolve** — import the `.fcpxml` or the marker `.csv`.

## Compatibility note (v0.1.0 → v0.2.0)

`beats`, `beatTimes`, `bpm`, `duration` keys are unchanged. The v0.1.0
`spectrum` key was **not a real FFT** (it was RMS time-slices with synthetic
frequency labels) and is replaced by the real `bands` matrix. See
[CHANGELOG](CHANGELOG.md).

## Development

```bash
pip install -e ".[dev]"       # pytest + ruff
pytest                        # 44 tests, synthetic fixtures, no network
ruff check src tests
```

MIT licensed. Built by [Dream-Pixels-Forge](https://github.com/Dream-Pixels-Forge).
