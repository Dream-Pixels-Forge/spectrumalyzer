"""Watch mode — re-analyze + re-export on file change (v1.3).

Ported for iterative edit sessions: trim a video bed, audition cuts, re-export
at a different fps — without re-running the CLI by hand. The session polls a
source file, and when its ``(mtime_ns, size)`` changes it re-runs the analysis
(through the v1.1 precomputed cache, so a touch that only bumps mtime is an
instant cache hit) and re-exports to the same output path.

Design decisions (documented):
- **Polling, not inotify.** Pure stdlib, portable (Windows/macOS/Linux), no
  ``watchdog`` dependency. ``inotify``/``FSEvents`` are a v2 refinement if
  sub-poll-latency ever matters.
- **Reuses ``analyze_cached``** (v1.1): the watch loop never pays for a
  content-unchanged re-export.
- **Clock- and stop-injectable** ``run()`` so tests never sleep in CI.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Callable

from spectrumalyzer.analysis.cache import analyze_cached
from spectrumalyzer.model import AnalysisResult


def change_key(path: str) -> tuple[int, int]:
    """The (mtime_ns, size) tuple that identifies one file's content state.

    Exported so the watch loop, tests, and the v1.1 cache-key logic can agree
    on what "the file changed" means.
    """
    st = os.stat(path)
    return (st.st_mtime_ns, st.st_size)


def _default_sleep(seconds: float) -> None:
    time.sleep(seconds)


class WatchSession:
    """Poll one source file and re-export on change.

    Args:
        path: the source audio file to watch.
        out_path: where to write the re-export (a single format's output).
        formats: export formats to write on each change (default json).
        fps: frame rate for frame-based exports (None = no frames).
        analyze_kwargs: extra kwargs forwarded to the analyzer (bands,
            sections, key, min/max bpm, accent quantile, ...).
        on_change: optional ``fn(result, cache_hit)`` hook, called after each
            re-export. Lets a caller (CLI, MCP, test) react without the engine
            knowing about printing.
        sleep_fn: the pause between polls. Injectable so tests use a fake
            clock. Defaults to ``time.sleep``.
    """

    def __init__(
        self,
        path: str,
        out_path: str,
        *,
        formats: tuple[str, ...] | list[str] = ("json",),
        fps: float | None = None,
        analyze_kwargs: dict | None = None,
        on_change: Callable[[AnalysisResult, bool], None] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self.path = path
        self.out_path = out_path
        self.formats: tuple[str, ...] = tuple(formats)
        self.fps = fps
        self.analyze_kwargs = dict(analyze_kwargs or {})
        self.on_change = on_change
        self._sleep = sleep_fn or _default_sleep
        self._last_key: tuple[int, int] | None = None
        self._changes = 0
        self.last_cache_hit: bool | None = None

    # -- introspection -------------------------------------------------------
    @property
    def changes(self) -> int:
        """Number of times the file was seen as changed and re-exported."""
        return self._changes

    # -- core ----------------------------------------------------------------
    def poll(self) -> bool:
        """Check once. Re-export when the file changed; return True on change.

        The first call (no prior key) counts as a change so the watcher always
        produces an initial export. A content-identical touch is a v1.1 cache
        hit — the re-export is still written, but the DSP was not re-run.
        """
        try:
            key = change_key(self.path)
        except OSError:
            # file vanished / unreadable: report unchanged, don't crash the loop
            return False
        if key == self._last_key:
            return False

        result, hit = analyze_cached(
            self.path,
            use_cache=True,
            fps=self.fps,
            **self.analyze_kwargs,
        )
        self._write_exports(result)
        self._last_key = key
        self._changes += 1
        self.last_cache_hit = hit
        if self.on_change is not None:
            self.on_change(result, hit)
        return True

    def _write_exports(self, result: AnalysisResult) -> None:
        from spectrumalyzer.exporters import export, export_filename

        # The first format defines the base; each format appends its own
        # suffix to the same base path.
        base = self.out_path
        first = self.formats[0]
        written = export_filename(result, first, base=base)
        Path(written).write_text(export(result, first), encoding="utf-8")
        for fmt in self.formats[1:]:
            w = export_filename(result, fmt, base=base)
            Path(w).write_text(export(result, fmt), encoding="utf-8")

    def run(
        self,
        interval: float = 1.0,
        max_polls: int | None = None,
        stop_event: threading.Event | None = None,
    ) -> int:
        """Blocking watch loop. Returns the number of re-exports performed.

        Polls immediately, then sleeps ``interval`` between checks. Stops when
        ``stop_event`` is set, ``max_polls`` is reached, or Ctrl-C (the caller
        wraps this; the loop itself re-raises KeyboardInterrupt after a clean
        last poll).
        """
        polls = 0
        while True:
            try:
                self.poll()
            except KeyboardInterrupt:
                break
            polls += 1
            if max_polls is not None and polls >= max_polls:
                break
            if stop_event is not None and stop_event.is_set():
                break
            self._sleep(interval)
        return self._changes
