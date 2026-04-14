# Apache SkyWalking Provider

## Overview

The SkyWalking provider connects Keep to [Apache SkyWalking](https://skywalking.apache.org/), an open-source APM (Application Performance Monitoring) system designed for distributed systems, cloud-native architectures, and containers.

## Features

- **Pull alerts/alarms** from SkyWalking OAP server via GraphQL API
- **Webhook support** for real-time alarm notifications
- **Service topology** data for topology mapping
- **Severity mapping** from SkyWalking alarm levels to Keep severity levels

## Authentication

| Parameter | Required | Description |
|-----------|----------|-------------|
| `host` | Yes | SkyWalking OAP server URL (e.g., `http://localhost:12800`) |
| `username` | No | Username if authentication is enabled |
| `password` | No | Password if authentication is enabled |

## Setup

1. Ensure your SkyWalking OAP server is running and accessible
2. Add the provider in Keep with the OAP server URL
3. (Optional) Configure SkyWalking webhook to point to Keep's webhook endpoint for real-time alerts

### Webhook Configuration

In your SkyWalking `alarm-settings.yml`, add a webhook hook:

```yaml
webhooks:
  - url: https://your-keep-instance/alerts/event/skywalking
```

## Scopes

| Scope | Description | Required |
|-------|-------------|----------|
| `read_alerts` | Read alarms/alerts from SkyWalking | Yes |
| `read_topology` | Read service topology data | No |

## Data Mapping

### Severity Mapping

| SkyWalking Level | Keep Severity |
|-----------------|---------------|
| critical, fatal | CRITICAL |
| error, high | HIGH |
| warning, warn | WARNING |
| info, notice | INFO |

## Useful Links

- [SkyWalking Documentation](https://skywalking.apache.org/docs/)
- [SkyWalking GraphQL API](https://skywalking.apache.org/docs/main/latest/en/api/query-protocol/)
- [SkyWalking Alarm Webhooks](https://skywalking.apache.org/docs/main/latest/en/setup/backend/backend-alarm/#webhook)
