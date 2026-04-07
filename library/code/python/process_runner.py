"""
process_runner.py — Subprocess execution helpers with streaming output,
timeout enforcement, pipe chaining, and structured result objects.

All functions use the subprocess module from the stdlib.  Streaming output
avoids buffering entire stdout/stderr in memory for long-running commands.
Timeout enforcement uses subprocess.communicate(timeout=) and kills the
process on expiry.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence


@dataclass
class ProcessResult:
    """Structured result from a completed subprocess.

    Attributes:
        returncode: Integer exit code of the process.
        stdout:     Captured standard output as a string.
        stderr:     Captured standard error as a string.
        command:    The command list that was executed.
        elapsed:    Wall-clock seconds the process ran, if measured.
    """
    returncode: int
    stdout: str
    stderr: str
    command: List[str]
    elapsed: float = 0.0

    @property
    def ok(self) -> bool:
        """True if the process exited with code 0."""
        return self.returncode == 0

    def check(self) -> 'ProcessResult':
        """Raise RuntimeError if returncode is non-zero, else return self."""
        if not self.ok:
            msg = f'command failed (exit {self.returncode}): {" ".join(self.command)}'
            if self.stderr:
                msg += f'\n{self.stderr.strip()}'
            raise RuntimeError(msg)
        return self


def run_command(cmd: Sequence[str], cwd: str = None, env: Dict[str, str] = None,
                input: str = None, encoding: str = 'utf-8') -> ProcessResult:
    """Run a command and capture its stdout and stderr as strings.

    Blocks until the command completes.  Does not stream output.  Use
    stream_output() when you need live output.  The command is passed as a
    sequence to avoid shell injection; use shell=False (the default).

    Args:
        cmd:      Command and arguments as a list of strings.
        cwd:      Working directory for the subprocess; defaults to current.
        env:      Environment variables dict; None inherits the parent env.
        input:    String to write to stdin; None means no stdin.
        encoding: Encoding for stdout/stderr decoding.
    """
    import time
    start = time.monotonic()
    result = subprocess.run(
        list(cmd),
        cwd=cwd,
        env=env,
        input=input,
        capture_output=True,
        text=True,
        encoding=encoding,
        errors='replace',
    )
    elapsed = time.monotonic() - start
    return ProcessResult(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        command=list(cmd),
        elapsed=elapsed,
    )


def stream_output(cmd: Sequence[str], cwd: str = None, env: Dict[str, str] = None,
                  prefix: str = '', stream=None) -> int:
    """Run a command and stream its stdout line-by-line to stream.

    Stderr is merged into stdout.  Each line is printed as it arrives, making
    this suitable for long-running builds or installs.  Returns the integer
    exit code.  Blocks until the process completes.

    Args:
        cmd:    Command and arguments as a list of strings.
        cwd:    Working directory; defaults to current.
        env:    Environment variables; None inherits parent env.
        prefix: String prepended to each output line.
        stream: Output stream; defaults to sys.stdout.
    """
    stream = stream or sys.stdout
    proc = subprocess.Popen(
        list(cmd),
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    for line in proc.stdout:
        stream.write(prefix + line)
        stream.flush()
    proc.wait()
    return proc.returncode


def run_with_timeout(cmd: Sequence[str], timeout: float,
                     cwd: str = None, env: Dict[str, str] = None) -> ProcessResult:
    """Run a command with a wall-clock timeout, killing it on expiry.

    Uses communicate(timeout=) and kills the process on TimeoutExpired.
    The ProcessResult's returncode is -9 if the process was killed by timeout.
    Stderr and stdout are captured even when the process is killed.

    Args:
        cmd:     Command and arguments as a list of strings.
        timeout: Maximum seconds to wait before killing the process.
        cwd:     Working directory; defaults to current.
        env:     Environment variables; None inherits parent env.
    """
    import time
    start = time.monotonic()
    proc = subprocess.Popen(
        list(cmd),
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        returncode = proc.returncode
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        returncode = -9
    elapsed = time.monotonic() - start
    return ProcessResult(
        returncode=returncode,
        stdout=stdout or '',
        stderr=stderr or '',
        command=list(cmd),
        elapsed=elapsed,
    )


def check_executable(name: str) -> Optional[str]:
    """Return the full path of an executable, or None if it is not found.

    Searches PATH using shutil.which.  Useful for pre-flight checks before
    invoking external tools like git, docker, or make.

    Args:
        name: Executable name to search for (e.g. 'git', 'python3').
    """
    import shutil
    return shutil.which(name)


def pipe_commands(pipeline: Sequence[Sequence[str]],
                  cwd: str = None, env: Dict[str, str] = None,
                  input: str = None) -> ProcessResult:
    """Run a pipeline of commands, piping stdout of each into stdin of the next.

    Equivalent to shell: cmd1 | cmd2 | cmd3.  Returns the result of the last
    command.  If any intermediate command fails, its stderr is included in
    the returned result's stderr.  The pipeline must have at least one command.

    Args:
        pipeline: Ordered list of commands; each is a list of strings.
        cwd:      Working directory applied to all commands.
        env:      Environment variables applied to all commands.
        input:    String written to stdin of the first command.
    """
    pipeline = [list(cmd) for cmd in pipeline]
    procs = []
    for i, cmd in enumerate(pipeline):
        stdin = subprocess.PIPE if i == 0 else procs[-1].stdout
        proc = subprocess.Popen(
            cmd, cwd=cwd, env=env,
            stdin=stdin,
            stdout=subprocess.PIPE if i < len(pipeline) - 1 else subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace',
        )
        procs.append(proc)
    stdout, stderr = procs[-1].communicate(input=input if len(procs) == 1 else None)
    for proc in procs[:-1]:
        proc.wait()
    return ProcessResult(
        returncode=procs[-1].returncode,
        stdout=stdout or '',
        stderr=stderr or '',
        command=pipeline[-1],
    )


def capture_output(cmd: Sequence[str], cwd: str = None,
                   env: Dict[str, str] = None) -> str:
    """Run a command and return its stdout as a stripped string.

    Convenience wrapper around run_command for the common case of capturing
    a single line of output (e.g. a version string or file path).  Raises
    RuntimeError if the command exits non-zero.

    Args:
        cmd: Command and arguments.
        cwd: Working directory.
        env: Environment variables.
    """
    result = run_command(cmd, cwd=cwd, env=env)
    result.check()
    return result.stdout.strip()
