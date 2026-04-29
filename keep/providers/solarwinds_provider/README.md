## SolarWinds Provider

[SolarWinds Orion](https://www.solarwinds.com/) is a leading IT management platform for network, infrastructure, and application monitoring.

### Authentication

Keep connects to the SolarWinds Information Service (SWIS) REST API using basic authentication.

| Field | Description | Required |
|-------|-------------|----------|
| `orion_url` | Base URL of your SolarWinds Orion server, e.g. `https://orion.example.com` | Yes |
| `username` | SolarWinds Orion administrator username | Yes |
| `password` | SolarWinds Orion password | Yes |
| `verify_ssl` | Whether to verify SSL certificates (default `false` — Orion commonly uses self-signed certs) | No |

### Pull

Keep queries `Orion.AlertActive` joined with `Orion.AlertConfigurations` to retrieve all currently active alerts. Results are mapped to Keep's unified `AlertDto`:

**Severity mapping**

| SolarWinds severity | Keep severity |
|--------------------|---------------|
| 1 — Information | INFO |
| 2 — Warning | WARNING |
| 3 — Serious | HIGH |
| 4 — Critical | CRITICAL |

Acknowledged alerts are set to `ACKNOWLEDGED` status; all others are `FIRING`.

### Requirements

- The user account must have at minimum **read** access to `Orion.AlertActive` and `Orion.AlertConfigurations`.
- SWIS REST API must be enabled on the Orion server (enabled by default on port 17778, proxied at `/SolarWinds/InformationService/`).
