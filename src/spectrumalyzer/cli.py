"""spectrumalyzer CLI — analyze, report, formats."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from spectrumalyzer._version import __version__
from spectrumalyzer.exporters import FORMATS, export, export_filename, extra_files


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
        f"{result.beat_count} beats · {len(result.onsets)} onsets · "
        f"{len(result.sections)} sections · {result.duration:.1f}s",
    )

    base = args.output
    written: list[str] = []

    if args.stdout:
        first = export(result, formats[0])
        sys.stdout.write(first if formats[0] != "json" else json.dumps(result.to_dict(), indent=2))
        sys.stdout.write("\n")

    for fmt in formats:
        out_path = export_filename(result, fmt, base=base)
        Path(out_path).write_text(export(result, fmt), encoding="utf-8")
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "analyze":
        return cmd_analyze(args)
    if args.command == "report":
        return cmd_report(args)
    if args.command == "formats":
        return cmd_formats(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
