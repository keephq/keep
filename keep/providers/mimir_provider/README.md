# Grafana Mimir Provider

[Grafana Mimir](https://grafana.com/oss/mimir/) is a horizontally scalable, highly available,
multi-tenant, long-term storage solution for Prometheus metrics. It exposes the same HTTP API
as Prometheus with the addition of multi-tenancy via the `X-Scope-OrgID` header.

## Overview

The Keep Mimir provider supports:

- **Pulling alerts** from the Mimir Alertmanager API (`/api/v1/alerts`)
- **Querying metrics** via PromQL (`/api/v1/query`)
- **Receiving alerts via webhook** from Mimir's Alertmanager (same format as Prometheus Alertmanager)
- **Multi-tenant deployments** via the `X-Scope-OrgID` header

## Authentication

Mimir supports multiple authentication methods depending on your deployment:

| Method | Config Fields |
|--------|---------------|
| No auth (single-tenant local) | `url` only |
| Basic auth | `url`, `username`, `password` |
| API key (Grafana Cloud) | `url`, `username`, `password` (API key as password) |
| Multi-tenant | add `tenant` (maps to `X-Scope-OrgID`) |

### Grafana Cloud Mimir

For Grafana Cloud-hosted Mimir:
- `url`: Your Prometheus-compatible endpoint, e.g. `https://prometheus-prod-01-eu-west-0.grafana.net/api/prom`
- `username`: Your numeric Grafana Cloud stack ID (found in the Grafana Cloud portal)
- `password`: A Grafana Cloud API key with `MetricsPublisher` or `Viewer` scope

## Configuration

```yaml
provider:
  type: mimir
  config:
    url: "https://mimir.example.com"
    username: ""          # optional: basic auth username
    password: ""          # optional: basic auth password / API key
    tenant: ""            # optional: X-Scope-OrgID for multi-tenant Mimir
    verify: true          # optional: set false for self-signed certs
```

## Receiving Alerts via Webhook

Mimir uses the Prometheus Alertmanager wire format. To forward alerts to Keep, configure
your Mimir Alertmanager with:

```yaml
route:
  receiver: "keep"
  group_by: ['alertname']
  group_wait:      15s
  group_interval:  15s
  repeat_interval: 1m
  continue: true

receivers:
- name: "keep"
  webhook_configs:
  - url: 'https://<your-keep-instance>/alerts/event/mimir'
    send_resolved: true
    http_config:
      basic_auth:
        username: api_key
        password: <your-keep-api-key>
```

For Grafana Mimir, the Alertmanager configuration can be applied via the
[`/api/v1/alerts` API](https://grafana.com/docs/mimir/latest/operators-guide/reference-http-api/#alertmanager)
or through `mimirtool`:

```bash
mimirtool alertmanager load alertmanager.yaml \
  --address=https://mimir.example.com \
  --id=<tenant-id>
```

## Example Workflow

```yaml
workflow:
  id: mimir-high-cpu-alert
  description: "Handle high CPU alerts from Mimir"
  triggers:
    - type: alert
      filters:
        - key: source
          value: "mimir"
        - key: name
          value: "HighCPUUsage"
  steps:
    - name: notify-slack
      provider:
        type: slack
        config: "{{ providers.slack }}"
      with:
        message: |
          CPU alert fired!
          Host: {{ event.labels.host }}
          Severity: {{ event.severity }}
          Summary: {{ event.description }}
```

## Multi-Tenant Usage

If your Mimir deployment uses multi-tenancy, set the `tenant` field to the desired
`X-Scope-OrgID` value. All API requests (queries and alert pulls) will include this header.

```yaml
provider:
  type: mimir
  config:
    url: "https://mimir.example.com"
    tenant: "my-team"
```

## References

- [Mimir HTTP API Reference](https://grafana.com/docs/mimir/latest/operators-guide/reference-http-api/)
- [Mimir Authentication](https://grafana.com/docs/mimir/latest/manage/secure/authentication-and-authorization/)
- [Alertmanager Configuration](https://prometheus.io/docs/alerting/latest/configuration/)
- [GitHub Issue #4679](https://github.com/keephq/keep/issues/4679)
