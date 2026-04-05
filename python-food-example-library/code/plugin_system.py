"""
plugin_system.py — Dynamic plugin discovery, loading, and hook dispatch.

Plugins are Python modules or packages discovered by naming convention
(e.g. mytool_*) or explicit registration.  Each plugin declares a METADATA
dict and optionally implements hook functions that the registry calls at
defined lifecycle points: on_startup, on_shutdown, before_command,
after_command, on_error.
"""

from __future__ import annotations

import importlib
import importlib.util
import pkgutil
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence


HOOK_NAMES = ('on_startup', 'on_shutdown', 'before_command', 'after_command', 'on_error')


class PluginError(Exception):
    """Raised when a plugin cannot be loaded or fails interface validation.

    Attributes:
        plugin_name: Name of the plugin that caused the error.
    """

    def __init__(self, message: str, plugin_name: str = '') -> None:
        super().__init__(message)
        self.plugin_name = plugin_name


class PluginRegistry:
    """Registry that tracks loaded plugins and dispatches hook calls.

    Plugins are registered either by explicit load_plugin() calls or by
    running discover_plugins() to scan a namespace package prefix.  Hook
    methods are invoked in registration order.  Errors in individual plugin
    hooks are caught and reported rather than halting the entire dispatch.

    Usage:
        registry = PluginRegistry()
        registry.discover_plugins(prefix='mytool_')
        registry.fire_hook('on_startup', config=config)
    """

    def __init__(self) -> None:
        self._plugins: Dict[str, Any] = {}
        self._hooks: Dict[str, List[Callable]] = {h: [] for h in HOOK_NAMES}
        self._errors: List[str] = []

    def load_plugin(self, module_name: str) -> None:
        """Import a plugin module by name and register its hooks.

        The module must define a METADATA dict with at least a 'name' key.
        Optional hook functions (on_startup, before_command, etc.) are
        detected by name and registered automatically.

        Args:
            module_name: Fully qualified module name to import.
        """
        try:
            mod = importlib.import_module(module_name)
        except ImportError as exc:
            raise PluginError(f'cannot import plugin {module_name!r}: {exc}', module_name) from exc
        validate_plugin_interface(mod, module_name)
        name = mod.METADATA.get('name', module_name)
        self._plugins[name] = mod
        for hook in HOOK_NAMES:
            fn = getattr(mod, hook, None)
            if callable(fn):
                self._hooks[hook].append(fn)

    def load_plugin_from_path(self, path: str | Path, name: str = None) -> None:
        """Load a plugin from a filesystem path outside sys.path.

        Useful for loading plugins from user-specified directories without
        modifying sys.path globally.  The module name defaults to the file
        stem if name is not given.

        Args:
            path: Path to the .py plugin file.
            name: Module name to use; defaults to the file stem.
        """
        path = Path(path)
        name = name or path.stem
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise PluginError(f'cannot load plugin from {path}', name)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception as exc:
            del sys.modules[name]
            raise PluginError(f'error executing plugin {path}: {exc}', name) from exc
        validate_plugin_interface(mod, name)
        self._plugins[name] = mod
        for hook in HOOK_NAMES:
            fn = getattr(mod, hook, None)
            if callable(fn):
                self._hooks[hook].append(fn)

    def discover_plugins(self, prefix: str, path: Sequence[str] = None) -> List[str]:
        """Discover and load all installed packages matching a name prefix.

        Uses pkgutil.iter_modules to enumerate packages visible from path
        (defaults to sys.path).  Returns a list of successfully loaded plugin
        names.  Modules that fail to load are recorded in self._errors and
        skipped.

        Args:
            prefix: Module name prefix to match (e.g. 'mytool_').
            path:   Search path; defaults to sys.path.
        """
        loaded = []
        for finder, name, _ in pkgutil.iter_modules(path):
            if not name.startswith(prefix):
                continue
            try:
                self.load_plugin(name)
                loaded.append(name)
            except PluginError as exc:
                self._errors.append(str(exc))
        return loaded

    def fire_hook(self, hook_name: str, **kwargs: Any) -> List[Any]:
        """Invoke all registered handlers for a hook, returning their results.

        Handlers are called in registration order with the provided keyword
        arguments.  Exceptions from individual handlers are caught, stored in
        self._errors, and do not prevent remaining handlers from running.

        Args:
            hook_name: Name of the hook (e.g. 'on_startup', 'before_command').
            **kwargs:  Keyword arguments forwarded to each handler.
        """
        results = []
        for fn in self._hooks.get(hook_name, []):
            try:
                results.append(fn(**kwargs))
            except Exception as exc:
                self._errors.append(f'{hook_name} hook {fn.__module__} failed: {exc}')
        return results

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Return metadata dicts for all loaded plugins, sorted by name."""
        return [
            dict(mod.METADATA, name=name)
            for name, mod in sorted(self._plugins.items())
        ]


def validate_plugin_interface(module: Any, name: str) -> None:
    """Check that a module satisfies the minimum plugin interface contract.

    Requires METADATA to be a dict with a non-empty 'name' string.  Any
    defined hook functions are validated for callability.  Raises PluginError
    describing the first violation found.

    Args:
        module: Imported module object to validate.
        name:   Module name for use in error messages.
    """
    if not hasattr(module, 'METADATA') or not isinstance(module.METADATA, dict):
        raise PluginError(f"plugin {name!r} must define a METADATA dict", name)
    if not module.METADATA.get('name'):
        raise PluginError(f"plugin {name!r} METADATA must include a non-empty 'name' key", name)
    for hook in HOOK_NAMES:
        fn = getattr(module, hook, None)
        if fn is not None and not callable(fn):
            raise PluginError(f"plugin {name!r} attribute {hook!r} must be callable", name)


def register_hook(registry: PluginRegistry, hook_name: str,
                  fn: Callable) -> None:
    """Manually register a callable for a named hook outside the plugin system.

    Useful for registering hooks from the host application itself rather than
    from plugin modules.  The function is appended after any plugin-provided
    handlers for that hook.

    Args:
        registry:  PluginRegistry instance.
        hook_name: Hook name; must be one of HOOK_NAMES.
        fn:        Callable to register.
    """
    if hook_name not in HOOK_NAMES:
        raise ValueError(f'unknown hook {hook_name!r}; valid hooks: {HOOK_NAMES}')
    if not callable(fn):
        raise TypeError(f'hook handler must be callable, got {type(fn).__name__}')
    registry._hooks[hook_name].append(fn)
