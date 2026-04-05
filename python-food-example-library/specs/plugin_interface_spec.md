# Plugin Interface Specification

## Interface Contract

A conforming plugin module must satisfy the following contract.  Violations
are detected by validate_plugin_interface and reported as PluginError at
load time, before the plugin is added to the registry.

The module must define METADATA as a module-level dict.  METADATA must
contain a name key whose value is a non-empty string.  The name must be
unique across all loaded plugins; duplicate names cause a PluginError.

Any hook attribute on the module (on_startup, on_shutdown, before_command,
after_command, on_error) must be callable.  Defining a hook attribute as a
non-callable (e.g. a string or a class that is not instantiated) is an error.

Plugin modules must not execute side effects at import time.  Network
connections, file writes, and subprocess calls must happen inside hook
functions, not at module level.  This allows the registry to import plugins
for inspection (metadata listing, schema collection) without triggering
side effects.

## Hook Signatures

Each hook function has a defined signature.  Plugins must accept **kwargs
in addition to any declared positional parameters to remain compatible with
future hook arguments added by the tool.

on_startup(config: dict, **kwargs) -> None
before_command(command: str, namespace: dict, **kwargs) -> Optional[int]
after_command(command: str, namespace: dict, returncode: int, **kwargs) -> None
on_error(command: str, exception: Exception, **kwargs) -> Optional[bool]
on_shutdown(config: dict, **kwargs) -> None

Return values are only meaningful for before_command (int short-circuits
the command) and on_error (True suppresses re-raise).  All other hooks
must return None; non-None returns are ignored.

## Versioning and Compatibility

Plugin API versions are tracked by the tool_api_version key in METADATA.
Plugins that declare tool_api_version must specify the minimum tool version
they require.  The registry emits a warning when loading a plugin whose
required API version exceeds the running tool's version.

Plugins should declare the tool_api_version they were built against to allow
the tool to warn users when a plugin may be incompatible with an upgrade.
Omitting tool_api_version is allowed and produces no warning.
