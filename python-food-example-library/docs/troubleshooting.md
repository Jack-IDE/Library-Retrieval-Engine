# Troubleshooting

## Common Errors

**"required field 'output.dir' is missing"** — The config validation failed
because no output directory was configured.  Add `"output": {"dir": "dist"}`
to your .mytoolrc file, or pass --output-dir dist on the command line.

**"unknown command 'xyz'"** — The subcommand name was not found in the
registry.  Run `mytool help` for a list of valid commands.  If the command
comes from a plugin, ensure the plugin is installed and not excluded by
the plugins.exclude config key.

**"cannot import plugin 'mytool_xyz'"** — The plugin package is named in
the config but is not importable.  Check that the package is installed in
the same Python environment as the tool (pip show mytool_xyz should show
a version).  If you are using a virtual environment, confirm it is activated.

**"vocab mismatch"** (ranker warning) — This applies to the internal search
index used by the help and search commands.  Re-run `mytool index rebuild`
to regenerate the index against the current vocab.

**"JSON parse error"** in config — The config file contains invalid JSON.
Common causes are trailing commas (not valid in JSON), unquoted keys, or
Windows line endings in files edited with Notepad.  Use a JSON validator
or switch to TOML format which allows comments and is more forgiving.

## Debugging Config Loading

Run any command with --verbose to see which config files were found and the
order they were loaded.  At debug log level, the fully merged config is
printed before command dispatch, which makes it easy to verify that env
var overrides and multi-layer merges resolved as expected.

To print only the resolved config without running a command, use:

```
mytool config dump
```

This prints the merged config as JSON to stdout and exits.  Pass --format json
if you want to pipe it to jq for filtering.

## Plugin Load Failures

By default, plugin load failures are warnings: the plugin is skipped and the
tool continues.  Set strict_plugins = true in your config or pass
--strict-plugins to make any plugin load failure a fatal error.

To list all discovered and loaded plugins with their metadata, run:

```
mytool plugins list
```

Plugins that failed to load appear in the list with a failed status and
the error message.  The --verbose flag adds the full traceback.

## File Permission Errors

Atomic writes require write permission on the directory containing the target
file (not just the file itself), because the write-temp-then-rename strategy
creates a temporary file in the same directory.  If you see permission errors
on write, check the parent directory permissions rather than the file itself.

## Process Timeout Errors

Commands that invoke subprocesses respect the subprocess.timeout config key
(default 60 seconds).  If a subprocess exceeds the timeout, it is killed and
the command exits with code -9.  Increase the timeout for slow operations
like large dependency installs:

```json
{ "subprocess": { "timeout": 300 } }
```

## Getting More Help

Run `mytool help <command>` for command-specific argument documentation.
Set MYTOOL_LOG_LEVEL=debug for maximum verbosity.  File issues at the
project GitHub repository with the output of `mytool config dump` and the
full --verbose log attached.
