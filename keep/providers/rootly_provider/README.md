# Rootly Provider

## Overview

The **Rootly** provider integrates Keep with the [Rootly](https://rootly.com/) incident management platform, allowing you to centralize alerts and incidents from Rootly alongside your other monitoring tools.

It supports **two modes**:

| Mode | How it works |
|------|-------------|
| **Pull (polling)** | Keep periodically fetches alerts and incidents from the Rootly API |
| **Push (webhook)** | Rootly sends real-time events to Keep via webhooks |

## Authentication

| Parameter | Required | Description |
|-----------|----------|-------------|
| `api_key` | Yes | Rootly API Key (Global, Team, or Personal) |
| `api_url` | No | API base URL. Defaults to `https://api.rootly.com` |
| `pull_incidents` | No | Also pull incidents in addition to alerts. Default: `true` |

### Generating an API Key

1. Log in to Rootly
2. Navigate to **Organization dropdown** → **Organization Settings** → **API Keys**
3. Click **Generate New API Key**
4. Choose scope: **Global**, **Team**, or **Personal**
5. Copy the generated key

## Data Pulled

### Alerts (`GET /v1/alerts`)
- Summary, description, status, source
- Services, environments, groups
- Labels (key-value pairs)
- Deduplication key

### Incidents (`GET /v1/incidents`)
- Title, summary, status, severity
- Services, environments
- Key timestamps (started_at, mitigated_at, resolved_at, etc.)
- Sequential ID, Slack channel
- Labels

## Severity Mapping

| Rootly Severity | Keep Severity |
|----------------|--------------|
| `critical` | Critical |
| `high` / `major` | High |
| `medium` / `warning` | Warning |
| `low` / `minor` | Low |
| `info` | Info |

## Status Mapping

### Alerts

| Rootly Status | Keep Status |
|--------------|------------|
| `open` / `triggered` | Firing |
| `acknowledged` | Acknowledged |
| `resolved` | Resolved |
| `noise` | Suppressed |

### Incidents

| Rootly Status | Keep Status |
|--------------|------------|
| `started` | Firing |
| `in_triage` | Acknowledged |
| `mitigated` | Pending |
| `closed` | Resolved |
| `cancelled` | Suppressed |

## Webhook Setup

To receive real-time events from Rootly:

1. Go to **Rootly** → **Settings** → **Integrations** → **Webhooks**
2. Click **Add Webhook**
3. Set the **Endpoint URL** to your Keep webhook endpoint: `https://your-keep-instance/alerts/event/rootly`
4. Select events to forward:
   - `alert.created`, `alert.updated`, `alert.resolved`
   - `incident.created`, `incident.updated`, `incident.mitigated`, `incident.resolved`, `incident.cancelled`
5. Add header `X-API-KEY: <your-keep-api-key>` under **Headers**
6. Click **Save**

## Notify (Create/Update)

The provider supports creating and updating incidents and alerts:

```python
# Create a new incident
provider.notify(title="API outage", summary="Users cannot login")

# Update an incident
provider.notify(incident_id="inc-123", status="mitigated")

# Resolve an alert
provider.notify(alert_id="alert-456", status="resolved")
```

## Fingerprinting

| Entity Type | Fingerprint Format |
|------------|-------------------|
| Alert | `rootly-alert-{alert_id}` |
| Incident | `rootly-incident-{incident_id}` |

## Useful Links

- [Rootly API Reference](https://docs.rootly.com/api-reference/overview)
- [Rootly API: List Alerts](https://docs.rootly.com/api-reference/alerts/list-alerts)
- [Rootly API: List Incidents](https://docs.rootly.com/api-reference/incidents/list-incidents)
- [Rootly API: Authentication](https://docs.rootly.com/api-reference/overview#how-to-generate-an-api-key)
