
# cli run

Run a workflow.

## Usage

```
Usage: cli run [OPTIONS]
```

## Options
* `alerts_directory`:
  * Type: <click.types.Path object at 0x11c1a5e90>
  * Default: `none`
  * Usage: `--alerts-directory
--alerts-file
-af`

  The path to the alert yaml/alerts directory


* `alert_url`:
  * Type: STRING
  * Default: `none`
  * Usage: `--alert-url
-au`

  A url that can be used to download an alert yaml NOTE: This argument is mutually exclusive with alerts_directory


* `interval`:
  * Type: INT
  * Default: `0`
  * Usage: `--interval
-i`

  When interval is set, Keep will run the alert every INTERVAL seconds


* `providers_file`:
  * Type: <click.types.Path object at 0x10afd52d0>
  * Default: `providers.yaml`
  * Usage: `--providers-file
-p`

  The path to the providers yaml


* `tenant_id`:
  * Type: STRING
  * Default: `keep`
  * Usage: `--tenant-id
-t`

  The tenant id


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

  Run a workflow.

Options:
  -af, --alerts-directory, --alerts-file PATH
                                  The path to the alert yaml/alerts directory
  -au, --alert-url TEXT           A url that can be used to download an alert
                                  yaml NOTE: This argument is mutually
                                  exclusive with alerts_directory

  -i, --interval INTEGER          When interval is set, Keep will run the
                                  alert every INTERVAL seconds

  -p, --providers-file PATH       The path to the providers yaml
  -t, --tenant-id TEXT            The tenant id
  --api-key TEXT                  The API key for keep's API
  --api-url TEXT                  The URL for keep's API
  --help                          Show this message and exit.
```
