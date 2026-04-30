# SolarWinds Provider

The SolarWinds provider allows Keep to receive alerts from the SolarWinds Orion Platform.

## Supported Features

- **Pull-based alerts**: Fetches active alerts from SolarWinds Orion via the SWIS REST API using SWQL queries.
- **Push-based alerts (webhook)**: Receives alert notifications from SolarWinds Orion via webhooks.

## Prerequisites

- SolarWinds Orion Platform installed and accessible
- SWIS API credentials (username + password or API token)
- The SWIS API is typically available at `https://<hostname>:17778/SolarWinds/InformationService/v3/Json`

## Authentication

The provider supports two authentication methods:

### Username + Password (Basic Auth)

```yaml
authentication:
  host_url: https://solarwinds.example.com:17778/SolarWinds/InformationService/v3/Json
  username: admin
  password: your_password
```

### API Token (Bearer Auth)

```yaml
authentication:
  host_url: https://solarwinds.example.com:17778/SolarWinds/InformationService/v3/Json
  api_token: your_api_token
```

### Configuration Options

| Field | Required | Description |
|-------|----------|-------------|
| `host_url` | Yes | SolarWinds SWIS API base URL |
| `username` | No* | Username for basic auth |
| `password` | No* | Password for basic auth |
| `api_token` | No* | API token for bearer auth |
| `verify_ssl` | No | Verify SSL certificates (default: true) |

\* Either `username` + `password` or `api_token` must be provided.

## Setup

### Pull-based (Automatic Alert Fetching)

1. Add the SolarWinds provider in Keep with your SWIS API credentials.
2. Keep will periodically query the SWIS API for active alerts.
3. Alerts are mapped to Keep's alert format with severity, status, and node information.

### Webhook-based (Push from SolarWinds)

1. In Keep, add the SolarWinds provider to get the webhook URL and API key.
2. In SolarWinds Orion Web Console:
   - Go to **Settings > All Settings > Alerting, Reports, and Events > Alert Actions**.
   - Click **Add New Alert Action** and select **Execute an External Program** or **Send a Webhook**.
   - Configure the webhook URL with your Keep API key.
3. Assign the alert action to your alert definitions.

## Alert Fields Mapping

| SolarWinds Field | Keep Field |
|-----------------|------------|
| AlertObjectID | id |
| AlertDefinition Name | name |
| Severity (0-5) | severity (LOW/INFO/WARNING/HIGH/CRITICAL) |
| Acknowledged | status (ACKNOWLEDGED) |
| Node Status (Up/Down/Warning) | status (RESOLVED/FIRING) |
| AlertMessage | description / message |
| Node Caption | hostname |
| Node IP | ip_address |
| TriggeredDateTime | lastReceived |
| EntityCaption | service |
| NodeGroup | labels.node_group |

## Severity Mapping

| SolarWinds Severity | Keep Severity |
|--------------------|--------------| 
| 0 - Unknown | LOW |
| 1 - Information | INFO |
| 2 - Warning | WARNING |
| 3 - Minor | WARNING |
| 4 - Major | HIGH |
| 5 - Critical | CRITICAL |
| 14 - Notice | INFO |

## Troubleshooting

- **Connection refused**: Ensure the SWIS API port (default 17778) is accessible.
- **Authentication failed**: Verify your credentials and that the account has API access.
- **SSL errors**: Set `verify_ssl: false` if using self-signed certificates.
- **No alerts returned**: Check that there are active alerts in SolarWinds and the account has read permissions on `Orion.AlertActive`.
