# Getting Started

## Installation

Install the tool from PyPI using pip.  Python 3.10 or newer is required.
The core package has no mandatory third-party dependencies; all functionality
uses the Python standard library.  Optional TOML config support requires
Python 3.11 or the tomli package.

```
pip install mytool
```

To verify the installation worked, run the help command and confirm the
version string appears:

```
mytool --help
```

If you need TOML config file support on Python 3.10, install the optional
dependency:

```
pip install mytool[toml]
```

## Quick Start

The minimal workflow is: create a config file, run a build, and query output.
Create a file named `.mytoolrc` in your project root with the following JSON:

```json
{
  "output": { "color": true, "format": "text" },
  "log_level": "info"
}
```

Then run the build command from your project directory:

```
mytool build --target dist/
```

The tool discovers `.mytoolrc` automatically by walking up from the current
directory.  You can override the config file path explicitly with --config.

## Basic Commands

The four most commonly used commands are build, check, run, and clean.
Each accepts --help for full argument documentation.

The build command compiles or packages the project into the output directory.
The check command runs validation without producing output (useful in CI).
The run command executes the built artifact with any arguments you provide.
The clean command removes generated files under the output directory.

All commands accept --verbose for detailed logging and --dry-run to preview
actions without executing them.  Dry-run mode is especially useful before
running clean, which is irreversible.

## Project Layout

A typical project directory looks like this after initialization:

```
my-project/
  .mytoolrc          # Project config (JSON or TOML)
  src/               # Source files
  tests/             # Test files
  dist/              # Build output (generated, gitignored)
  plugins/           # Local plugin directory (optional)
```

The tool never writes outside the project root unless you explicitly set an
absolute output path in the config.  Generated directories are listed in
.gitignore by the init command.

## Environment Variables

Any config value can be overridden with an environment variable prefixed with
MYTOOL_.  The variable name is the uppercased config key path with dots
replaced by underscores.  For example, MYTOOL_OUTPUT_FORMAT=json overrides
output.format in the config file.

Environment variable overrides apply on top of all config file layers and
below command-line flags in the precedence order.

## Getting Help

Run `mytool help <command>` for detailed documentation on any subcommand.
The project README on GitHub covers advanced topics including plugin
development, CI integration, and performance tuning.
