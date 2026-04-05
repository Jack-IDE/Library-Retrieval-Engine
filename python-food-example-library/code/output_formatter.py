"""
output_formatter.py — Terminal output utilities: tables, color, progress bars,
tree views, and human-readable size/duration formatting.

All color output is gated behind a is_color_enabled() check so piped output
and NO_COLOR environments are automatically handled.  Table and tree rendering
use only ASCII box characters by default with a unicode fallback.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Iterable, List, Optional, Sequence


def is_color_enabled(stream=None) -> bool:
    """Return True if color output is appropriate for the given stream.

    Checks: NO_COLOR env var (https://no-color.org), FORCE_COLOR env var,
    whether the stream is a TTY, and the TERM env var.  FORCE_COLOR always
    wins over NO_COLOR.  Defaults to sys.stdout.
    """
    if os.environ.get('FORCE_COLOR'):
        return True
    if os.environ.get('NO_COLOR'):
        return False
    stream = stream or sys.stdout
    if not hasattr(stream, 'isatty') or not stream.isatty():
        return False
    term = os.environ.get('TERM', '')
    return term != 'dumb'


def colorize(text: str, color: str, stream=None) -> str:
    """Wrap text in ANSI color escape codes if color output is enabled.

    Supported color names: black, red, green, yellow, blue, magenta, cyan,
    white, and their bright_ variants.  'bold' and 'dim' are also supported
    as modifiers.  Returns plain text unchanged if color is disabled.

    Args:
        text:   Text to colorize.
        color:  Color name string.
        stream: Output stream for TTY detection; defaults to sys.stdout.
    """
    if not is_color_enabled(stream):
        return text
    codes = {
        'black': '30', 'red': '31', 'green': '32', 'yellow': '33',
        'blue': '34', 'magenta': '35', 'cyan': '36', 'white': '37',
        'bright_black': '90', 'bright_red': '91', 'bright_green': '92',
        'bright_yellow': '93', 'bright_blue': '94', 'bright_magenta': '95',
        'bright_cyan': '96', 'bright_white': '97',
        'bold': '1', 'dim': '2',
    }
    code = codes.get(color, '0')
    return f'\x1b[{code}m{text}\x1b[0m'


def print_table(rows: Sequence[Sequence[Any]], headers: Sequence[str] = None,
                sep: str = '  ', stream=None) -> None:
    """Print a list of rows as a fixed-width text table to stream.

    Column widths are computed from the widest value in each column including
    the header row.  Each cell is left-aligned and padded to the column width.
    An optional header row is separated from data rows by a line of dashes.

    Args:
        rows:    Sequence of rows; each row is a sequence of cell values.
        headers: Optional column header strings.
        sep:     Column separator string; defaults to two spaces.
        stream:  Output stream; defaults to sys.stdout.
    """
    stream = stream or sys.stdout
    all_rows = [list(map(str, r)) for r in rows]
    if headers:
        all_rows = [list(headers)] + all_rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r)) for i in range(max(len(r) for r in all_rows))]
    for idx, row in enumerate(all_rows):
        line = sep.join(cell.ljust(widths[i]) for i, cell in enumerate(row))
        print(line.rstrip(), file=stream)
        if headers and idx == 0:
            print(sep.join('-' * w for w in widths), file=stream)


def print_json(data: Any, indent: int = 2, stream=None) -> None:
    """Serialize data to JSON and print it with syntax-like colorization.

    Keys are printed in cyan, string values in green, numbers in yellow,
    booleans and null in magenta.  Falls back to plain JSON when color is
    disabled.  Uses json.dumps for serialization; non-serializable values
    are converted to their repr string before encoding.

    Args:
        data:   Any JSON-serializable value.
        indent: Indentation level for pretty-printing; defaults to 2.
        stream: Output stream; defaults to sys.stdout.
    """
    import json
    stream = stream or sys.stdout

    def default(obj):
        return repr(obj)

    text = json.dumps(data, indent=indent, default=default, ensure_ascii=False)
    if not is_color_enabled(stream):
        print(text, file=stream)
        return
    import re
    def _colorize_token(m):
        tok = m.group(0)
        if tok.startswith('"') and m.group(0).endswith('":'):
            return colorize(tok, 'cyan', stream) + ':'
        if tok.startswith('"'):
            return colorize(tok, 'green', stream)
        if tok in ('true', 'false', 'null'):
            return colorize(tok, 'magenta', stream)
        try:
            float(tok)
            return colorize(tok, 'yellow', stream)
        except ValueError:
            return tok
    colored = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"(?=\s*:)|"[^"\\]*(?:\\.[^"\\]*)*"|-?\d+(?:\.\d+)?|true|false|null', _colorize_token, text)
    print(colored, file=stream)


def truncate_line(text: str, width: int, ellipsis: str = '...') -> str:
    """Truncate a string to fit within width characters, adding an ellipsis.

    If text is shorter than or equal to width, returns it unchanged.  The
    ellipsis is appended within the width budget, so the returned string is
    always <= width characters.  If width is smaller than len(ellipsis),
    returns ellipsis[:width].

    Args:
        text:     Input string to truncate.
        width:    Maximum character width of the returned string.
        ellipsis: Suffix appended when truncation occurs.
    """
    if len(text) <= width:
        return text
    cut = width - len(ellipsis)
    if cut <= 0:
        return ellipsis[:width]
    return text[:cut] + ellipsis


def format_bytes(n: int) -> str:
    """Format a byte count as a human-readable string with SI unit suffix.

    Returns values like '1.2 KB', '45.6 MB', '3.0 GB'.  Byte counts below
    1024 are returned as plain integer strings with ' B'.  Uses 1024-based
    units (KiB semantics) with IEC-style labels (KB, MB, GB, TB).

    Args:
        n: Non-negative integer byte count.
    """
    if n < 1024:
        return f'{n} B'
    for unit in ('KB', 'MB', 'GB', 'TB'):
        n /= 1024.0
        if n < 1024 or unit == 'TB':
            return f'{n:.1f} {unit}'
    return f'{n:.1f} TB'


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as a human-readable string.

    Returns strings like '45s', '2m 3s', '1h 4m', or '0ms' for sub-second
    durations below 1s (shown in milliseconds).  Hours are only shown when
    duration >= 3600s.  Fractional seconds below 1.0 are shown as milliseconds.

    Args:
        seconds: Non-negative float duration in seconds.
    """
    if seconds < 1.0:
        return f'{int(seconds * 1000)}ms'
    s = int(seconds)
    if s < 60:
        return f'{s}s'
    m, s = divmod(s, 60)
    if m < 60:
        return f'{m}m {s}s' if s else f'{m}m'
    h, m = divmod(m, 60)
    return f'{h}h {m}m' if m else f'{h}h'


def print_tree(node: dict, prefix: str = '', stream=None) -> None:
    """Print a nested dict as an ASCII tree to stream.

    Node keys are printed with tree-drawing prefixes (├── and └──).  Values
    that are dicts are recursively printed as subtrees.  Leaf values are
    printed inline after the key name with a colon separator.

    Args:
        node:   Dict where values are either nested dicts (subtrees) or leaf
                values (strings, numbers).
        prefix: Internal prefix string for recursive calls; leave empty.
        stream: Output stream; defaults to sys.stdout.
    """
    stream = stream or sys.stdout
    keys = list(node.keys())
    for i, key in enumerate(keys):
        val = node[key]
        connector = '└── ' if i == len(keys) - 1 else '├── '
        child_prefix = prefix + ('    ' if i == len(keys) - 1 else '│   ')
        if isinstance(val, dict):
            print(prefix + connector + str(key), file=stream)
            print_tree(val, child_prefix, stream)
        else:
            print(prefix + connector + f'{key}: {val}', file=stream)


class ProgressBar:
    """Terminal progress bar with elapsed time and optional ETA.

    Renders a bar like: [=====>    ] 45%  12/27  2s  ETA 3s
    Draws to stderr by default to avoid polluting piped stdout.  Auto-disabled
    when the stream is not a TTY.  Call update() to advance, finish() to
    complete and print a newline.

    Usage:
        bar = ProgressBar(total=100, label='Indexing')
        for i, item in enumerate(items):
            process(item)
            bar.update(i + 1)
        bar.finish()
    """

    def __init__(self, total: int, label: str = '', width: int = 30,
                 stream=None) -> None:
        self.total = total
        self.label = label
        self.width = width
        self.stream = stream or sys.stderr
        self._start = time.monotonic()
        self._current = 0
        self._enabled = is_color_enabled(self.stream)

    def update(self, current: int) -> None:
        """Advance the progress bar to current and redraw."""
        self._current = min(current, self.total)
        if not self._enabled:
            return
        elapsed = time.monotonic() - self._start
        frac = self._current / max(1, self.total)
        filled = int(self.width * frac)
        bar = '=' * filled + ('>' if filled < self.width else '') + ' ' * max(0, self.width - filled - 1)
        pct = f'{int(frac * 100):3d}%'
        count = f'{self._current}/{self.total}'
        dur = format_duration(elapsed)
        eta = ''
        if self._current > 0 and self._current < self.total:
            remaining = elapsed / frac - elapsed
            eta = f'  ETA {format_duration(remaining)}'
        label = f'{self.label}  ' if self.label else ''
        line = f'\r{label}[{bar}] {pct}  {count}  {dur}{eta}'
        self.stream.write(line)
        self.stream.flush()

    def finish(self) -> None:
        """Complete the progress bar and emit a newline."""
        self.update(self.total)
        if self._enabled:
            self.stream.write('\n')
            self.stream.flush()
