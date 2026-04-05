"""
cli_framework.py — Lightweight command dispatch and argument parsing framework.

Provides a CommandRegistry for registering subcommands, middleware support for
cross-cutting concerns (logging, auth, dry-run), and a top-level run_cli entry
point that ties argument parsing to command dispatch.
"""

from __future__ import annotations

import sys
import textwrap
from typing import Any, Callable, Dict, List, Optional, Sequence


class CommandRegistry:
    """Central registry mapping command names to handler functions.

    Each handler is a callable that receives a namespace of parsed arguments
    and returns an integer exit code.  Commands can declare required and
    optional argument specs that the registry uses to build help text and
    validate inputs before dispatch.

    Usage:
        registry = CommandRegistry(prog='mytool')
        registry.register('build', build_handler, args=[...])
        registry.dispatch(['build', '--output', 'dist'])
    """

    def __init__(self, prog: str, description: str = '') -> None:
        self.prog = prog
        self.description = description
        self._commands: Dict[str, dict] = {}
        self._middleware: List[Callable] = []

    def register(self, name: str, handler: Callable, args: list = None,
                 help: str = '') -> None:
        """Register a command handler under the given name.

        Args:
            name:    Subcommand name used on the command line.
            handler: Callable(namespace) -> int.
            args:    List of arg spec dicts with keys: name, type, default,
                     required, help.
            help:    One-line description shown in top-level help.
        """
        self._commands[name] = {
            'handler': handler,
            'args': args or [],
            'help': help,
        }

    def dispatch(self, argv: Sequence[str]) -> int:
        """Parse argv and invoke the matching command handler.

        Returns the handler's integer exit code, or 1 on parse error.
        Middleware chain is applied before the handler is called.
        """
        if not argv or argv[0] in ('-h', '--help'):
            print(build_help_text(self.prog, self.description, self._commands))
            return 0
        name = argv[0]
        if name not in self._commands:
            print(format_error(f"unknown command '{name}'", self.prog), file=sys.stderr)
            return 1
        spec = self._commands[name]
        namespace, err = parse_args(argv[1:], spec['args'])
        if err:
            print(format_error(err, self.prog), file=sys.stderr)
            return 1
        err = validate_required_args(namespace, spec['args'])
        if err:
            print(format_error(err, self.prog), file=sys.stderr)
            return 1
        handler = apply_middleware(spec['handler'], self._middleware)
        return handler(namespace)


class Middleware:
    """Base class for CLI middleware that wraps command handlers.

    Subclass and override __call__ to intercept handler execution.
    The next callable in the chain is passed as the second argument.

    Example middleware uses: timing, dry-run guards, credential injection,
    structured logging, and global error handling.
    """

    def __call__(self, handler: Callable, namespace: Any) -> int:
        return handler(namespace)


def parse_args(argv: Sequence[str], arg_specs: list) -> tuple:
    """Parse a flat argv list against a list of arg spec dicts.

    Returns (namespace_dict, error_string).  error_string is None on success.
    Supports --flag VALUE and --flag=VALUE forms, boolean flags, and
    positional arguments declared with positional=True in the spec.

    Args:
        argv:      Remaining argv after the subcommand name is removed.
        arg_specs: List of dicts with keys: name, type, default, required,
                   positional, help.
    """
    namespace: Dict[str, Any] = {}
    for spec in arg_specs:
        namespace[spec['name']] = spec.get('default')
    positionals = [s for s in arg_specs if s.get('positional')]
    pos_idx = 0
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok.startswith('--'):
            key, _, val = tok[2:].partition('=')
            key = key.replace('-', '_')
            if not val:
                if i + 1 < len(argv) and not argv[i + 1].startswith('--'):
                    val = argv[i + 1]
                    i += 1
                else:
                    val = 'true'
            namespace[key] = val
        elif pos_idx < len(positionals):
            namespace[positionals[pos_idx]['name']] = tok
            pos_idx += 1
        else:
            return namespace, f"unexpected argument: {tok}"
        i += 1
    return namespace, None


def build_help_text(prog: str, description: str, commands: dict) -> str:
    """Build a formatted help string listing all registered commands.

    Each command is shown with its one-line help text, aligned in two columns.
    The output follows standard Unix help conventions: usage line, blank line,
    description, blank line, commands section.

    Args:
        prog:        Program name for the usage line.
        description: Short description of the tool.
        commands:    Dict mapping command names to their spec dicts.
    """
    lines = [f'Usage: {prog} <command> [options]', '']
    if description:
        lines += [description, '']
    lines.append('Commands:')
    width = max((len(n) for n in commands), default=8) + 2
    for name, spec in sorted(commands.items()):
        lines.append(f'  {name:<{width}}{spec.get("help", "")}')
    return '\n'.join(lines)


def validate_required_args(namespace: dict, arg_specs: list) -> Optional[str]:
    """Return an error string if any required argument is missing or None.

    Checks each spec with required=True against the namespace.  Returns None
    when all required args are present, or a descriptive error string for the
    first missing argument found.
    """
    for spec in arg_specs:
        if spec.get('required') and namespace.get(spec['name']) is None:
            return f"missing required argument: --{spec['name'].replace('_', '-')}"
    return None


def apply_middleware(handler: Callable, middleware: List[Callable]) -> Callable:
    """Wrap a handler with the middleware chain in registration order.

    Middleware is applied so that the first registered middleware is the
    outermost wrapper.  Each middleware receives (handler, namespace) and
    is responsible for calling the inner handler or short-circuiting.

    Args:
        handler:    Base command handler callable.
        middleware: Ordered list of Middleware instances or callables.
    """
    wrapped = handler
    for mw in reversed(middleware):
        outer = wrapped

        def make_wrapper(mw, inner):
            def wrapper(ns):
                return mw(inner, ns)
            return wrapper

        wrapped = make_wrapper(mw, outer)
    return wrapped


def run_cli(registry: CommandRegistry, argv: Sequence[str] = None) -> None:
    """Top-level entry point: parse argv and exit with the command's return code.

    Calls registry.dispatch and raises SystemExit with the returned integer.
    Catches KeyboardInterrupt and exits cleanly with code 130.

    Args:
        registry: Configured CommandRegistry with all commands registered.
        argv:     Argument list; defaults to sys.argv[1:] if None.
    """
    if argv is None:
        argv = sys.argv[1:]
    try:
        code = registry.dispatch(argv)
    except KeyboardInterrupt:
        print('', file=sys.stderr)
        sys.exit(130)
    sys.exit(code)


def format_error(message: str, prog: str = '') -> str:
    """Format an error message with optional program prefix.

    Returns a string suitable for writing to stderr.  If prog is given,
    the message is prefixed with 'prog: error: message'.  Otherwise just
    'error: message'.  Does not include a trailing newline.
    """
    prefix = f'{prog}: ' if prog else ''
    return f'{prefix}error: {message}'
