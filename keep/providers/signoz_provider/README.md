# SigNoz Provider

Integrate [SigNoz](https://signoz.io/) with Keep for open-source, OpenTelemetry-native observability alerting.

## Modes

### Pull
Keep polls `GET /api/v1/alerts` on your SigNoz instance and surfaces active alerts.

### Push (Webhook)
SigNoz sends Prometheus Alertmanager-compatible webhook payloads to Keep on every alert state change.

## Configuration

| Field | Required | Description |
|-------|----------|-------------|
| `host_url` | Yes | Base URL of your SigNoz instance (e.g. `http://localhost:3301`) |
| `api_key` | No | SigNoz API key (`pat-...`) — required for SigNoz Cloud or auth-enabled self-hosted |
| `verify_ssl` | No | Verify SSL certificates (default: `true`) |

## Webhook Setup

1. In SigNoz: **Settings** -> **Alert Channels** -> **New Alert Channel** -> **Webhook**
2. Set URL to your Keep webhook URL
3. Enable **Send Resolved Alerts** (optional)
4. Assign the channel to alert rules under **Alerts** -> **Alert Rules**

## Severity Mapping

| SigNoz | Keep |
|--------|------|
| critical / p1 | CRITICAL |
| error / high / p2 | HIGH |
| warning / warn / medium / p3 | WARNING |
| info / informational / p4 | INFO |
| low / debug / p5 | LOW |

## References

- [SigNoz Webhook Channel](https://signoz.io/docs/alerts-management/notification-channel/webhook/)
- [SigNoz Alerts API](https://signoz.io/docs/alerts-management/alerts-api/)
