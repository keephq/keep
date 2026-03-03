# Coroot Provider

## Overview
The Coroot provider receives monitoring alerts from [Coroot](https://coroot.com) via webhooks and can query Coroot's API for application data.

## Authentication
| Field | Required | Sensitive | Description |
|-------|----------|-----------|-------------|
| `api_url` | Yes | No | Coroot instance URL (e.g., `https://coroot.example.com`) |
| `api_key` | No | Yes | API key for authenticated queries |

## Capabilities
- **Webhook ingestion**: Receives alerts when Coroot detects incidents (CRITICAL, WARNING, OK)
- **API query**: Fetches application list via `/api/v1/applications`

## Alert Mapping
| Coroot Status | Keep Severity | Keep Status |
|---------------|---------------|-------------|
| CRITICAL | critical | firing |
| WARNING | warning | firing |
| OK | info | resolved |

## Setup
1. In Coroot → **Project Settings** → **Integrations** → add Webhook
2. Set URL to Keep's webhook endpoint
3. Add `X-API-KEY` header with your Keep API key
4. Save — alerts flow automatically

## Files
- `coroot_provider.py` — Provider implementation
- `alerts_mock.py` — Sample webhook payload for testing
- `../../tests/test_coroot_provider.py` — Unit tests
