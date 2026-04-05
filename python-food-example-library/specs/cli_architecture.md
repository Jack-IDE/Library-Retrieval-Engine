# CLI Architecture

## Command Dispatch Model

The tool uses a two-stage dispatch model: argument tokenization followed by
command-specific parsing.  The top-level parser consumes only the subcommand
name and global flags (--config, --verbose, --format, --dry-run).  Remaining
tokens are passed verbatim to the subcommand's own argument spec.

This design allows each subcommand to define its own argument grammar
independently of others, avoids global argument namespace collisions, and
makes it straightforward to add new commands without modifying the top-level
parser.

The CommandRegistry is the central broker.  It holds a mapping from command
names to handler functions and their argument specs.  At startup, all built-in
commands are registered before plugin discovery runs, so plugins can see and
potentially wrap built-in command handlers.

## Middleware Pipeline

Cross-cutting concerns are implemented as middleware rather than being baked
into individual command handlers.  Middleware is registered as a list of
callables on the CommandRegistry.  The registry wraps the handler in the
middleware chain at dispatch time, not at registration time.

The middleware chain is applied in reverse registration order so that the
first registered middleware is the outermost wrapper.  Each middleware
receives the inner handler and the parsed namespace and decides whether to
call through, short-circuit, or modify the namespace before calling through.

Built-in middleware includes: dry-run enforcement (prints actions without
executing file operations), timing (records wall-clock duration and logs it),
and error normalisation (catches RuntimeError and converts to exit code 1
with a formatted stderr message).

## Argument Parsing

The tool's argument parser intentionally avoids argparse to keep the
dependency footprint minimal and to give full control over error messages.
The parse_args function in cli_framework.py handles --flag VALUE,
--flag=VALUE, boolean flags, and positional arguments declared in each
command's arg spec.

Type coercion happens after parsing: string values from the argv list are
converted to int, float, bool, or Path according to the type field in the
arg spec.  Coercion errors produce a formatted error message pointing to
the specific argument.

Required arguments missing from the command line cause validate_required_args
to return an error string which dispatch prints to stderr before returning
exit code 1.  Optional arguments default to the value in the spec's default
field, which is None when not specified.

## Exit Code Conventions

Exit code 0 means success.  Exit code 1 means a general error (bad arguments,
config validation failure, command-reported failure).  Exit code 2 is reserved
for usage errors caught before a command handler runs.  Exit code 130 is used
when the user interrupts with Ctrl-C (matching shell conventions for SIGINT).

Plugin hook handlers that return a non-None integer from before_command cause
the command to exit with that code immediately, without running the handler
or the after_command hooks.

## Startup Sequence

The complete startup sequence is: parse global flags, load config layers and
merge them, resolve environment variable substitutions, validate the merged
config against the schema, discover and load plugins (firing on_startup for
each), then dispatch the subcommand through the middleware pipeline.

If config validation fails, the tool exits before loading any plugins.  This
ensures that plugins can trust the config they receive in on_startup is
fully valid.  Plugin load failures are collected and reported as warnings
unless the --strict-plugins flag is set, which makes any plugin load failure
a fatal error.
