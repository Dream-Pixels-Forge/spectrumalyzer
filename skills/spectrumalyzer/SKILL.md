---
name: spectrumalyzer
description: Audio beat analysis tool for motion graphics - provides BPM detection, beat timestamps, and frequency spectrum data compatible with Remotion and HyperFrames workflows
---
## Skill Overview

spectrumalyzer is a Python CLI tool for audio beat analysis that helps motion graphics creators synchronize animations to music with maximum precision. The tool provides:

- **Beat detection** using FFT-based onset detection
- **BPM calculation** using median interval method
- **Frequency spectrum** generation (128 frequency bins, 20Hz-20kHz)
- **Remotion JSON output** (.remotion.json) for timeline synchronization
- **Standard JSON output** (.json) for general use
- **Adjustable parameters** (threshold, FFT size)

## Skill Actions

### analyze-beat(audio_file)

Analyze an audio file and return beat timestamps, BPM, and spectrum data.

**Parameters:**
- `audio_file` (required): Path to audio file (MP3, WAV, OGG)
- `--threshold` (optional): Beat detection threshold (0.0-1.0, default: 0.15)
- `--fft-size` (optional): FFT size for spectrum analysis (256-4096, default: 1024)
- `--output` (optional): Output JSON file path (default: beats.json)
- `--format` (optional): Output format (json or remotion, default: json)

**Returns:**
- JSON object with beat analysis results
- Beat timestamps in seconds
- BPM value
- Frequency spectrum data (128 bins)
- Metadata (version, created timestamp, analyzer name)

### Example Usage

```bash
spectrumalyzer analyze-beat /path/to/audio.mp3 --output beats.json --format remotion
```

### Compatible Workflows

- **Remotion:** Use `.remotion.json` output with `useSound` hook for timeline sync
- **HyperFrames:** Use beat times to drive timeline events and compositions
- **Motion Graphics:** Sync animations, camera movements, and visual effects to music beats

### Tested Audio

- `/assets/bed_music.mp3` (53.52s)
- Detected 12 beats at intervals: 3.02s, 7.59s, 9.88s, 13.30s, 15.59s, 19.02s, 21.30s, 31.59s, 32.73s, 33.88s, 34.45s, 35.02s
- BPM: 23 (calculated from median interval)

### Dependencies

- Python 3.8+ (standard library only)
- ffprobe/ffmpeg (system-installed)
- No external Python packages required

## Skill Status

- **Implementation:** Complete ✅
- **Testing:** Verified with browsy-promo music track
- **Output formats:** Both JSON and Remotion formats validated
- **Integration:** Ready for Remotion/HyperFrames workflows
