# ElastAlert2 Provider

[ElastAlert2](https://github.com/jertel/elastalert2) is a framework for alerting on anomalies,
spikes, or other patterns in data stored in Elasticsearch and OpenSearch. Keep integrates as an
HTTP POST receiver using ElastAlert2's built-in `http_post` alerter.

## Overview

The Keep ElastAlert2 provider is a **webhook-only** provider — no credentials are needed on the
Keep side. ElastAlert2 sends alert payloads to Keep's webhook endpoint whenever a rule fires.

**Supported fields in each alert payload:**

| Field | Description |
|-------|-------------|
| `rule_name` | Name of the ElastAlert2 rule that fired |
| `alert_text` | Rendered human-readable alert message |
| `num_hits` | Number of matching Elasticsearch documents |
| `num_matches` | Number of rule trigger matches |
| `@timestamp` | Timestamp of the matched document |
| `log.level` / `level` / `severity` | Used for Keep severity mapping |
| `alert_priority` | Numeric priority (1=critical … 5=low) |
| Any other fields | Passed as alert labels for workflow use |

## Setup

### 1. Create an ElastAlert2 rule

In your ElastAlert2 rule file (e.g. `rules/high_error_rate.yaml`):

```yaml
name: HighErrorRate
type: frequency
index: logs-*
num_events: 50
timeframe:
  minutes: 5

filter:
  - query:
      match:
        log.level: "error"

alert:
  - post

# Keep webhook URL — set your actual Keep host and API key
http_post_url: "https://<your-keep-instance>/alerts/event/elastalert2?api_key=<your-api-key>"

# Include all matched document fields in the payload
http_post_all_values: true

# Optional: add static metadata fields to every alert
http_post_payload:
  environment: "production"
  team: "platform"
```

### 2. Restart ElastAlert2

```bash
elastalert --config config.yaml --rule rules/high_error_rate.yaml
```

### 3. Verify in Keep

Alerts should appear in the Keep Alerts feed with:
- **Name**: the `rule_name` from your rule
- **Description**: the rendered `alert_text` plus match count
- **Severity**: mapped from `log.level`, `level`, `severity`, or `alert_priority`

## Severity Mapping

| ElastAlert2 field value | Keep severity |
|------------------------|---------------|
| `critical`, `alert_priority=1` | CRITICAL |
| `error`, `high`, `alert_priority=2` | HIGH |
| `warning`, `warn`, `medium`, `alert_priority=3` | WARNING |
| `info`, `information`, `alert_priority=4` | INFO |
| `low`, `debug`, `alert_priority=5` | LOW |

If no recognizable severity field is present, the alert defaults to **INFO**.

## Example Workflow

```yaml
workflow:
  id: elastalert2-security-incident
  description: "Create PagerDuty incident for ElastAlert2 security alerts"
  triggers:
    - type: alert
      filters:
        - key: source
          value: "elastalert2"
        - key: severity
          value: "CRITICAL"
  steps:
    - name: create-pagerduty-incident
      provider:
        type: pagerduty
        config: "{{ providers.pagerduty }}"
      with:
        title: "Security alert: {{ event.name }}"
        body: "{{ event.description }}"
```

## References

- [ElastAlert2 HTTP POST alerter docs](https://elastalert2.readthedocs.io/en/latest/ruletypes.html#http-post)
- [ElastAlert2 GitHub](https://github.com/jertel/elastalert2)
- [GitHub Issue #4232](https://github.com/keephq/keep/issues/4232)
