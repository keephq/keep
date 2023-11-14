
# alert list

List alerts.

## Usage

```
Usage: cli alert list [OPTIONS]
```

## Options
* `filter`:
  * Type: STRING
  * Default: `none`
  * Usage: `--filter
-f`

  Filter alerts based on specific attributes. E.g., --filter source=datadog


* `export`:
  * Type: <click.types.Path object at 0x11c1a7fd0>
  * Default: `none`
  * Usage: `--export`

  Export alerts to a specified JSON file.


* `help`:
  * Type: BOOL
  * Default: `false`
  * Usage: `--help`

  Show this message and exit.



## CLI Help

```
Usage: cli alert list [OPTIONS]

  List alerts.

Options:
  -f, --filter TEXT  Filter alerts based on specific attributes. E.g.,
                     --filter source=datadog

  --export PATH      Export alerts to a specified JSON file.
  --help             Show this message and exit.
```
