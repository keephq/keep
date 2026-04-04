# Mimir Provider

The Mimir Provider integrates Keep with [Grafana Mimir](https://grafana.com/oss/mimir/), the horizontally scalable, highly available, multi-tenant long-term storage backend for Prometheus metrics.

## Features

- **Pull firing alerts** from Mimir's built-in Alertmanager API (`/alertmanager/api/v2/alerts`)
- **Receive real-time alerts** via Mimir Alertmanager's webhook receiver
- Compatible with both **self-hosted Mimir** and **Grafana Cloud** (Mimir-based)
- Multi-tenant support via `X-Scope-OrgID` header

## Authentication

| Deployment           | Auth Method                          |
|----------------------|--------------------------------------|
| Self-hosted (single) | No auth required (tenant: anonymous) |
| Self-hosted (multi)  | `X-Scope-OrgID` header (tenant ID)   |
| Grafana Cloud        | Basic auth (username + API key)      |

## Configuration

| Field        | Required | Description                                                              |
|--------------|----------|--------------------------------------------------------------------------|
| `base_url`   | ✅ Yes   | Mimir server URL, e.g. `http://mimir:9009`                               |
| `tenant_id`  | ❌ No    | Tenant ID (X-Scope-OrgID header), default: `anonymous`                   |
| `username`   | ❌ No    | Basic auth username (Grafana Cloud: your instance ID)                    |
| `password`   | ❌ No    | Basic auth password / API key (Grafana Cloud)                            |
| `verify_ssl` | ❌ No    | Verify SSL cert (default: `true`)                                        |

## Setting up Webhooks

Configure Mimir's Alertmanager to forward alerts to Keep by adding a webhook receiver to your Alertmanager configuration:

```yaml
# alertmanager.yaml (used in Mimir ruler config)
global:
  resolve_timeout: 5m

route:
  receiver: keep-receiver
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 12h

receivers:
  - name: keep-receiver
    webhook_configs:
      - url: "https://<your-keep-url>/alerts/event/mimir"
        send_resolved: true
```

Upload this config to Mimir via the Alertmanager API:
```bash
curl -X POST http://mimir:9009/alertmanager/api/v1/alerts \
  -H "X-Scope-OrgID: anonymous" \
  -d @alertmanager.yaml
```

## Alert Field Mapping

| Mimir Alertmanager Field         | Keep Field      |
|----------------------------------|-----------------|
| `labels.alertname`               | `name`          |
| `labels.severity`                | `severity`      |
| `status`                         | `status`        |
| `annotations.summary/description`| `description`   |
| `startsAt`                       | `lastReceived`  |
| `endsAt`                         | `resolvedAt`    |
| `fingerprint`                    | `id`            |
| `generatorURL`                   | `generator_url` |
| `labels`                         | `labels`        |

## Severity Mapping

| Mimir Severity | Keep Severity |
|----------------|---------------|
| critical/page  | CRITICAL      |
| error/high     | HIGH          |
| warning/warn   | WARNING       |
| info/none      | INFO          |
| low            | LOW           |

## References

- [Grafana Mimir Documentation](https://grafana.com/docs/mimir/latest/)
- [Mimir HTTP API Reference](https://grafana.com/docs/mimir/latest/references/http-api/)
- [Mimir Alertmanager](https://grafana.com/docs/mimir/latest/references/http-api/#alertmanager)
- [Prometheus Alertmanager Webhook](https://prometheus.io/docs/alerting/latest/configuration/#webhook_config)
