# Configuration Guide

## Config File Formats

The tool supports three config file formats: JSON, TOML, and INI.  All three
formats express the same key/value structure.  JSON is the default and is
recommended for programmatic generation.  TOML is preferred for hand-edited
configs because it supports comments.  INI is supported for compatibility
with legacy project setups.

The tool auto-detects the format from the file extension: .json, .toml, .ini,
or .cfg.  Files without a recognised extension are attempted as JSON first,
then TOML.  The --config flag accepts any supported format explicitly.

## Config Search and Precedence

The tool applies configuration from multiple sources in a defined precedence
order, from lowest to highest: built-in defaults, user-level config file,
project config file, environment variables, and command-line flags.

The user-level config file lives at ~/.config/mytool/config.json on Linux
and macOS, and at %APPDATA%\mytool\config.json on Windows.  The project
config file is discovered by searching for .mytoolrc, mytool.json, or
mytool.toml starting from the current directory and walking up to the
filesystem root.  The first match wins.

Later layers override earlier ones on a per-key basis.  Nested dicts are
merged recursively, so you can override a single nested key without
repeating the entire parent structure.

## Environment Variable Substitution

String values in config files can reference environment variables using
${VAR_NAME} or $VAR_NAME syntax.  Substitution happens after the config
file is parsed and before schema validation runs.

For example, to use the CI-provided build number in your output path:

```json
{
  "output": {
    "dir": "dist/build-${CI_BUILD_NUMBER}"
  }
}
```

References to undefined variables are left as literal strings.  If you need
a literal dollar sign in a config value, write $$ to escape it.

## Schema and Validation

The config schema defines type constraints, required fields, and allowed
values for each key.  Validation runs at startup before any command executes.
Validation errors are reported as a list with the field name and the
constraint that was violated.

The required top-level fields are: output.dir (string) and log_level
(one of: debug, info, warning, error).  All other fields have defaults
and are optional.

Custom schema extensions for plugins are merged with the core schema at
startup.  A plugin can declare additional required fields that must be
present in the config when that plugin is active.

## Common Config Keys

The most frequently used config keys are listed below with their types and
default values.

output.dir (string, default "dist") sets the directory where build artifacts
are written.  output.format (string, default "text") controls output format:
text, json, or quiet.  output.color (bool, default true) enables ANSI color
in terminal output and is automatically disabled when stdout is not a TTY.

log_level (string, default "info") sets the minimum severity for log messages.
dry_run (bool, default false) previews all file-system operations without
executing them.  parallel (int, default 4) sets the number of worker threads
for parallel build steps.

## INI Format Example

INI configs must use a [tool] section for core settings.  Plugin config
goes in sections named [plugin.pluginname].

```ini
[tool]
log_level = info
output_dir = dist
output_format = text

[plugin.formatter]
style = compact
max_width = 120
```

Note that INI does not support nested dicts natively, so nested keys are
flattened with underscores (output_dir instead of output.dir).
