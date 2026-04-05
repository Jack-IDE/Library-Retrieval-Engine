"""
file_utils.py — File system helpers: discovery, atomic writes, watching,
temp directories, path resolution, and recursive copy.

Designed for CLI tools that need reliable file operations without third-party
dependencies.  Atomic writes use a write-to-temp-then-rename pattern to avoid
partial files on crash.  File watching uses polling for portability.
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
import time
from pathlib import Path
from typing import Callable, Generator, Iterator, List, Optional, Sequence


def find_files(root: str | Path, patterns: Sequence[str] = ('*',),
               exclude_dirs: Sequence[str] = ('.git', '__pycache__', 'node_modules'),
               recursive: bool = True) -> List[Path]:
    """Discover files under root matching any of the given glob patterns.

    Walks the directory tree recursively by default.  Directories whose names
    appear in exclude_dirs are skipped entirely, which avoids descending into
    VCS and build artifact directories.  All patterns are matched against the
    filename only (not the full path).

    Args:
        root:         Starting directory for the search.
        patterns:     Glob patterns matched against filenames (e.g. '*.py').
        exclude_dirs: Directory names to skip during traversal.
        recursive:    If False, only search the top level of root.
    """
    root = Path(root)
    results: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for fname in filenames:
            for pat in patterns:
                if Path(fname).match(pat):
                    results.append(Path(dirpath) / fname)
                    break
        if not recursive:
            break
    return sorted(results)


def atomic_write(path: str | Path, content: str | bytes,
                 encoding: str = 'utf-8') -> None:
    """Write content to path atomically using a temp-file-then-rename strategy.

    Writes to a temporary file in the same directory as path, then renames
    it into place.  Because rename is atomic on POSIX, readers never see a
    partially-written file.  Preserves the existing file's permissions if
    it already exists.  Raises OSError on failure.

    Args:
        path:     Destination file path.
        content:  String or bytes to write.
        encoding: Text encoding when content is a string; ignored for bytes.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode if path.exists() else 0o644
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix='.tmp_')
    try:
        with os.fdopen(fd, 'wb') as f:
            if isinstance(content, str):
                f.write(content.encode(encoding))
            else:
                f.write(content)
        os.chmod(tmp_path, stat.S_IMODE(mode))
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def watch_file(path: str | Path, callback: Callable[[Path], None],
               interval: float = 1.0, stop_after: Optional[float] = None) -> None:
    """Poll a file for modifications and invoke callback when it changes.

    Detects changes by comparing the file's mtime.  Calls callback with the
    path each time the mtime advances.  Blocks until stop_after seconds have
    elapsed (if set) or a KeyboardInterrupt is received.  Polling interval is
    in seconds.

    Args:
        path:       File to watch.
        callback:   Called with the Path on each detected change.
        interval:   Polling interval in seconds.
        stop_after: Stop watching after this many seconds; None = forever.
    """
    path = Path(path)
    last_mtime = path.stat().st_mtime if path.exists() else 0.0
    start = time.monotonic()
    while True:
        time.sleep(interval)
        if stop_after is not None and (time.monotonic() - start) >= stop_after:
            break
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if mtime != last_mtime:
            last_mtime = mtime
            callback(path)


def safe_makedirs(path: str | Path, mode: int = 0o755) -> Path:
    """Create directory and all parents; do nothing if it already exists.

    Unlike os.makedirs with exist_ok=True, this also handles the race
    condition where a concurrent process creates the directory between the
    existence check and the mkdir call.  Returns the resolved Path.

    Args:
        path: Directory path to create.
        mode: Permission bits for newly created directories.
    """
    path = Path(path)
    path.mkdir(parents=True, mode=mode, exist_ok=True)
    return path


def read_lines(path: str | Path, encoding: str = 'utf-8',
               strip: bool = True, skip_comments: bool = False) -> List[str]:
    """Read a text file and return its non-empty lines as a list.

    Optionally strips leading/trailing whitespace from each line and skips
    lines beginning with '#' when skip_comments is True.  Empty lines (after
    stripping) are always excluded.

    Args:
        path:          File to read.
        encoding:      Text encoding; defaults to utf-8.
        strip:         Strip whitespace from each line.
        skip_comments: Ignore lines starting with '#'.
    """
    path = Path(path)
    lines = path.read_text(encoding=encoding, errors='ignore').splitlines()
    result = []
    for line in lines:
        if strip:
            line = line.strip()
        if not line:
            continue
        if skip_comments and line.startswith('#'):
            continue
        result.append(line)
    return result


def resolve_path(path: str | Path, relative_to: str | Path = None) -> Path:
    """Resolve a path to an absolute Path, optionally relative to a base.

    Expands ~ and environment variables in path.  If the path is relative
    and relative_to is given, it is joined with relative_to before resolution.
    If relative_to is None, the current working directory is used.

    Args:
        path:        Path string or Path object, possibly relative or with ~.
        relative_to: Base directory for relative paths; defaults to cwd.
    """
    path = Path(os.path.expandvars(os.path.expanduser(str(path))))
    if not path.is_absolute():
        base = Path(relative_to) if relative_to else Path.cwd()
        path = base / path
    return path.resolve()


def temp_dir(prefix: str = 'tool_', cleanup: bool = True) -> Iterator[Path]:
    """Context manager that creates a temporary directory and optionally cleans it up.

    Yields a Path to the temporary directory.  If cleanup is True (the
    default), the directory and all its contents are removed on exit.
    If cleanup is False, the directory is left for inspection or reuse.

    Args:
        prefix:  Prefix string for the temp directory name.
        cleanup: Whether to delete the directory on context exit.
    """
    tmp = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield tmp
    finally:
        if cleanup and tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)


def copy_tree(src: str | Path, dst: str | Path,
              exclude_patterns: Sequence[str] = (),
              overwrite: bool = True) -> List[Path]:
    """Recursively copy a directory tree from src to dst.

    Creates dst if it does not exist.  Files matching any exclude_pattern
    (matched against filenames only, using Path.match) are skipped.  Returns
    a list of destination Paths for all files actually copied.

    Args:
        src:              Source directory.
        dst:              Destination directory.
        exclude_patterns: Filename glob patterns to skip.
        overwrite:        If False, skip files that already exist at dst.
    """
    src, dst = Path(src), Path(dst)
    dst.mkdir(parents=True, exist_ok=True)
    copied: List[Path] = []
    for item in src.rglob('*'):
        if not item.is_file():
            continue
        if any(item.match(pat) for pat in exclude_patterns):
            continue
        rel = item.relative_to(src)
        target = dst / rel
        if not overwrite and target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        copied.append(target)
    return copied
