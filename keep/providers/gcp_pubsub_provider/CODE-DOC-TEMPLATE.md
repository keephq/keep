# GCP Pub/Sub Provider

## Overview

The GCP Pub/Sub provider integrates Google Cloud Pub/Sub with Keep, enabling ingestion of GKE cluster notifications (security bulletins, upgrade notifications, end-of-support warnings) as alerts.

## Authentication

| Field | Required | Sensitive | Description |
|-------|----------|-----------|-------------|
| `project_id` | Yes | No | GCP Project ID |
| `subscription_id` | Yes | No | Pub/Sub Subscription ID |
| `credentials_json` | Yes | Yes | Google Service Account JSON credentials |

## Capabilities

### Webhook (Push)
Receives Pub/Sub push messages via HTTP POST. The message `data` field is base64-decoded and parsed as JSON.

### Query (Pull)
Pulls messages from the configured subscription using the Pub/Sub REST API:
- `POST https://pubsub.googleapis.com/v1/projects/{project}/subscriptions/{sub}:pull`

## Severity Mapping

| GKE Notification Type | Keep Severity |
|-----------------------|---------------|
| SECURITY_BULLETIN | critical |
| UPGRADE_AVAILABLE | info |
| UPGRADE_FORCED | warning |
| END_OF_SUPPORT | high |

## Setup

1. Create a Pub/Sub topic and subscription in your GCP project.
2. Configure a push subscription pointing to Keep's webhook URL, or use pull mode.
3. Provide service account credentials with `pubsub.subscriptions.pull` and `pubsub.subscriptions.consume` permissions.
