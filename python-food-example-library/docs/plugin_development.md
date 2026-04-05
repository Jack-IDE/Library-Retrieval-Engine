# Plugin Development

## Plugin Structure

A plugin is a Python module or package installable via pip.  The module name
must start with the tool's plugin prefix (mytool_) so the auto-discovery
mechanism finds it.  Alternatively, plugins can be loaded explicitly by path
using the --plugin flag or the plugins.paths config key.

Every plugin module must define a top-level METADATA dict with at least a
name key.  The name is used in log messages, error reports, and the plugin
list output.  Additional recommended metadata keys are version, author, and
description.

```python
METADATA = {
    'name': 'my-formatter',
    'version': '1.0.0',
    'author': 'Your Name',
    'description': 'Custom output formatter plugin',
}
```

## Hook Functions

Plugins interact with the tool through named hook functions.  Define any
subset of the supported hooks; you do not need to implement all of them.
Hook functions are called synchronously in plugin registration order.

The five supported hooks are on_startup, on_shutdown, before_command,
after_command, and on_error.

on_startup(config) is called once after all plugins are loaded and config
is fully resolved.  Use it to validate plugin-specific config and initialise
shared resources.

before_command(command, namespace) is called before a command handler runs.
Return a non-None value to short-circuit the command with that return code.

after_command(command, namespace, returncode) is called after a command
handler returns.  Use it for cleanup, metrics emission, or post-processing.

on_error(command, exception) is called when a command raises an unhandled
exception.  Return True to suppress the exception; False or None to re-raise.

on_shutdown(config) is called once at process exit, even if a command failed.

## Plugin Configuration

Plugins declare their config schema by defining a CONFIG_SCHEMA dict at
module level.  The tool merges plugin schemas with its own core schema at
startup and validates the entire merged config in one pass.

Plugin config keys live under a plugins.<name> namespace in the config file
to avoid collisions with core keys.  Inside the plugin, retrieve config using
the config argument passed to hook functions.

```python
CONFIG_SCHEMA = {
    'max_width': {'type': int, 'default': 80},
    'style':     {'type': str, 'choices': ['compact', 'verbose'], 'default': 'compact'},
}
```

## Error Handling in Hooks

If a hook function raises an exception, the registry catches it, records an
error message, and continues calling remaining hooks for that event.  A single
misbehaving plugin does not block other plugins or the command itself.

The exception is logged at debug level with a full traceback.  At warning
level, only the plugin name and exception message are shown.  Plugin authors
should prefer to handle expected error conditions inside the hook and return
gracefully rather than raising.

## Testing Plugins

Load a plugin under development directly from a local path using the
--plugin-path flag:

```
mytool --plugin-path ./my_plugin.py build
```

The plugin registry's fire_hook method can be called in unit tests by
constructing a registry, calling load_plugin_from_path, and then calling
fire_hook with test arguments to assert on the return values.

Use the validate_plugin_interface function to check your METADATA and hook
signatures before running full integration tests.
