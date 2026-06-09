# Squadcast Provider

The Squadcast provider enables Keep to integrate with [Squadcast](https://www.squadcast.com/) for incident management, alert routing, escalation policies, and on-call scheduling.

## Overview

Squadcast is an incident management platform similar to PagerDuty and Grafana OnCall. This provider allows Keep to:

- **Send alerts to Squadcast** — Create and manage incidents via webhook or REST API.
- **Receive alerts from Squadcast** — Process Squadcast webhook events as Keep alerts.
- **Query Squadcast** — Retrieve incidents, services, and escalation policies.

## Authentication

| Field | Required | Description |
|-------|----------|-------------|
| `api_key` | Yes | Squadcast API Refresh Token (Settings > API Tokens) |
| `webhook_url` | No | Squadcast Incident Webhook URL for simple incident creation |
| `api_url` | No | Squadcast API Base URL (defaults to `https://api.squadcast.com`) |

### Getting your API Refresh Token

1. Log in to [Squadcast](https://app.squadcast.com)
2. Navigate to **Settings** > **API Tokens**
3. Create a new token or copy an existing refresh token

### Getting a Webhook URL (Optional)

1. Navigate to your Service in Squadcast
2. Go to **Alert Sources**
3. Add or select the **Incident Webhook** integration
4. Copy the webhook URL

## Usage

### Creating Incidents

#### Via Webhook (Simple)

```yaml
workflow:
  id: squadcast-alert
  triggers:
    - type: alert
  actions:
    - name: notify-squadcast
      provider:
        type: squadcast
        config: "{{ providers.squadcast }}"
        with:
          message: "{{ alert.name }}"
          description: "{{ alert.description }}"
          priority: "P2"
          status: "trigger"
          event_id: "{{ alert.fingerprint }}"
          tags:
            environment: production
            service: "{{ alert.service }}"
```

#### Via REST API

```yaml
workflow:
  id: squadcast-api-alert
  triggers:
    - type: alert
  actions:
    - name: notify-squadcast
      provider:
        type: squadcast
        config: "{{ providers.squadcast }}"
        with:
          message: "{{ alert.name }}"
          description: "{{ alert.description }}"
          priority: "P1"
          service_id: "your-service-id"
          escalation_policy_id: "your-escalation-policy-id"
```

### Querying Squadcast

```yaml
workflow:
  id: query-squadcast
  triggers:
    - type: manual
  steps:
    - name: get-incidents
      provider:
        type: squadcast
        config: "{{ providers.squadcast }}"
        with:
          query_type: incidents
```

### Receiving Webhooks from Squadcast

To receive incident updates from Squadcast:

1. In Squadcast, go to **Settings** > **Extensions** > **Webhooks**
2. Add a new webhook pointing to your Keep instance:
   ```
   https://your-keep-instance/alerts/event/squadcast
   ```
3. Select the event types you want to forward (triggered, acknowledged, resolved)

Keep will automatically parse incoming Squadcast webhooks and create alerts.

## Notify Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `message` | string | Yes | Short incident summary |
| `description` | string | No | Detailed description |
| `priority` | string | No | Priority level: P1-P5 |
| `status` | string | No | Event status: trigger, acknowledge, resolve |
| `event_id` | string | No | Unique ID for deduplication |
| `tags` | dict | No | Key-value tags |
| `service_id` | string | API only | Squadcast service ID |
| `escalation_policy_id` | string | API only | Escalation policy ID |

## Query Types

| Type | Description |
|------|-------------|
| `incidents` | List incidents |
| `services` | List services |
| `escalation_policies` | List escalation policies |

## Alert Mapping

| Squadcast Field | Keep Alert Field |
|-----------------|------------------|
| `id` | `id` |
| `message` | `name` |
| `description` | `description` |
| `priority` (P1-P5) | `severity` (critical-low) |
| `event_type` | `status` |
| `service.name` | `service` |
| `tags` | `tags` |
| `url` | `url` |
| `created_at` | `lastReceived` |
