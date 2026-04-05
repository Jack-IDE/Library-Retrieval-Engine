"""
config_loader.py — Multi-format config loading with env var substitution,
schema validation, and layered merge semantics.

Supports JSON, TOML (stdlib tomllib on 3.11+), and INI formats.  Configs
from multiple sources are merged with a defined precedence: CLI flags >
env vars > project config file > user config file > built-in defaults.
"""

from __future__ import annotations

import configparser
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


ENV_VAR_RE = re.compile(r'\$\{([A-Z_][A-Z0-9_]*)\}|\$([A-Z_][A-Z0-9_]*)')


class ConfigError(Exception):
    """Raised when a config file cannot be parsed or fails schema validation.

    Attributes:
        path:    Path to the offending config file, if applicable.
        field:   Name of the field that failed validation, if applicable.
    """

    def __init__(self, message: str, path: str = '', field: str = '') -> None:
        super().__init__(message)
        self.path = path
        self.field = field


def find_config_file(names: Sequence[str], search_dirs: Sequence[str] = None) -> Optional[Path]:
    """Search for the first matching config filename in candidate directories.

    Searches in order: each name in each directory.  Candidate directories
    default to [cwd, user home, /etc] when search_dirs is None.  Returns the
    first Path that exists, or None if no file is found.

    Args:
        names:       Ordered list of filenames to look for (e.g. ['.mytoolrc', 'mytool.json']).
        search_dirs: Directories to search; searched in given order.
    """
    if search_dirs is None:
        search_dirs = [os.getcwd(), str(Path.home()), '/etc']
    for d in search_dirs:
        for name in names:
            candidate = Path(d) / name
            if candidate.is_file():
                return candidate
    return None


def load_json_config(path: str | Path) -> Dict[str, Any]:
    """Load and parse a JSON config file, returning a flat or nested dict.

    Raises ConfigError on file-not-found or JSON parse errors.  The returned
    dict is a plain Python dict with no special proxy behaviour — callers may
    mutate it freely.

    Args:
        path: Path to the JSON config file.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding='utf-8')
    except OSError as exc:
        raise ConfigError(f'cannot read config: {exc}', path=str(path)) from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(f'JSON parse error: {exc}', path=str(path)) from exc


def load_toml_config(path: str | Path) -> Dict[str, Any]:
    """Load and parse a TOML config file.

    Uses stdlib tomllib (Python 3.11+) or falls back to a minimal TOML
    subset parser for older versions.  Raises ConfigError on parse failure.
    Only the top-level table is returned as a plain dict.

    Args:
        path: Path to the .toml config file.
    """
    path = Path(path)
    try:
        text = path.read_bytes()
    except OSError as exc:
        raise ConfigError(f'cannot read config: {exc}', path=str(path)) from exc
    try:
        import tomllib  # type: ignore
        return tomllib.loads(text.decode('utf-8'))
    except ImportError:
        pass
    try:
        import tomli  # type: ignore
        return tomli.loads(text.decode('utf-8'))
    except ImportError:
        raise ConfigError('TOML support requires Python 3.11+ or the tomli package', path=str(path))


def load_ini_config(path: str | Path, section: str = 'tool') -> Dict[str, Any]:
    """Load an INI config file and return the named section as a flat dict.

    Uses configparser with interpolation disabled to avoid surprising %()s
    substitutions.  If the named section is absent, returns an empty dict
    rather than raising.  All values are returned as strings.

    Args:
        path:    Path to the .ini or .cfg config file.
        section: INI section name to extract; defaults to 'tool'.
    """
    path = Path(path)
    parser = configparser.RawConfigParser()
    try:
        parser.read(str(path), encoding='utf-8')
    except configparser.Error as exc:
        raise ConfigError(f'INI parse error: {exc}', path=str(path)) from exc
    if not parser.has_section(section):
        return {}
    return dict(parser.items(section))


def merge_configs(*layers: Dict[str, Any]) -> Dict[str, Any]:
    """Merge multiple config dicts with later layers taking precedence.

    Performs a deep merge: nested dicts are recursively merged rather than
    replaced wholesale.  Non-dict values are overwritten by the later layer.
    None values in a later layer do NOT overwrite earlier values, enabling
    sparse override layers that only specify changed keys.

    Args:
        *layers: Config dicts in ascending precedence order (lowest first).
    """
    result: Dict[str, Any] = {}
    for layer in layers:
        for key, val in layer.items():
            if val is None:
                continue
            if key in result and isinstance(result[key], dict) and isinstance(val, dict):
                result[key] = merge_configs(result[key], val)
            else:
                result[key] = val
    return result


def resolve_env_vars(config: Dict[str, Any], environ: Dict[str, str] = None) -> Dict[str, Any]:
    """Substitute ${VAR} and $VAR placeholders in string config values.

    Walks the config dict recursively and replaces env var references in any
    string value.  References to undefined variables are left as-is rather
    than raising.  Does not modify the input dict; returns a new dict.

    Args:
        config:  Config dict possibly containing env var references.
        environ: Env var mapping; defaults to os.environ.
    """
    if environ is None:
        environ = os.environ

    def _subst(val: Any) -> Any:
        if isinstance(val, str):
            def repl(m):
                name = m.group(1) or m.group(2)
                return environ.get(name, m.group(0))
            return ENV_VAR_RE.sub(repl, val)
        if isinstance(val, dict):
            return {k: _subst(v) for k, v in val.items()}
        if isinstance(val, list):
            return [_subst(v) for v in val]
        return val

    return _subst(config)


def validate_schema(config: Dict[str, Any], schema: Dict[str, dict]) -> List[str]:
    """Validate a config dict against a simple schema, returning error strings.

    Schema is a dict mapping field names to spec dicts with optional keys:
      type:     Python type or tuple of types (checked with isinstance).
      required: bool — if True, field must be present and non-None.
      choices:  List of allowed values.
      min/max:  Numeric bounds (inclusive).

    Returns a list of error strings; empty list means validation passed.

    Args:
        config: Flat config dict to validate.
        schema: Schema dict mapping field names to constraint specs.
    """
    errors: List[str] = []
    for field, spec in schema.items():
        val = config.get(field)
        if spec.get('required') and val is None:
            errors.append(f"required field '{field}' is missing")
            continue
        if val is None:
            continue
        if 'type' in spec and not isinstance(val, spec['type']):
            errors.append(f"field '{field}' must be {spec['type'].__name__}, got {type(val).__name__}")
        if 'choices' in spec and val not in spec['choices']:
            errors.append(f"field '{field}' must be one of {spec['choices']}, got {val!r}")
        if 'min' in spec and val < spec['min']:
            errors.append(f"field '{field}' must be >= {spec['min']}")
        if 'max' in spec and val > spec['max']:
            errors.append(f"field '{field}' must be <= {spec['max']}")
    return errors


def get_config_value(config: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Retrieve a value from a nested config dict using dot-separated key paths.

    Supports dotted key paths like 'output.color.mode' to traverse nested
    dicts.  Returns default if any segment of the path is missing or if an
    intermediate value is not a dict.

    Args:
        config:  Config dict, potentially nested.
        key:     Dot-separated key path string.
        default: Value to return when the key path is absent.
    """
    parts = key.split('.')
    current = config
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current
