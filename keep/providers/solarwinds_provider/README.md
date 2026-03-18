## Using Keep with SolarWinds

Keep integrates with SolarWinds Orion via the **SolarWinds Information Service (SWIS) REST API**.
This allows Keep to pull active alerts and node-down events from your SolarWinds infrastructure.

### Prerequisites

- SolarWinds Orion Platform (NPM, SAM, or any module using the Orion SDK)
- Admin or read-only user credentials
- SWIS REST API accessible (default port `17778`)

### Authentication

The SolarWinds provider uses **HTTP Basic Authentication** against the SWIS endpoint.

| Field | Description | Required |
|-------|-------------|----------|
| `hostname` | Orion server hostname or IP address | ✅ |
| `username` | SolarWinds admin username | ✅ |
| `password` | SolarWinds admin password | ✅ |
| `port` | SWIS REST API port (default: `17778`) | Optional |
| `verify_ssl` | Verify SSL certificate (default: `false`) | Optional |

### What Keep ingests

- **Active Alerts** (`Orion.AlertActive`) — all currently firing alerts with severity,
  trigger time, acknowledgement status, and affected node.
- **Node Alerts** (`Orion.Nodes`) — nodes with non-"Up" status (Down, Warning, Shutdown, etc.)

### Alert Severity Mapping

| SolarWinds Severity | Keep Severity |
|--------------------|---------------|
| 1 – Information | INFO |
| 2 – Warning | WARNING |
| 3 – Critical | CRITICAL |
| 4 – Emergency | CRITICAL |

### Connecting SolarWinds to Keep

1. Navigate to **Providers** in the Keep UI.
2. Click **Add Provider** → select **SolarWinds**.
3. Enter your Orion server hostname, username, and password.
4. Click **Connect** — Keep will validate the connection.
5. Keep will now regularly pull active alerts from your SolarWinds instance.

### References

- [SolarWinds SWIS REST API docs](https://github.com/solarwinds/OrionSDK/wiki/REST)
- [OrionSDK on GitHub](https://github.com/solarwinds/OrionSDK)
