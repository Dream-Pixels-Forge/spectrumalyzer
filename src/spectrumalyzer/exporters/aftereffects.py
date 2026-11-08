"""After Effects export — ExtendScript that places comp markers on the beats.

Run the generated .jsx via File > Scripts > Run Script File... with a
composition open; every beat/onset becomes a named comp marker you can snap
layers and keyframes to.
"""

from __future__ import annotations

from spectrumalyzer.model import AnalysisResult


def _require_fps(result: AnalysisResult) -> float:
    if not result.fps:
        raise ValueError("After Effects export needs fps — pass --fps (or fps= to analyze)")
    return result.fps


def render(result: AnalysisResult) -> str:
    _require_fps(result)
    fps = int(result.fps) if result.fps == int(result.fps) else result.fps

    beat_times: list[str] = [f"{b.time:.4f}" for b in result.beat_grid]
    onset_times: list[str] = [f"{o.time:.4f}" for o in result.onsets]
    section_lines = []
    for s in result.sections:
        section_lines.append(
            f'    addMarker({s.start:.4f}, "section: {s.label} (energy {s.energy:.2f})");'
        )

    bar_lines: list[str] = []
    downbeat_lines: list[str] = []
    if result.bars is not None:
        for bar in result.bars:
            bar_lines.append(f'addMarker({bar.downbeat_time:.4f}, "BAR {bar.index + 1}");')
            downbeat_lines.append(f'addMarker({bar.downbeat_time:.4f}, "BAR {bar.index + 1} \\u2193");')

    jsx = f"""// spectrumalyzer markers for After Effects
// Generated from: {result.path}
// {len(result.beat_grid)} beats @ {result.bpm} BPM, {len(result.onsets)} onsets, fps {fps}
//
// Usage: File > Scripts > Run Script File... (with your composition open,
// or select a comp in the project panel).

(function spectrumalyzerMarkers() {{
    if (!app.project) {{ alert("No project open."); return; }}
    var comp = app.project.activeItem;
    if (!(comp && comp.name !== undefined && comp.numLayers !== undefined)) {{
        alert("Select a composition first."); return;
    }}

    function addMarker(timeSeconds, comment) {{
        var mv = new MarkerValue(comment);
        comp.markerProperty.setValueAtTime(timeSeconds, mv);
    }}

    app.beginUndoGroup("spectrumalyzer beat markers");

    var beats = [{", ".join(beat_times)}];
    for (var i = 0; i < beats.length; i++) {{
        addMarker(beats[i], "beat " + (i + 1));
    }}

    var onsets = [{", ".join(onset_times)}];
    for (var j = 0; j < onsets.length; j++) {{
        addMarker(onsets[j], "hit");
    }}

    var sections = [
{chr(10).join(section_lines)}
    ];

    var bars = [
{chr(10).join(bar_lines)}
    ];
    for (var k = 0; k < bars.length; k++) {{
        eval(bars[k]);
    }}

    var downbeats = [
{chr(10).join(downbeat_lines)}
    ];
    for (var m = 0; m < downbeats.length; m++) {{
        eval(downbeats[m]);
    }}

    app.endUndoGroup();
    alert("Added " + (beats.length + onsets.length) + " beat/hit markers" +
          ", " + bars.length + " bar markers" +
          " and " + sections.length + " section markers to \\"" + comp.name + "\\".");
}})();
"""
    return jsx
