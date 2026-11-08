"""MCP server — spectrumalyzer as native tools for AI agents.

Exposes the analysis, description, search, export and reporting capabilities
over the Model Context Protocol (stdio transport). Run with:

    spectrumalyzer mcp

Client registration (e.g. Claude Desktop / pi / any MCP host):

    {"command": "spectrumalyzer", "args": ["mcp"]}

Design notes:
- Tools return LEAN payloads by default (no multi-thousand-row band matrices);
  pass include_analysis=true when the full matrices are wanted.
- All tools are read-only with respect to the user's audio; the only writes
  are export targets the caller names and the embedding index under
  ~/.config/spectrumalyzer/.
- Errors are returned as structured {"error": ...} payloads (never raised
  through the protocol), so agents can react instead of crashing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from spectrumalyzer._version import __version__
from spectrumalyzer.exporters import FORMATS, export, export_filename, extra_files

TOOL_NAMES = (
    "analyze_audio",
    "describe_audio",
    "find_music",
    "export_beats",
    "render_report",
    "model_status",
    "trim_audio",
    "generate_cut_list",
)


def _err(message: str, **extra: Any) -> str:
    return json.dumps({"error": message, **extra})


def _analyze_lean(path: str, fps: float | None, include_analysis: bool,
                  min_bpm: float, max_bpm: float) -> dict[str, Any]:
    from spectrumalyzer.api import analyze

    result = analyze(
        path, fps=fps, bands=True, sections=True,
        min_bpm=min_bpm, max_bpm=max_bpm,
    )
    data = result.to_dict(fps=fps, include_analysis=include_analysis)
    # lean defaults: drop the per-frame series agents rarely need in full
    if not include_analysis:
        data.pop("loudness", None)
        data.pop("centroid", None)
        data.pop("waveformPeaks", None)
    return data


def create_server() -> FastMCP:
    mcp = FastMCP(
        "spectrumalyzer",
        instructions=(
        "Audio-reactive analysis for motion graphics: beat/tempo detection, "
        "frequency bands, song sections, semantic description and search, and "
        "frame-native exports for Remotion, HyperFrames, After Effects, FCPXML "
        "and CSV. All analysis runs locally."
    ))

    @mcp.tool()
    def analyze_audio(
        path: str,
        fps: float | None = None,
        include_analysis: bool = False,
        min_bpm: float = 60.0,
        max_bpm: float = 200.0,
    ) -> str:
        """Analyze an audio file: BPM, beat grid, bars, onsets, sections, key.

        Returns bpm, bpmConfidence, beats (time/frame/strength), bars,
        downbeats, onsets, sections, and key (Krumhansl-Schmuckler key with
        Camelot position + a deterministic palette suggestion; "unknown" with
        confidence 0 when the material has no trustworthy tonality).
        Set fps (24/25/30/60) for frame numbers. Set include_analysis=true to
        also receive the full frequency-band matrix, spectral centroid and
        loudness envelope (large payload).
        """
        p = Path(path)
        if not p.exists():
            return _err("file_not_found", path=path)
        try:
            data = _analyze_lean(path, fps, include_analysis, min_bpm, max_bpm)
        except Exception as exc:  # noqa: BLE001 — report decoder errors to the agent
            return _err("analysis_failed", detail=str(exc))
        return json.dumps(data)

    @mcp.tool()
    def describe_audio(path: str, top: int = 3) -> str:
        """Describe a track in natural language with mood/energy/flavor/use tags.

        Requires the embedding model (auto-downloads on first use, ~90 MB).
        Tags blend embedding similarity with measured feature profiles.
        """
        p = Path(path)
        if not p.exists():
            return _err("file_not_found", path=path)
        try:
            from spectrumalyzer.api import analyze
            from spectrumalyzer.embedding.describe import describe, feature_vector
            from spectrumalyzer.embedding.lifecycle import ensure_backend
            from spectrumalyzer.embedding.mood import tag_track

            backend = ensure_backend()
            result = analyze(path)
            d = describe(result)
            tags = tag_track(backend, d["text"], features=feature_vector(result), top_k=top)
            return json.dumps({
                "summary": d["summary"],
                "description": d["description"],
                "tags": {axis: [[t, round(s, 3)] for t, s in scored] for axis, scored in tags.items()},
            })
        except Exception as exc:  # noqa: BLE001 — surface model/IO errors to the agent
            return _err("describe_failed", detail=str(exc))

    @mcp.tool()
    def find_music(query: str, directory: str, limit: int = 10) -> str:
        """Semantic search over a folder of audio files.

        Natural-language query ("calm warm bed for an intro") against an
        indexed library; results ranked by embedding similarity with bpm and
        tags. The index persists and refreshes per-file by mtime/size.
        """
        directory_path = Path(directory)
        if not directory_path.exists():
            return _err("directory_not_found", directory=directory)
        try:
            from spectrumalyzer.embedding.describe import describe, embedding_text, feature_vector
            from spectrumalyzer.embedding.lifecycle import ensure_backend
            from spectrumalyzer.embedding.mood import tag_track
            from spectrumalyzer.embedding.store import EmbeddingStore

            backend = ensure_backend()
            store = EmbeddingStore()
            store.model_name = backend.name
            files = EmbeddingStore.audio_files(directory)
            if not files:
                return _err("no_audio_files", directory=directory)
            for f in files:
                stat = EmbeddingStore._stat_of(f)
                if store.get(f, stat) is not None:
                    continue
                from spectrumalyzer.api import analyze

                result = analyze(str(f))
                d = describe(result)
                tags = tag_track(backend, d["text"], features=feature_vector(result))
                store.upsert_entry(
                    f, summary=embedding_text(d, tags),
                    embedding=backend.embed_one(embedding_text(d, tags)).tolist(),
                    tags=tags, bpm=result.bpm, duration=result.duration, stat=stat,
                )
                store.save()
            hits = store.search(query, embedder=backend, k=limit)
            return json.dumps({"query": query, "count": len(hits), "hits": hits})
        except Exception as exc:  # noqa: BLE001
            return _err("search_failed", detail=str(exc))

    @mcp.tool()
    def export_beats(
        path: str,
        format: str = "json",
        fps: float | None = None,
        output: str | None = None,
    ) -> str:
        """Export beat/band data in a creative-tool format.

        format: comma-separated list of json, remotion, hyperframes, ae, csv,
        fcpxml. fps required for frame-based formats (remotion, hyperframes,
        ae, csv, fcpxml). Returns the list of files written.
        """
        p = Path(path)
        if not p.exists():
            return _err("file_not_found", path=path)
        fmts = [f.strip().lower() for f in format.split(",") if f.strip()]
        unknown = [f for f in fmts if f not in FORMATS]
        if unknown:
            return _err(
                "invalid_format",
                unknown=unknown,
                available=sorted(FORMATS),
            )
        needs_fps = any(FORMATS[f].requires_fps for f in fmts)
        if needs_fps and not fps:
            return _err(
                "fps_required",
                formats_requiring_fps=[f for f in fmts if FORMATS[f].requires_fps],
            )
        try:
            from spectrumalyzer.api import analyze

            result = analyze(str(p), fps=fps)
            base = output
            written: list[str] = []
            for fmt in fmts:
                out_path = export_filename(result, fmt, base=base)
                Path(out_path).write_text(export(result, fmt), encoding="utf-8")
                written.append(out_path)
                for extra_name, content in extra_files(result, fmt).items():
                    base_stem = out_path.removesuffix(FORMATS[fmt].suffix)
                    extra_path = str(Path(out_path).parent / (Path(base_stem).name + extra_name))
                    Path(extra_path).write_text(content, encoding="utf-8")
                    written.append(extra_path)
            return json.dumps({"written": written, "count": len(written), "bpm": round(result.bpm, 2)})
        except Exception as exc:  # noqa: BLE001
            return _err("export_failed", detail=str(exc))

    @mcp.tool()
    def render_report(path: str, output: str | None = None, fps: float | None = None) -> str:
        """Render a self-contained HTML visual report for an audio file.

        Returns the path of the written report (waveform + beats + band
        heatmap + sections — open it in a browser).
        """
        p = Path(path)
        if not p.exists():
            return _err("file_not_found", path=path)
        try:
            from spectrumalyzer.report.html_report import write_report

            out = output or str(p.with_suffix(".report.html"))
            write_report(str(p), out, fps=fps)
            return json.dumps({"report": str(out)})
        except Exception as exc:  # noqa: BLE001
            return _err("report_failed", detail=str(exc))

    @mcp.tool()
    def model_status() -> str:
        """Report the local embedding model state (installed model, paths).

        Useful before calling describe_audio / find_music.
        """
        from spectrumalyzer.embedding.backend import (
            FALLBACK_MODEL,
            PREFERRED_MODEL,
            EmbeddingBackend,
            default_model_dir,
        )

        return json.dumps({
            "modelHome": str(default_model_dir()),
            "preferred": PREFERRED_MODEL,
            "fallback": FALLBACK_MODEL,
            "installed": EmbeddingBackend.downloaded_name(),
            "version": __version__,
        })

    @mcp.tool()
    def trim_audio(
        path: str,
        length_s: float = 90.0,
        output: str | None = None,
        crossfade_s: float = 0.5,
        preview: bool = False,
    ) -> str:
        """Cut the best short version of a long track (or video) for video use.

        Picks the most worthwhile window of length_s (loudness + onset density
        + section energy, cuts snapped to the beat grid) and cuts the source
        with ffmpeg. If the source is a video, the video is cut to the same
        window. Returns the window, why it was chosen, and the written file
        (skipped when the track is already short enough or preview=true).
        """
        p = Path(path)
        if not p.exists():
            return _err("file_not_found", path=path)
        try:
            from spectrumalyzer.api import analyze
            from spectrumalyzer.trimmer import default_output_path, select_trim_window
            from spectrumalyzer.trimmer import trim_audio as cut

            result = analyze(str(p))
            sel = select_trim_window(result, length_s)
            written: str | None = None
            if not preview and sel.trimmed:
                written = cut(
                    str(p),
                    output or default_output_path(str(p)),
                    sel.start,
                    sel.end,
                    crossfade=crossfade_s,
                )
            return json.dumps(
                {
                    "selection": sel.to_dict(),
                    "sourceDuration": round(result.duration, 3),
                    "output": written,
                    "skipped": (not sel.trimmed) or preview or not written,
                }
            )
        except Exception as exc:  # noqa: BLE001 — surface ffmpeg/decoder errors to the agent
            return _err("trim_failed", detail=str(exc))

    @mcp.tool()
    def generate_cut_list(
        path: str,
        every_beats: int = 4,
        section: str | None = None,
        tier: str | None = None,
        clip_len_s: float | None = None,
        fps: float | None = None,
    ) -> str:
        """Generate an edit-decision cut list for video editing.

        Pure selection over the analysis: cuts every N beats on the beat
        grid, optionally restricted to one section label ('peak' = the
        loudest section) and/or one impact tier ('downbeat'/'accent'/
        'normal'), with optional clip windows (montage holds). Returns JSON
        with {everyBeats, section, tier, clipLen, count, cuts:[{time,in,out,
        frame,tier,section,energy,reason}]}. No media is cut — this is data
        for your NLE's EDL/marker import.
        """
        p = Path(path)
        if not p.exists():
            return _err("file_not_found", path=path)
        try:
            from spectrumalyzer.analysis.cutlist import (
                CutList,
            )
            from spectrumalyzer.analysis.cutlist import (
                generate_cut_list as _gen,
            )
            from spectrumalyzer.api import analyze

            result = analyze(str(p))
            cuts = _gen(
                result,
                every_beats=every_beats,
                section=section,
                tier=tier,
                clip_len=clip_len_s,
                fps=fps,
            )
            cl = CutList(
                cuts=cuts, every_beats=every_beats, section=section,
                tier=tier, clip_len=clip_len_s, fps=fps or result.fps,
            )
            return json.dumps(cl.to_dict())
        except Exception as exc:  # noqa: BLE001 — surface decoder errors to the agent
            return _err("cut_list_failed", detail=str(exc))

    @mcp.resource("spectrumalyzer://formats")
    def formats() -> str:
        """List available export formats."""
        return json.dumps({
            spec.name: {"suffix": spec.suffix, "description": spec.description,
                        "requires_fps": spec.requires_fps}
            for spec in FORMATS.values()
        })

    return mcp


def main() -> int:
    """Entry point for `spectrumalyzer mcp` — blocking stdio server."""
    server = create_server()
    server.run()  # stdio transport (default)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
