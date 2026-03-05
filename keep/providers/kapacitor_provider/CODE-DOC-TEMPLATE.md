# Kapacitor Provider

## Overview

The Kapacitor provider integrates InfluxData Kapacitor with Keep, enabling ingestion of Kapacitor alerts via webhook or pull-based querying of alert topics.

## Authentication

| Field | Required | Sensitive | Description |
|-------|----------|-----------|-------------|
| `url` | Yes | No | Kapacitor base URL (e.g. `http://localhost:9092`) |
| `username` | No | No | Kapacitor username |
| `password` | No | Yes | Kapacitor password |

## Capabilities

### Webhook (Push)
Receives Kapacitor HTTP POST alerts with JSON payload containing `id`, `message`, `details`, `level`, `time`, `duration`, and `data`.

### Query (Pull)
Queries alert topics via the Kapacitor REST API:
- `GET /kapacitor/v1/alerts/topics`

## Severity Mapping

| Kapacitor Level | Keep Severity | Keep Status |
|-----------------|---------------|-------------|
| CRITICAL | critical | firing |
| WARNING | warning | firing |
| INFO | info | firing |
| OK | low | resolved |

## Setup

1. In your TICKscript, add an HTTP POST handler pointing to Keep's webhook URL.
2. Include the `X-API-KEY` header with your Keep API key.
3. Alerts will flow into Keep automatically.
