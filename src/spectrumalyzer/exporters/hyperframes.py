"""HyperFrames export — timeline events + data-* snippet.

HyperFrames compositions are HTML with data-* timing attributes and seek
events, so the JSON mirrors that shape: one event list with frame numbers a
composition can map onto data-hf-* attributes or hf-seek listeners.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spectrumalyzer.model import AnalysisResult, time_to_frame


def _require_fps(result: AnalysisResult) -> float:
    if not result.fps:
        raise ValueError("HyperFrames export needs fps — pass --fps (or fps= to analyze)")
    return result.fps


def render(result: AnalysisResult) -> str:
    fps = _require_fps(result)
    events = []
    for i, b in enumerate(result.beat_grid):
        events.append({
            "frame": time_to_frame(b.time, fps),
            "type": "beat",
            "index": i + 1,
            "strength": round(b.strength, 3),
        })
    for o in result.onsets:
        events.append({
            "frame": time_to_frame(o.time, fps),
            "type": "onset",
            "strength": round(o.strength, 3),
        })
    if result.bars is not None:
        for bar in result.bars:
            f = bar.frame if bar.frame is not None else time_to_frame(bar.downbeat_time, fps)
            events.append({
                "frame": f,
                "type": "bar",
                "index": bar.index,
                "endFrame": bar.end_frame if bar.end_frame is not None else time_to_frame(bar.end_time, fps),
            })
            events.append({
                "frame": f,
                "type": "downbeat",
                "index": bar.index,
            })
    for s in result.sections:
        events.append({
            "frame": time_to_frame(s.start, fps),
            "endFrame": time_to_frame(s.end, fps),
            "type": "section",
            "label": s.label,
            "energy": round(s.energy, 3),
        })
    events.sort(key=lambda e: (e["frame"], e["type"]))

    data: dict[str, Any] = {
        "bpm": round(result.bpm, 2),
        "fps": int(fps) if fps == int(fps) else fps,
        "durationInFrames": time_to_frame(result.duration, fps),
        "timeline": {
            "fps": int(fps) if fps == int(fps) else fps,
            "events": events,
        },
    }
    if result.key is not None and result.key.key != "unknown":
        data["key"] = result.key.key
        data["keyConfidence"] = round(result.key.confidence, 3)
        data["camelot"] = result.key.camelot
        data["palette"] = result.key.palette
    rows = result.band_rows_at_fps()
    if rows is not None:
        data["bandsByFrame"] = rows
        data["bandNames"] = ["sub", "bass", "lowMid", "mid", "highMid", "treble"]
    return json.dumps(data, indent=2)


def extras(result: AnalysisResult, base: str = "song") -> dict[str, str]:
    data_name = Path(base).name + ".hyperframes.json"
    snippet = f"""<!-- spectrumalyzer x HyperFrames — beat-reactive composition -->
<!--
  1) Copy {data_name} next to your composition.
  2) Load it and drive your timeline with the events, e.g.:

  <script type="module">
    import data from './{data_name}' with {{ type: 'json' }};
    const beats = data.timeline.events.filter(e => e.type === 'beat');

    // Beat-scaled visual: grow the element on each beat
    const el = document.querySelector('#reactive');
    document.addEventListener('hf-seek', (ev) => {{
      const frame = ev.detail.frame;
      const last = [...beats].reverse().find(b => b.frame <= frame);
      if (last && frame - last.frame < 5) {{
        const pop = 1 + 0.2 * last.strength * (1 - (frame - last.frame) / 5);
        el.style.transform = `scale(${{pop}})`;
      }} else {{
        el.style.transform = 'scale(1)';
      }}
    }});

    // Static timing alternative: one clip per section
    for (const s of data.timeline.events.filter(e => e.type === 'section')) {{
      console.log(`section ${{s.label}}: data-hf-start="${{s.frame}}" data-hf-end="${{s.endFrame}}"`);
    }}
  </script>
-->
"""
    return {".hyperframes.snippet.html": snippet}
