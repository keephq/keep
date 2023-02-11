
# cli

Run Keep CLI.

## Usage

```
Usage: cli [OPTIONS] COMMAND [ARGS]...
```

## Options
* `verbose`:
  * Type: IntRange(0, None)
  * Default: `0`
  * Usage: `--verbose
-v`

  Enable verbose output.


* `keep_config`:
  * Type: STRING
  * Default: `keep.yaml`
  * Usage: `--keep-config
-c`

  The path to the keep config file


* `help`:
  * Type: BOOL
  * Default: `false`
  * Usage: `--help`

  Show this message and exit.



## CLI Help

```
Usage: cli [OPTIONS] COMMAND [ARGS]...

  Run Keep CLI.

Options:
  -v, --verbose           Enable verbose output.
  -c, --keep-config TEXT  The path to the keep config file
  --help                  Show this message and exit.

Commands:
  config   Set keep configuration.
  init     Set the config.
  run      Run the alert.
  version  Get the library version.
```
