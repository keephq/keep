## Falco Provider

[Falco](https://falco.org/) is a CNCF-hosted cloud-native runtime security engine that detects anomalous behaviour in containers, Kubernetes clusters, and hosts by inspecting system calls.

### Authentication

This provider connects to [Falco Sidekick](https://github.com/falcosecurity/falcosidekick), the fan-out component that ships Falco events to external services.

| Field | Description | Required |
|-------|-------------|----------|
| `falcosidekick_url` | Base URL of your Falco Sidekick instance, e.g. `http://falcosidekick:2801` | Yes |
| `username` | Basic-auth username (leave blank if Sidekick is open) | No |
| `password` | Basic-auth password | No |
| `verify_ssl` | Whether to verify SSL certificates (default `true`) | No |

### Pull

Keep polls the Sidekick `/events` endpoint and converts each Falco event into an `AlertDto`.

**Severity mapping**

| Falco priority | Keep severity |
|----------------|---------------|
| emergency / alert / critical | CRITICAL |
| error | HIGH |
| warning | WARNING |
| notice / informational | INFO |
| debug | LOW |

### Webhook (Push)

Configure Falco Sidekick to forward events to Keep in real time:

```yaml
webhook:
  address: https://<your-keep-host>/api/alerts/event/falco
  customHeaders:
    Authorization: Bearer <api_key>
```

Each incoming webhook payload is automatically parsed and ingested as an alert.
