# Output and Formatting

## Output Formats

The tool supports three output formats selectable with --format or the
output.format config key: text, json, and quiet.

Text format (the default) produces human-readable output with aligned tables,
tree views, and color highlighting.  It is optimised for interactive use in
a terminal and should not be parsed by scripts because its layout may change
between versions.

JSON format emits one JSON object per logical result, one per line (NDJSON).
Each object contains a type field identifying the record kind and a data field
with the payload.  JSON format is stable across patch versions and is the
recommended format for scripted consumers and CI pipelines.

Quiet format suppresses all output except errors and the final exit code.
It is useful when the calling script only cares whether the command succeeded
and does not want to parse any output.

## Color Output

Color is automatically enabled when stdout is a TTY and the TERM environment
variable is not set to "dumb".  Color is automatically disabled when stdout
is piped or redirected.

Two environment variables control color regardless of TTY detection.
NO_COLOR (https://no-color.org) disables color when set to any non-empty
value.  FORCE_COLOR enables color even when stdout is not a TTY, which is
useful when a CI system captures colorized output for display in a web UI.
FORCE_COLOR takes precedence over NO_COLOR if both are set.

## Table Output

Tabular data is rendered with auto-sized columns padded to the widest value
in each column.  Column headers are separated from data rows by a line of
dashes.  Long cell values are truncated with an ellipsis to prevent wrapping.

When --format json is active, tables are emitted as arrays of objects where
each key corresponds to a column header.  The JSON representation always
includes the full untruncated value regardless of terminal width.

## Progress Bars

Long-running operations display a progress bar on stderr.  The bar shows
a filled/unfilled indicator, a percentage, the current and total item count,
elapsed time, and an ETA when the rate can be estimated.

Progress bars are automatically suppressed when stderr is not a TTY, when
NO_COLOR is set, or when --format quiet is active.  The ETA is recalculated
every update cycle using a simple linear rate estimate.

## Verbosity Levels

Four verbosity levels are available via --verbose / --quiet flags and the
log_level config key: error, warning, info, and debug.

At the default info level, the tool prints a one-line summary per major step.
At debug level, every file operation, config merge step, and plugin hook call
is logged with a timestamp.  Error and warning messages always appear
regardless of verbosity setting.  The --verbose flag is equivalent to
setting log_level to debug for the duration of the command.

## Redirecting and Piping Output

All user-facing messages go to stdout.  Log messages and progress bars go
to stderr.  This separation allows safe piping of tool output to downstream
commands without mixing log noise into the data stream.

For example, to pipe JSON output into jq:

```
mytool list --format json | jq '.data.name'
```

The tool flushes stdout after every logical record in JSON mode, so downstream
commands receive data incrementally rather than waiting for the tool to finish.
