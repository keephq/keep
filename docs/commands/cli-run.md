
# cli run

Run the alert.

## Usage

```
Usage: cli run [OPTIONS]
```

## Options
* `alerts_file` (REQUIRED):
  * Type: <click.types.Path object at 0x101793b10>
  * Default: `none`
  * Usage: `--alerts-file
-f`

  The path to the alert yaml


* `providers_file`:
  * Type: <click.types.Path object at 0x101793b50>
  * Default: `providers.yaml`
  * Usage: `--providers-file
-f`

  The path to the providers yaml


* `api_key`:
  * Type: STRING
  * Default: `none`
  * Usage: `--api-key`

  The API key for keep's API


* `api_url`:
  * Type: STRING
  * Default: `https://s.keephq.dev`
  * Usage: `--api-url`

  The URL for keep's API


* `help`:
  * Type: BOOL
  * Default: `false`
  * Usage: `--help`

  Show this message and exit.



## CLI Help

```
Usage: cli run [OPTIONS]

  Run the alert.

Options:
  -f, --alerts-file PATH     The path to the alert yaml  [required]
  -f, --providers-file PATH  The path to the providers yaml
  --api-key TEXT             The API key for keep's API
  --api-url TEXT             The URL for keep's API
  --help                     Show this message and exit.
```
