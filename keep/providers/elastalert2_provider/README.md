# ElastAlert2 Provider

The ElastAlert2 Provider integrates Keep with [ElastAlert2](https://elastalert2.readthedocs.io/en/latest/), an alerting framework for Elasticsearch that detects anomalies, spikes, or patterns in your log data.

## Features

- **Receive real-time alerts** from ElastAlert2 via its `http_post` / `http_post2` alerter
- **Pull rule error status** from the ElastAlert2 REST API
- Automatic severity and timestamp mapping from alert payload fields

## How It Works

ElastAlert2 continuously queries Elasticsearch and triggers configured alerters when rules match. The Keep provider receives these via the **HTTP POST alerter**, which sends the matched document fields to Keep's webhook endpoint.

## Authentication

ElastAlert2 exposes an optional REST API when started with `--http-port`:

```bash
elastalert --config config.yaml --http-port 3030
```

If api key authentication is configured on the server, provide it in the `api_key` field.

## Configuration

| Field        | Required | Description                                                             |
|--------------|----------|-------------------------------------------------------------------------|
| `base_url`   | ✅ Yes   | ElastAlert2 REST server URL, e.g. `http://elastalert2:3030`             |
| `api_key`    | ❌ No    | Bearer token if ElastAlert2 authentication is enabled                   |
| `verify_ssl` | ❌ No    | Verify SSL certificate (default: `true`)                                |

## Setting up Webhooks

Add the following to your ElastAlert2 rule YAML file:

```yaml
# Rule type and Elasticsearch config
...

# Alert using HTTP POST to Keep
alert:
  - post2

http_post_url: "https://<your-keep-url>/alerts/event/elastalert2"
http_post_payload:
  alert_name: "%(rule_name)s"
  message: "%(message)s"
  num_hits: "%(num_hits)s"
  severity: "warning"
  "@timestamp": "@timestamp"
http_post_headers:
  Content-Type: "application/json"
```

Keep will automatically parse and store the incoming alert.

## Alert Field Mapping

| ElastAlert2 Field        | Keep Field      |
|--------------------------|-----------------|
| `alert_name`/`rule_name` | `name`          |
| `message`/`body`         | `description`   |
| `severity`/`priority`    | `severity`      |
| `@timestamp`             | `lastReceived`  |
| `num_hits`               | `num_hits`      |
| `_index`                 | `index`         |

## Severity Mapping

| ElastAlert2  | Keep Severity |
|--------------|---------------|
| critical / 1 | CRITICAL      |
| error/high/2 | HIGH          |
| warning / 3  | WARNING       |
| info / 4     | INFO          |
| debug/low    | LOW           |

## References

- [ElastAlert2 Documentation](https://elastalert2.readthedocs.io/en/latest/)
- [HTTP POST Alerter](https://elastalert2.readthedocs.io/en/latest/alerts.html#http-post)
- [ElastAlert2 REST API](https://elastalert2.readthedocs.io/en/latest/elastalert_server.html)
