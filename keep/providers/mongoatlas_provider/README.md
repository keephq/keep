# MongoDB Atlas Provider

MongoDB Atlas is a managed cloud database service by MongoDB that includes built-in monitoring and alerting. This provider integrates Keep with Atlas alerts, supporting both **pull** (polling the Atlas API) and **push** (receiving Atlas webhook notifications).

## Overview

| Feature | Support |
|---------|---------|
| Pull alerts | Yes — polls Atlas Alerts API v2 |
| Receive webhooks | Yes — Atlas webhook notifications |
| Authentication | HTTP Digest Auth (public + private API key) |
| Alert types | HOST_DOWN, NO_PRIMARY, DISK_FULL, REPLICATION_OPLOG_WINDOW_RUNNING_OUT, QUERY_EXECUTION_TIME_ALERT, and all Atlas event types |

## Authentication

MongoDB Atlas uses **HTTP Digest Authentication** with a public/private API key pair.

### Creating an API Key

1. Log in to [MongoDB Atlas](https://cloud.mongodb.com/).
2. Navigate to **Organization Settings** → **Access Manager** → **API Keys**.
3. Click **Create API Key** and assign the **Project Read Only** role (minimum required for pulling alerts).
4. Copy the **Public Key** and **Private Key** — the private key is shown only once.
5. Note your **Project ID** (Group ID):
   - Go to **Project Settings** → scroll to **Project ID**.

### Required Configuration Fields

| Field | Description |
|-------|-------------|
| `public_key` | MongoDB Atlas API public key |
| `private_key` | MongoDB Atlas API private key (sensitive) |
| `group_id` | Atlas Project ID (also called Group ID) |

## Pull Mode (Active Monitoring)

When configured, Keep will periodically poll the Atlas Alerts API for open alerts:

```
GET https://cloud.mongodb.com/api/atlas/v2/groups/{groupId}/alerts?status=OPEN
```

All open alerts are converted to Keep `AlertDto` objects with appropriate severity and status mappings.

## Push Mode (Webhook)

Atlas can send webhook notifications to Keep whenever an alert is opened or resolved.

### Setting Up Atlas Webhook

1. Log in to [MongoDB Atlas](https://cloud.mongodb.com/) and open your **Project**.
2. Go to **Project Settings** → **Alerts** → **Notification Settings**.
3. Click **+ Add** to create a new notification channel.
4. Select **Webhook** as the notification method.
5. Set the **Webhook URL** to your Keep webhook endpoint:
   ```
   {keep_webhook_api_url}
   ```
6. Add the following HTTP header for authentication:
   - **Header Name**: `X-API-KEY`
   - **Header Value**: `{api_key}`
7. Save the notification channel.
8. Assign this webhook to alert conditions under **Project Settings → Alerts → Alert Conditions**.

Atlas will POST alert payloads to Keep whenever an alert is triggered or resolved.

## Alert Severity Mapping

| Atlas Severity | Keep Severity |
|----------------|---------------|
| CRITICAL | CRITICAL |
| HIGH | HIGH |
| MEDIUM | WARNING |
| WARNING | WARNING |
| LOW | INFO |
| INFO / INFORMATIONAL | INFO |

For pull mode (status-based):

| Atlas Status | Keep Severity |
|--------------|---------------|
| OPEN | HIGH |
| TRACKING | WARNING |
| CLOSED | INFO |

## Alert Status Mapping

| Atlas Status | Keep Status |
|--------------|-------------|
| OPEN | FIRING |
| TRACKING | FIRING |
| CLOSED | RESOLVED |

## Supported Alert Types

Atlas generates alerts for a wide range of conditions including:

- **Host Alerts**: `HOST_DOWN`, `HOST_RESTARTED`, `HOST_RECOVERED`
- **Replica Set**: `NO_PRIMARY`, `REPLICATION_OPLOG_WINDOW_RUNNING_OUT`, `MEMBER_REMOVED`
- **Performance**: `QUERY_EXECUTION_TIME_ALERT`, `CONNECTIONS_PERCENT_ALERT`
- **Disk**: `DISK_FULL`, `DISK_AUTO_SCALE_INITIATED`
- **Cluster**: `CLUSTER_MONGOS_IS_MISSING`, `AUTO_SCALING_INITIATED`

All event types follow the Atlas [alert event types reference](https://www.mongodb.com/docs/atlas/reference/api-resources-spec/v2/#tag/Events).

## Example Webhook Payload

Atlas sends the following JSON structure to the webhook endpoint:

```json
{
  "id": "5f5a4a5e3b9a1a0001f3a1a1",
  "groupId": "5f5a4a5e3b9a1a0001f3a1b2",
  "eventTypeName": "HOST_DOWN",
  "status": "OPEN",
  "severity": "CRITICAL",
  "humanReadable": "We could not reach your MongoDB process at host1:27017.",
  "hostnameAndPort": "host1:27017",
  "clusterName": "MyCluster",
  "replicaSetName": "rs0",
  "created": "2024-01-15T10:00:00Z",
  "updated": "2024-01-15T10:00:00Z"
}
```

## References

- [MongoDB Atlas Alerts Overview](https://www.mongodb.com/docs/atlas/alert-basics/)
- [Atlas Alerts API v2](https://www.mongodb.com/docs/atlas/reference/api-resources-spec/v2/#tag/Alerts)
- [Configure Atlas Webhooks](https://www.mongodb.com/docs/atlas/configure-alerts/)
- [Atlas API Authentication](https://www.mongodb.com/docs/atlas/api/api-authentication/)
