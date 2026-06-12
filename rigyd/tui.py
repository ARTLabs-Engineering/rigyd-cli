"""Tiny zero-dependency terminal UI for the Rigyd CLI.

Brand language: the Rigyd mark is a crosshair — rendered here as ``[+]`` and
animated by rotating the crosshair 45 degrees (``+`` -> ``x``). Accent color is
the brand lime.

Behavior:
- stderr is a TTY  -> one in-place status line (spinner + stage + progress bar),
  redrawn by a background thread.
- stderr is piped  -> plain de-duplicated lines (CI/agent logs stay parseable).
- Colors respect NO_COLOR and TERM=dumb; result paths on stdout are never styled.
"""

from __future__ import annotations

import os
import sys
import threading
import time

# -- color ------------------------------------------------------------------

_LIME = "\x1b[38;5;190m"
_DIM = "\x1b[2m"
_RED = "\x1b[38;5;203m"
_BOLD = "\x1b[1m"
_RESET = "\x1b[0m"


def _stream_colors(stream) -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def style(text: str, *codes: str, stream=None) -> str:
    stream = stream if stream is not None else sys.stderr
    if not codes or not _stream_colors(stream):
        return text
    return "".join(codes) + text + _RESET


def lime(text: str, stream=None) -> str:
    return style(text, _LIME, stream=stream)


def dim(text: str, stream=None) -> str:
    return style(text, _DIM, stream=stream)


def glyph(inner: str = "+", stream=None) -> str:
    """The bracketed crosshair: dim brackets, lime core."""
    return dim("[", stream=stream) + lime(inner, stream=stream) + dim("]", stream=stream)


def ok_line(text: str, stream=None) -> str:
    return f"{glyph('+', stream=stream)} {text}"


def err_line(text: str, stream=None) -> str:
    return f"{glyph('!', stream=stream)} {style(text, _RED, stream=stream)}"


def bar(frac: float, width: int = 14, stream=None) -> str:
    frac = max(0.0, min(1.0, frac))
    filled = int(round(frac * width))
    return (lime("█" * filled, stream=stream)
            + dim("░" * (width - filled), stream=stream))


def _elapsed(since: float) -> str:
    total = int(time.monotonic() - since)
    return f"{total // 60}m{total % 60:02d}s" if total >= 60 else f"{total}s"


# -- banner -------------------------------------------------------------------

_CROSSHAIR = [
    "  ██  ",
    "  ██  ",
    "██████",
    "  ██  ",
    "  ██  ",
]

_WORDMARK = [
    "██████  ██  ██████  ██  ██  █████ ",
    "██  ██  ██  ██      ██  ██  ██  ██",
    "██████  ██  ██ ███   ████   ██  ██",
    "██ ██   ██  ██  ██    ██    ██  ██",
    "██  ██  ██  ██████    ██    █████ ",
]


def banner(stream=None, tagline: str = "") -> str:
    """The Rigyd logo as terminal art: lime crosshair + blocky wordmark,
    framed by the logo's dim corner registration marks."""
    stream = stream if stream is not None else sys.stdout
    rows = [
        "  " + lime(c, stream=stream) + "  " + style(w, _BOLD, stream=stream)
        for c, w in zip(_CROSSHAIR, _WORDMARK)
    ]
    width = 2 + len(_CROSSHAIR[0]) + 2 + len(_WORDMARK[0]) + 2
    top = dim("▛" + " " * width + "▜", stream=stream)
    bottom = dim("▙" + " " * width + "▟", stream=stream)
    out = [top] + [" " + r for r in rows] + [bottom]
    if tagline:
        out.append(" " + dim(tagline, stream=stream))
    return "\n".join(out) + "\n"


# -- status line ------------------------------------------------------------

_FRAMES = ["+", "+", "×", "×"]  # crosshair rotating 45 degrees


class StatusLine:
    """One animated, in-place status line on stderr (plain lines when piped)."""

    def __init__(self, stream=None, interval: float = 0.25):
        self._stream = stream or sys.stderr
        self._tty = bool(getattr(self._stream, "isatty", lambda: False)())
        self._interval = interval
        self._lock = threading.Lock()
        self._text = ""
        self._frac: float | None = None
        self._frame = 0
        self._started = time.monotonic()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_plain = ""

    # -- lifecycle -----------------------------------------------------------
    def start(self, text: str = "") -> "StatusLine":
        self._started = time.monotonic()
        self.update(text)
        if self._tty and self._thread is None:
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        return self

    def update(self, text: str, frac: float | None = None) -> None:
        with self._lock:
            self._text = text
            self._frac = frac
        if not self._tty:
            plain = f"  [{_FRAMES[0]}] {text}" + (
                f" {int(round((frac or 0) * 100))}%" if frac is not None else "")
            if plain != self._last_plain:
                print(plain, file=self._stream)
                self._last_plain = plain

    def done(self, text: str) -> None:
        self._finish(ok_line(text, stream=self._stream))

    def fail(self, text: str) -> None:
        self._finish(err_line(text, stream=self._stream))

    def _finish(self, line: str) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None
        if self._tty:
            self._stream.write("\r\x1b[2K")
        print(line, file=self._stream)
        self._stream.flush()

    # -- render --------------------------------------------------------------
    def _spin(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                text, frac = self._text, self._frac
            frame = _FRAMES[self._frame % len(_FRAMES)]
            self._frame += 1
            parts = [glyph(frame, stream=self._stream), text]
            if frac is not None:
                parts += [bar(frac, stream=self._stream),
                          f"{int(round(frac * 100)):>3}%"]
            parts.append(dim(_elapsed(self._started), stream=self._stream))
            self._stream.write("\r\x1b[2K " + "  ".join(p for p in parts if p))
            self._stream.flush()
            self._stop.wait(self._interval)
