# Spectrumalyzer

Audio beat analysis tool for motion graphics - provides BPM detection, beat timestamps, and frequency spectrum data compatible with Remotion and HyperFrames workflows.

## Features

- BPM (Beats Per Minute) detection
- Beat timestamp extraction
- Frequency spectrum analysis
- Compatible with Remotion and HyperFrames workflows

## Installation

```bash
pip install spectrumalyzer
```

## Usage

```python
from spectrumalyzer import analyze_audio

# Analyze an audio file
results = analyze_audio("path/to/audio/file.mp3")

# Get BPM
bpm = results["bpm"]

# Get beat timestamps
beats = results["beats"]

# Get frequency spectrum
spectrum = results["spectrum"]
```

## API

See the [SKILL.md](skills/spectrumalyzer/SKILL.md) file for detailed API documentation.

## License

MIT
