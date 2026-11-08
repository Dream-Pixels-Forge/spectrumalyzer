"""spectrumalyzer CLI — analyze, report, formats."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from spectrumalyzer._version import __version__
from spectrumalyzer.embedding.backend import EmbeddingNotAvailable
from spectrumalyzer.exporters import FORMATS, export, export_filename, extra_files


def _load_backend():
    """Load the local embedding backend (seam for tests / dependency injection)."""
    from spectrumalyzer.embedding.backend import EmbeddingBackend

    return EmbeddingBackend.load()


def _ensure_backend():
    """Load the backend, auto-pulling model weights on first use.

    The library ships with the package (single install); the weights are
    downloaded on demand so `describe`/`find`/`--embed` just work out of the
    box. Raises the underlying error when offline.
    """
    from spectrumalyzer.embedding.backend import EmbeddingBackend

    try:
        return EmbeddingBackend.load()
    except EmbeddingNotAvailable:
        print("First run: downloading the embedding model (one-time, ~90 MB) …", file=sys.stderr)
        chosen = EmbeddingBackend.pull()
        print(f"Model ready: {chosen}", file=sys.stderr)
        return EmbeddingBackend.load()


def _analyze_and_enrich(args, quiet: bool):
    """Shared analyze+optional-embed logic; returns (result, payload_extra)."""
    from spectrumalyzer.api import analyze

    result = analyze(
        args.audio if hasattr(args, "audio") else args.audio_path,
        fps=getattr(args, "fps", None),
        bands=not getattr(args, "no_bands", False),
        sections=not getattr(args, "no_sections", False),
        min_bpm=getattr(args, "min_bpm", 60.0),
        max_bpm=getattr(args, "max_bpm", 200.0),
    )
    extra: dict = {}
    if getattr(args, "embed", False):
        from spectrumalyzer.embedding.describe import describe
        from spectrumalyzer.embedding.mood import tag_track

        backend = _load_backend()
        d = describe(result)
        tags = tag_track(backend, d["text"])
        extra = {
            "description": {"summary": d["summary"], "description": d["description"]},
            "tags": {axis: [[t, round(s, 3)] for t, s in scored] for axis, scored in tags.items()},
        }
        _log(quiet, f"  ↳ {d['summary']}")
    return result, extra


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spectrumalyzer",
        description=(
            "Audio-reactive analysis toolkit for motion graphics: spectral-flux beat "
            "detection, BPM, frequency bands, song sections, and frame-native exports "
            "for Remotion, HyperFrames, After Effects, FCPXML and CSV."
        ),
    )
    parser.add_argument("--version", action="version", version=f"spectrumalyzer {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # ---- analyze ---------------------------------------------------------
    p_analyze = sub.add_parser(
        "analyze",
        help="Analyze an audio file and export beat/band data",
        description="Analyze an audio file; export any combination of formats.",
    )
    p_analyze.add_argument("audio", help="Audio file (any format ffmpeg reads)")
    p_analyze.add_argument(
        "-o", "--output", default=None,
        help="Output base path (default: <audio name without extension>). "
             "Each format appends its own suffix.",
    )
    p_analyze.add_argument(
        "-f", "--format", default="json",
        help=f"Comma-separated formats: {', '.join(FORMATS)} (default: json)",
    )
    p_analyze.add_argument(
        "--fps", type=float, default=None,
        help="Video frame rate (24/25/30/60). Required for frame-based exports "
             "(remotion, hyperframes, ae, csv, fcpxml); adds frame numbers to JSON.",
    )
    p_analyze.add_argument(
        "--min-bpm", type=float, default=60.0, help="Tempo search lower bound (default 60)"
    )
    p_analyze.add_argument(
        "--max-bpm", type=float, default=200.0, help="Tempo search upper bound (default 200)"
    )
    p_analyze.add_argument(
        "--no-bands", action="store_true", help="Skip frequency-band analysis"
    )
    p_analyze.add_argument(
        "--no-sections", action="store_true", help="Skip song-structure segmentation"
    )
    p_analyze.add_argument(
        "--stdout", action="store_true", help="Write JSON of the first format to stdout"
    )
    p_analyze.add_argument(
        "--embed", action="store_true",
        help="Add natural-language description + mood tags (requires local embedding model: spectrumalyzer model pull)",
    )
    p_analyze.add_argument("-q", "--quiet", action="store_true", help="Suppress progress output")

    # ---- report ----------------------------------------------------------
    p_report = sub.add_parser(
        "report",
        help="Generate a self-contained HTML visual report",
        description="Analyze an audio file and render an interactive HTML report.",
    )
    p_report.add_argument("audio", help="Audio file (any format ffmpeg reads)")
    p_report.add_argument(
        "-o", "--output", default=None, help="Output HTML path (default: <audio>.report.html)"
    )
    p_report.add_argument("--fps", type=float, default=None, help="Video frame rate for frame data")
    p_report.add_argument("--no-bands", action="store_true", help="Skip band analysis")
    p_report.add_argument("--no-sections", action="store_true", help="Skip section analysis")
    p_report.add_argument("-q", "--quiet", action="store_true", help="Suppress progress output")

    # ---- formats ---------------------------------------------------------
    sub.add_parser("formats", help="List available export formats")

    # ---- model (embedding lifecycle) ---------------------------------------
    p_model = sub.add_parser(
        "model",
        help="Manage the local embedding model",
        description="Pull or inspect the local embedding model used by describe/find/--embed.",
    )
    p_model.add_argument("action", choices=["pull", "status"], help="pull = download to config dir; status = show what is installed")

    # ---- describe ----------------------------------------------------------
    p_desc = sub.add_parser(
        "describe",
        help="Describe a track in natural language + mood tags",
        description="Analyze a track and describe it in words (requires the embedding model).",
    )
    p_desc.add_argument("audio", help="Audio file")
    p_desc.add_argument("--fps", type=float, default=None, help="Frame rate for frame data")
    p_desc.add_argument("--top", type=int, default=3, help="Tags per axis (default 3)")

    # ---- find (semantic library search) -------------------------------------
    p_find = sub.add_parser(
        "find",
        help="Semantic search over a folder of audio files",
        description='e.g. spectrumalyzer find "calm warm bed for intro" ./my-library --limit 5',
    )
    p_find.add_argument("query", help="Natural-language query")
    p_find.add_argument("directory", help="Folder to search (recursive)")
    p_find.add_argument("--limit", type=int, default=10, help="Max results (default 10)")
    p_find.add_argument("--refresh", action="store_true", help="Re-analyze even if cached")

    # ---- mcp (Model Context Protocol server) -------------------------------
    sub.add_parser(
        "mcp",
        help="Run the MCP server (stdio) — spectrumalyzer as tools for AI agents",
        description=(
            "Expose analyze/describe/find/export/report/trim as MCP tools over stdio. "
            'Register with: {"command": "spectrumalyzer", "args": ["mcp"]}'
        ),
    )

    # ---- trim (short version for video) --------------------------------------
    p_trim = sub.add_parser(
        "trim",
        help="Cut the best short version of a long track (or video)",
        description=(
            "Pick the most worthwhile window of a target length (loudness + onset "
            "density + section energy, cuts snapped to the beat) and cut the source "
            "with ffmpeg. Works on video files too — the video is cut to the same window."
        ),
    )
    p_trim.add_argument("audio", help="Audio (or video) file")
    p_trim.add_argument(
        "--length", type=float, default=90.0,
        help="Target length of the short version in seconds (default 90)",
    )
    p_trim.add_argument(
        "-o", "--output", default=None,
        help="Output path (default: <name>-short.mp3 next to the source)",
    )
    p_trim.add_argument(
        "--crossfade", type=float, default=0.5,
        help="Fade in/out seconds at the cut points (default 0.5, 0 disables)",
    )
    p_trim.add_argument(
        "--preview", action="store_true",
        help="Only print the chosen window; do not cut anything",
    )
    p_trim.add_argument("-q", "--quiet", action="store_true", help="Suppress progress output")

    return parser


def _log(quiet: bool, msg: str) -> None:
    if not quiet:
        print(msg, file=sys.stderr)


def _resolve_format(value: str) -> list[str]:
    fmts = [f.strip().lower() for f in value.split(",") if f.strip()]
    unknown = [f for f in fmts if f not in FORMATS]
    if unknown:
        raise SystemExit(
            f"Unknown format(s): {', '.join(unknown)}. Available: {', '.join(FORMATS)}"
        )
    return fmts


def cmd_analyze(args: argparse.Namespace) -> int:
    from spectrumalyzer.api import analyze

    audio = Path(args.audio)
    if not audio.exists():
        print(f"Error: file not found: {audio}", file=sys.stderr)
        return 1

    formats = _resolve_format(args.format)
    if args.fps is None and any(FORMATS[f].requires_fps for f in formats):
        print(
            "Error: format(s) " + ", ".join(f for f in formats if FORMATS[f].requires_fps)
            + " need frame numbers — pass --fps (24/25/30/60)",
            file=sys.stderr,
        )
        return 1

    _log(args.quiet, f"Analyzing {audio.name} …")
    result = analyze(
        str(audio),
        fps=args.fps,
        bands=not args.no_bands,
        sections=not args.no_sections,
        min_bpm=args.min_bpm,
        max_bpm=args.max_bpm,
    )
    _log(
        args.quiet,
        f"BPM {result.bpm:.1f} (confidence {result.bpm_confidence:.2f}) · "
        f"{result.beat_count} beats · {len(result.bars.bars) if result.bars else 0} bars · "
        f"{len(result.onsets)} onsets · "
        f"{len(result.sections)} sections · {result.duration:.1f}s",
    )

    extra_payload: dict = {}
    if getattr(args, "embed", False):
        from spectrumalyzer.embedding.describe import describe, feature_vector
        from spectrumalyzer.embedding.mood import tag_track

        try:
            backend = _load_backend()
            d = describe(result)
            tags = tag_track(backend, d["text"], features=feature_vector(result))
            extra_payload = {
                "description": {"summary": d["summary"], "description": d["description"]},
                "tags": {axis: [[t, round(s, 3)] for t, s in scored] for axis, scored in tags.items()},
            }
            _log(args.quiet, f"  ↳ {d['summary']}")
        except Exception as exc:  # noqa: BLE001 — surface model/IO errors to the user
            print(f"warning: embedding skipped ({exc})", file=sys.stderr)

    base = args.output
    written: list[str] = []

    if args.stdout:
        first = export(result, formats[0])
        sys.stdout.write(first if formats[0] != "json" else json.dumps(result.to_dict(), indent=2))
        sys.stdout.write("\n")

    for fmt in formats:
        out_path = export_filename(result, fmt, base=base)
        rendered = export(result, fmt)
        if extra_payload and fmt == "json":
            import json as _json

            data = _json.loads(rendered)
            data.update(extra_payload)
            rendered = _json.dumps(data, indent=2)
        Path(out_path).write_text(rendered, encoding="utf-8")
        written.append(out_path)
        base_stem = out_path.removesuffix(FORMATS[fmt].suffix)
        for extra_suffix, content in extra_files(result, fmt, base=base_stem).items():
            extra_path = str(Path(out_path).parent / (Path(base_stem).name + extra_suffix))
            Path(extra_path).write_text(content, encoding="utf-8")
            written.append(extra_path)
        _log(args.quiet, f"  → {out_path}")

    if not args.quiet:
        print()
        print("Beats (first 8):")
        for i, b in enumerate(result.beat_grid[:8]):
            frame = f"  [frame {b.frame}]" if b.frame is not None else ""
            print(f"  {i + 1}. {b.time:7.3f}s  strength {b.strength:.2f}{frame}")
        if result.bars and result.bars.bars:
            print()
            print("Bars (first 4):")
            for bar in result.bars.bars[:4]:
                f = f"  [frame {bar.frame}]" if bar.frame is not None else ""
                print(f"  BAR {bar.index + 1}: {bar.downbeat_time:7.3f}s → {bar.end_time:7.3f}s{f}")
        print()
        print(f"Files written: {len(written)}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from spectrumalyzer.report.html_report import write_report

    audio = Path(args.audio)
    if not audio.exists():
        print(f"Error: file not found: {audio}", file=sys.stderr)
        return 1
    out = args.output or str(audio.with_suffix(".report.html"))
    write_report(str(audio), out, fps=args.fps)
    _log(args.quiet, f"Report written: {out}")
    return 0


def cmd_formats(_args: argparse.Namespace) -> int:
    print("Export formats:")
    for spec in FORMATS.values():
        fps_note = " (needs --fps)" if spec.requires_fps else ""
        print(f"  {spec.name:<12} → *{spec.suffix:<20}{fps_note}")
        print(f" {' ' * 14}{spec.description}")
    return 0


def cmd_model(args: argparse.Namespace) -> int:
    from spectrumalyzer.embedding.backend import (
        FALLBACK_MODEL,
        PREFERRED_MODEL,
        EmbeddingBackend,
        default_model_dir,
    )

    d = default_model_dir()
    if args.action == "status":
        print(f"Model home:        {d}")
        print(f"Preferred model:   {PREFERRED_MODEL}  (Gemma license: accept on HF + HF_TOKEN)")
        print(f"Fallback model:    {FALLBACK_MODEL}  (non-gated, automatic)")
        installed = EmbeddingBackend.downloaded_name()
        if installed:
            print(f"Installed:         {installed} ✓")
        elif EmbeddingBackend.is_downloaded():
            print("Installed:         (local files present)")
        else:
            print("Installed:         none — run: spectrumalyzer model pull")
        return 0

    print(f"Pulling embedding model into {d} …")
    try:
        chosen = EmbeddingBackend.pull()
    except Exception as exc:  # noqa: BLE001 — surface model/IO errors to the user
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Installed: {chosen}")
    return 0


def cmd_describe(args: argparse.Namespace) -> int:
    from spectrumalyzer.api import analyze
    from spectrumalyzer.embedding.describe import describe, feature_vector
    from spectrumalyzer.embedding.mood import tag_track

    audio = Path(args.audio)
    if not audio.exists():
        print(f"Error: file not found: {audio}", file=sys.stderr)
        return 1
    try:
        backend = _load_backend()
    except Exception as exc:  # noqa: BLE001 — surface model/IO errors to the user
        print(f"Error: {exc}", file=sys.stderr)
        return 1


    result = analyze(str(audio), fps=args.fps)
    d = describe(result)
    tags = tag_track(backend, d["text"], features=feature_vector(result), top_k=args.top)

    print(f"{audio.name}")
    print(f"  {d['summary']}")
    print(f"  {d['description']}")
    print()
    for axis, scored in tags.items():
        label = ", ".join(f"{t} ({s:.2f})" for t, s in scored)
        print(f"  {axis:<8} {label}")
    return 0


def cmd_find(args: argparse.Namespace) -> int:
    from spectrumalyzer.api import analyze
    from spectrumalyzer.embedding.describe import (
        describe,
        embedding_text,
        feature_vector,
    )
    from spectrumalyzer.embedding.mood import tag_track
    from spectrumalyzer.embedding.store import EmbeddingStore

    directory = Path(args.directory)
    files = EmbeddingStore.audio_files(directory)
    if not files:
        print(f"No audio files found in {directory}", file=sys.stderr)
        return 1
    try:
        backend = _load_backend()
    except Exception as exc:  # noqa: BLE001 — surface model/IO errors to the user
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    store = EmbeddingStore()
    store.model_name = backend.name
    indexed = 0
    for f in files:
        stat = EmbeddingStore._stat_of(f)
        if not args.refresh and store.get(f, stat) is not None:
            continue
        _log(False, f"Analyzing {f.name} …")
        result = analyze(str(f))
        d = describe(result)
        tags = tag_track(backend, d["text"], features=feature_vector(result))
        vec = backend.embed_one(embedding_text(d, tags))
        store.upsert_entry(
            f, summary=d["text"], embedding=vec.tolist(), tags=tags,
            bpm=result.bpm, duration=result.duration, stat=stat,
        )
        indexed += 1
    if indexed:
        store.save()

    hits = store.search(args.query, embedder=backend, k=args.limit)
    if not hits:
        print("No matches.")
        return 0
    print(f"\nTop {len(hits)} matches for '{args.query}':\n")
    for i, hit in enumerate(hits, 1):
        bpm = f"{hit['bpm']:.0f} bpm" if hit.get("bpm") else "—"
        top_tags = ", ".join(
            t for axis in ("mood", "energy", "use")
            for t, _ in (hit.get("tags") or {}).get(axis, [])[:1]
        )
        print(f"  {i}. [{hit['score']:+.3f}] {Path(hit['path']).name}  ({bpm}; {top_tags})")
        print(f"      {hit['summary'][:110]}")
    print()
    return 0


def cmd_trim(args: argparse.Namespace) -> int:
    from spectrumalyzer.api import analyze
    from spectrumalyzer.trimmer import default_output_path, select_trim_window, trim_audio

    audio = Path(args.audio)
    if not audio.exists():
        print(f"Error: file not found: {audio}", file=sys.stderr)
        return 1

    _log(args.quiet, f"Analyzing {audio.name} …")
    result = analyze(str(audio))
    selection = select_trim_window(result, args.length)
    _log(
        args.quiet,
        f"Window: {selection.start:7.2f}s → {selection.end:7.2f}s "
        f"({selection.duration:.1f}s of {result.duration:.1f}s)",
    )
    for r in selection.reasons:
        _log(args.quiet, f"  · {r}")

    if args.preview:
        return 0

    if not selection.trimmed:
        _log(args.quiet, "Nothing to trim — track is already short enough.")
        return 0

    out = args.output or default_output_path(str(audio))
    try:
        trim_audio(str(audio), out, selection.start, selection.end, crossfade=args.crossfade)
    except Exception as exc:  # noqa: BLE001 — surface ffmpeg/IO errors to the user
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    _log(args.quiet, f"Short version written: {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "analyze":
        return cmd_analyze(args)
    if args.command == "report":
        return cmd_report(args)
    if args.command == "formats":
        return cmd_formats(args)
    if args.command == "mcp":
        from spectrumalyzer.mcp_server import main as mcp_main

        return mcp_main()
    if args.command == "model":
        return cmd_model(args)
    if args.command == "describe":
        return cmd_describe(args)
    if args.command == "find":
        return cmd_find(args)
    if args.command == "trim":
        return cmd_trim(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
