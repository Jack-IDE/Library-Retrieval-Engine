# Config Resolution Specification

## Layer Precedence

Config resolution applies five layers in ascending precedence order.  A value
at a higher layer always wins over the same key at a lower layer, with the
exception that None values never overwrite lower-layer values (sparse override
semantics).

Layer 1 (lowest): Built-in defaults defined in the tool source.  These are
always present and provide a valid baseline config so the tool can run without
any user config.

Layer 2: User-level config file, read from ~/.config/mytool/config.json or
the platform equivalent.  Shared across all projects on the machine.

Layer 3: Project config file, discovered by walking up from cwd.  Filenames
searched in order: .mytoolrc, mytool.json, mytool.toml, mytool.cfg.

Layer 4: Environment variables with the MYTOOL_ prefix.  The key path is
derived by lowercasing the suffix and replacing underscores with dots:
MYTOOL_OUTPUT_FORMAT maps to output.format.  Env var layer is applied after
all file layers are merged.

Layer 5 (highest): Command-line flags.  Only explicitly passed flags are
applied as an override layer; absent flags do not contribute None values
to the layer.

## Deep Merge Algorithm

The merge_configs function implements the deep merge algorithm used between
all layers.  Two dicts are merged by iterating the keys of the overlay dict.
For each key, if both the base and overlay values are dicts, they are merged
recursively.  Otherwise the overlay value replaces the base value.

None values in the overlay are skipped (they do not overwrite).  This allows
sparse overlay dicts where unset keys are represented as absent rather than
explicitly None, which is the natural representation for parsed command-line
flags where the user did not provide the flag.

List values are not merged: an overlay list entirely replaces a base list.
To append to a list defined in a lower layer, use the extend syntax in the
config file (a separate key like output.extra_flags that is appended by the
tool at config post-processing time).

## Schema Validation

Validation runs once after all layers are merged and env var substitution is
applied.  The schema is a flat dict mapping dotted key paths to constraint
specs.  Nested config is flattened to dot-separated paths for validation
purposes, then re-nested for use by the tool and plugins.

Validation collects all errors in one pass rather than stopping at the first
failure, so users see all problems at once.  Errors reference the full dotted
key path and the constraint that was violated.

Plugin schemas are merged with the core schema before validation runs.  A
plugin can mark a key as required, which will cause validation to fail if the
key is absent in the merged config, even if the core tool would not require it.

## Environment Variable Mapping

Env var names use the MYTOOL_ prefix followed by the uppercased key path with
dots replaced by underscores.  The reverse mapping (env var name to key path)
is performed before the env layer is applied to the merged config.

Type coercion for env vars follows the schema type for that key.  String env
vars are cast to int, float, or bool according to the schema.  For bool keys,
the strings 'true', '1', and 'yes' (case-insensitive) map to True; 'false',
'0', and 'no' map to False.  Invalid values for typed keys produce a
validation error at startup.
