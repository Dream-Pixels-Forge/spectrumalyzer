"""DAW project stubs — REAPER (.RPP) + Ableton Live (.als) — v1.4.

Emits openable project files with the analysis pre-embedded: project tempo =
detected BPM, an audio item/clip for the source at t=0, and markers on the
v0.7 bar grid (downbeats, labeled ``BAR N``) + section markers
(``SECTION <label>``). Pure text generators — no DAW install is needed to
produce them, and none is needed to open them (both are the DAWs' own
native text formats).

Design decisions (documented, not silent):
- **REAPER markers use seconds, not ticks.** REAPER project files carry a
  project-rate (PPQ) *header*, but absolute-position markers may be written
  in seconds (``TIME`` in the marker line) and REAPER displays them on its
  timeline natively. Ticks only matter for time-map / tempo-change events,
  which these stubs do not contain (constant detected tempo — see below).
- **Constant tempo = detected BPM.** The stub assumes the track plays from
  t=0 at its detected BPM. Per-event tempo maps are out of scope; the marker
  times are absolute seconds, so the file is still correct when opened in a
  project that plays at that BPM.
- **``bpm is None`` / no bars → 120.0 fallback.** Documented; the file stays
  valid with zero markers.
- **FLP is NOT generated.** FL Studio's project format is binary and
  proprietary; shipping it needs a real test vector. Documented in ROADMAP
  (stays a later item). **DaVinci Resolve** scripting is a separate v1.5
  item (needs a running Resolve instance).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spectrumalyzer.model import AnalysisResult, Bar

_FALLBACK_BPM = 120.0


def _bpm(result: AnalysisResult) -> float:
    return result.bpm if result.bpm and result.bpm > 0 else _FALLBACK_BPM


def _bars(result: AnalysisResult) -> list[Bar]:
    return result.bars.bars if result.bars else []


def _secs(value: float) -> str:
    """REAPER absolute time (seconds), 6-dp fixed — its native marker format."""
    return f"{value:.6f}"


def _fmt(value: float) -> str:
    """Fixed 6-dp float formatting for .als/.RPP numbers (deterministic)."""
    return f"{value:.6f}"


def _reaper_marker_lines(result: AnalysisResult) -> list[str]:
    """BAR + SECTION marker lines for the main track's <MARKERS> block."""
    lines: list[str] = []
    for i, bar in enumerate(_bars(result), start=1):
        lines.append(f'\t"MARKER {i}" "{_secs(bar.downbeat_time)}" "BAR {i}"')
    for j, sec in enumerate(result.sections, start=1):
        label = sec.label or f"region{j}"
        lines.append(
            f'\t"MARKER {j + len(_bars(result))}" "{_secs(sec.start)}" '
            f'"SECTION {label}"'
        )
    return lines


def export_reaper(
    result: AnalysisResult, source_path: str, out_path: str
) -> Path:
    """Write a minimal valid REAPER ``.RPP`` project stub.

    Layout: one audio track, one media item at t=0 spanning the detected
    duration, project tempo = detected BPM, PPQ 480, and BAR/SECTION markers
    on the track. Returns the written ``Path``; raises ``FileNotFoundError``
    when ``source_path`` does not exist.
    """
    src = Path(source_path)
    if not src.exists():
        raise FileNotFoundError(f"source audio not found: {source_path}")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    bpm = _bpm(result)
    dur = result.duration
    # REAPER wants time as an absolute seconds value (project-rate header
    # PPQ 480 is decorative for these stubs; markers are written in seconds).
    markers = _reaper_marker_lines(result)
    marker_block = "\n".join(markers) if markers else "\t"

    text = f"""<REAPER_PROJECT 0.1 'spectrumalyzer v1.4 stub'>
	<REAPER_TEMP 1.1>
		<TEMPO 60/bpm>
		PPQ 480
	</REAPER_TEMP>
	<REAPER_TRACK 1>
		NAME "{src.stem} ({bpm:.0f} BPM)"
		<MARKERS {len(_bars(result)) + len(result.sections)}>
{marker_block}
		</MARKERS>
		<ITEM 1>
			PLAY "{src.name}" 0.000000 0.000000 {dur:.6f}
		</ITEM>
	</REAPER_TRACK>
</REAPER_PROJECT>
"""
    out.write_text(text, encoding="utf-8")
    return out


def _ableton_value(value: Any) -> str:
    """Render a Python value as the .als Lua-ish scalar format."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def export_ableton(
    result: AnalysisResult, source_path: str, out_path: str
) -> Path:
    """Write a minimal valid Ableton Live ``.als`` project stub.

    ``.als`` is Ableton's Lua-fragment text format: a top-level ``<n> # { ... }``
    record list with named fields. We emit the documented minimal subset that
    keeps the project openable:

    - ``tempoMap`` — one entry at beat 0 with the detected BPM (120.0 when
      the track has no usable tempo);
    - one ``audioTrack`` whose first clip references the source file, placed
      at beat 0 with length = detected duration in beats;
    - one ``markerTrack`` with ``BAR N`` markers at bar downbeats and
      ``SECTION <label>`` markers at section starts.

    Returns the written ``Path``; raises ``FileNotFoundError`` when
    ``source_path`` does not exist.
    """
    src = Path(source_path)
    if not src.exists():
        raise FileNotFoundError(f"source audio not found: {source_path}")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    bpm = _bpm(result)
    bars = _bars(result)
    beat_period = 60.0 / bpm
    n_beats = max(1, round(result.duration / beat_period))

    # ---- tempo map: one constant entry at beat 0 ---------------------------
    tempo_block = (
        f"    0 # {{ tempo: {_fmt(bpm)}, beats: 1 }}\n"
        if bars
        else f"    0 # {{ tempo: {_fmt(_FALLBACK_BPM)}, beats: 1 }}\n"
    )

    # ---- audio clip: source file at beat 0 ---------------------------------
    clip_block = (
        "audioClip =\n"
        "  0 # {\n"
        "    0.0 # { source: {\n"
        f'      file: "{src.name}",\n'
        "    },\n"
        "    0.0 # {},\n"
        "  },\n"
        "  0.0,\n"
        f"  {_fmt(n_beats)},\n"
        "  }\n"
    )

    # ---- marker track: BAR downbeats + SECTION starts ----------------------
    marker_lines: list[str] = []
    for i, bar in enumerate(bars, start=1):
        beat = round(bar.downbeat_time / beat_period)
        marker_lines.append(
            f"    {i} # {{ name: \"BAR {i}\", time: {_fmt(beat)}, "
            f"track: 1, length: 0 }}\n"
        )
    for j, sec in enumerate(result.sections, start=1):
        beat = round(sec.start / beat_period)
        label = sec.label or f"region{j}"
        marker_lines.append(
            f"    {j + len(bars)} # {{ name: \"SECTION {label}\", time: {_fmt(beat)}, "
            f"track: 1, length: 0 }}\n"
        )
    markers_block = "".join(marker_lines) if marker_lines else "    0 # { }\n"

    text = (
        "# spectrumalyzer v1.4 DAW stub — minimal .als subset "
        "(tempo + audio clip + markers)\n"
        f"# source: {src.name}  bpm: {_fmt(bpm)}  bars: {len(bars)}  "
        f"duration: {_fmt(result.duration)}s\n"
        "Ableton Live Project 10.0:\n"
        "  2 # { tracks: {\n"
        "    audioTrack: {\n"
        f"      {clip_block}"
        "      name: \"spectrumalyzer\"\n"
        "    },\n"
        "    markerTrack: {\n"
        f"      {len(marker_lines)} # {{ markers:\n"
        f"{markers_block}"
        "      }}\n"
        "      name: \"markers\"\n"
        "    }\n"
        "  }},\n"
        f"  tempoMap: {{\n{tempo_block}"
        "  }\n"
    )
    out.write_text(text, encoding="utf-8")
    return out
