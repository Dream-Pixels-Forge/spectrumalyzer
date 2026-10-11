"""FCPXML export — markers for Final Cut Pro, DaVinci Resolve & Compressor.

Generates a minimal but valid FCPXML document wrapping the source audio in an
asset-clip with beat/onset/section markers on the timeline.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from spectrumalyzer.model import AnalysisResult, time_to_frame


def _require_fps(result: AnalysisResult) -> float:
    if not result.fps:
        raise ValueError("FCPXML export needs fps — pass --fps (or fps= to analyze)")
    return result.fps


def _rational(frame: int, fps: float) -> str:
    """FCPXML rational time: '15/30s' for frame 15 at 30 fps."""
    fps_int = int(fps) if fps == int(fps) else fps
    return f"{frame}/{fps_int}s"


def render(result: AnalysisResult) -> str:
    fps = _require_fps(result)
    total = time_to_frame(result.duration, fps)
    asset_name = escape(result.path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1])

    markers = []
    for i, b in enumerate(result.beat_grid):
        frame = time_to_frame(b.time, fps)
        markers.append(
            f'        <marker start="{_rational(frame, fps)}" '
            f'duration="{_rational(1, fps)}" value="beat {i + 1}"/>'
        )
    for o in result.onsets:
        frame = time_to_frame(o.time, fps)
        markers.append(
            f'        <marker start="{_rational(frame, fps)}" '
            f'duration="{_rational(1, fps)}" value="hit ({o.strength:.2f})"/>'
        )
    for s in result.sections:
        frame = time_to_frame(s.start, fps)
        markers.append(
            f'        <marker start="{_rational(frame, fps)}" '
            f'duration="{_rational(1, fps)}" value="section: {escape(s.label)}"/>'
        )
    marker_block = "\n".join(markers)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.8">
  <resources>
    <format id="r1" frameDuration="1/{int(fps) if fps == int(fps) else fps}s"/>
    <asset id="a1" name="{asset_name}" src="{escape(result.path)}" hasAudio="1" format="r1"/>
  </resources>
  <library>
    <event name="spectrumalyzer — {asset_name} @ {round(result.bpm, 1)} BPM">
      <project name="{asset_name} beats">
        <sequence format="r1" duration="{_rational(total, fps)}" tcStart="0/1s" tcFormat="ndf">
          <spine>
            <asset-clip ref="a1" name="{asset_name}" offset="0/1s" duration="{_rational(total, fps)}">
{marker_block}
            </asset-clip>
          </spine>
        </sequence>
      </project>
    </event>
  </library>
</fcpxml>
"""
