# Mezmo Provider (formerly LogDNA)

The Mezmo Provider allows Keep to receive and query alerts from [Mezmo](https://www.mezmo.com), the observability platform formerly known as LogDNA.

## Features

- **Pull alert definitions** from Mezmo using the Log Analysis API
- **Receive webhook alerts** triggered by Mezmo alert conditions in real-time

## Authentication

You need a **Service Key** from your Mezmo account.

1. Go to **Mezmo** → **Settings** → **Organization** → **API Keys**
2. Copy your **Service Key**

## Configuration

| Field          | Required | Description                                                          |
|----------------|----------|----------------------------------------------------------------------|
| `service_key`  | ✅ Yes   | Mezmo Service Key for API authentication                             |
| `ingestion_key`| ❌ No    | Mezmo Ingestion Key (only if you want to send logs/events to Mezmo)  |
| `hostname`     | ❌ No    | API hostname (default: `api.mezmo.com`)                              |

## Setting up Webhooks

1. Go to **Mezmo** → **Alerts** → Create or edit an existing alert
2. Set notification channel to **Webhook**
3. Use your Keep webhook URL:
   ```
   https://<your-keep-url>/alerts/event/mezmo
   ```
4. Save — Keep will receive alert notifications from Mezmo automatically.

## Alert Fields Mapping

| Mezmo Field       | Keep Field      |
|-------------------|-----------------|
| `id` / `alertid`  | `id`            |
| `name`            | `name`          |
| `severity`/`level`| `severity`      |
| `status`/`state`  | `status`        |
| `triggered_at`    | `lastReceived`  |
| `body`/`message`  | `description`   |
| `url`             | `url`           |
| `query`           | `query`         |
| `channels`        | `channels`      |

## References

- [Mezmo Log Analysis API](https://docs.mezmo.com/log-analysis-api)
- [Mezmo Alert Configuration](https://docs.mezmo.com/log-analysis-api#tag/Alerts)
- [Mezmo Webhook Notifications](https://docs.mezmo.com/docs/alerts#notifications)
