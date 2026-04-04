# SolarWinds Provider

The SolarWinds Provider integrates Keep with [SolarWinds Orion](https://www.solarwinds.com/solutions/orion), enabling alert and node monitoring data to flow into Keep workflows.

## Features

- **Pull active alerts** via the SolarWinds Information Service (SWIS) REST API
- **Pull node/device status** — fetches all nodes not in "Up" state (Down, Warning, Unreachable, etc.)
- **Webhook support** — receive SolarWinds alert notifications via Keep's webhook endpoint (using HTTP Action in Orion Alert Manager)

## Authentication

SolarWinds uses username/password authentication for the SWIS API.

1. Use an existing Orion user or create a dedicated API user
2. Ensure the user has at least **Orion Read-Only** role

## Configuration

| Field        | Required | Description                                          |
|--------------|----------|------------------------------------------------------|
| `hostname`   | ✅ Yes   | SolarWinds Orion server hostname or IP               |
| `username`   | ✅ Yes   | Orion username                                       |
| `password`   | ✅ Yes   | Orion password                                       |
| `port`       | ❌ No    | SWIS API port (default: `17774`)                     |
| `verify_ssl` | ❌ No    | Verify SSL certificate (default: `false`)            |

## Setting up Webhooks

1. In SolarWinds Orion, go to **Alerts & Activity** → **Alerts**
2. Edit an alert → **Trigger Actions** → Add action → **Send a GET or POST request to a URL**
3. Configure:
   - **URL**: `https://<your-keep-url>/alerts/event/solarwinds`
   - **Method**: POST
   - **Body**: Include alert variables as JSON:
   ```json
   {
     "AlertID": "${N=Alerting;M=AlertID}",
     "Name": "${N=Alerting;M=AlertName}",
     "Severity": "${N=Alerting;M=Severity}",
     "Message": "${N=Alerting;M=AlertMessage}",
     "RelatedNodeCaption": "${N=SwisEntity;M=Caption}",
     "TriggeredDateTime": "${N=Alerting;M=AlertTriggerTime}"
   }
   ```

## Alert State Mapping

### Severity
| SolarWinds   | Keep Severity |
|--------------|---------------|
| Critical     | CRITICAL      |
| Major        | HIGH          |
| Warning      | WARNING       |
| Informational| INFO          |

### Node Status
| SolarWinds   | Keep Status   | Keep Severity |
|--------------|---------------|---------------|
| Up (1)       | RESOLVED      | INFO          |
| Down (2)     | FIRING        | CRITICAL      |
| Warning (3)  | FIRING        | WARNING       |
| Unreachable  | FIRING        | HIGH          |

## References

- [SolarWinds Orion SDK (SWIS REST API)](https://github.com/solarwinds/OrionSDK/wiki/REST)
- [SWQL Reference](https://github.com/solarwinds/OrionSDK/wiki/SWQL)
- [Alert Variables](https://documentation.solarwinds.com/en/success_center/orionplatform/content/configure-alert-actions.htm)
