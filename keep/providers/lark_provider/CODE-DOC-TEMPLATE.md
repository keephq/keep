# Lark/Feishu Provider

## Overview
The Lark provider integrates with [Lark/Feishu](https://www.larksuite.com/) helpdesk to receive ticket events via webhooks and manage tickets via API.

## Authentication
| Field | Required | Sensitive | Description |
|-------|----------|-----------|-------------|
| `app_id` | Yes | No | Lark Open Platform App ID |
| `app_secret` | Yes | Yes | Lark App Secret |
| `helpdesk_id` | No | No | Filter tickets by helpdesk |

Token management: The provider obtains a `tenant_access_token` via Lark's internal auth endpoint. Tokens are cached and automatically refreshed before the ~2h expiry.

## Capabilities
- **Webhook ingestion**: Receives `helpdesk.ticket.created_v1` and `helpdesk.ticket.updated_v1` events
- **API query**: Fetches helpdesk tickets
- **Notify**: Creates new helpdesk tickets

## Priority → Severity Mapping
| Lark Priority | Keep Severity |
|---------------|---------------|
| 1 / urgent | critical |
| 2 / high | high |
| 3 / medium | warning |
| 4 / low | low |
| (none) | info |

## Setup
1. Create an app on [Lark Open Platform](https://open.larksuite.com/)
2. Enable **Event Subscriptions** → set Request URL to Keep's webhook endpoint
3. Subscribe to `helpdesk.ticket.created_v1` and `helpdesk.ticket.updated_v1`
4. Add `X-API-KEY` header with your Keep API key
5. Publish app version

## Files
- `lark_provider.py` — Provider implementation
- `alerts_mock.py` — Sample helpdesk ticket event payload
- `../../tests/test_lark_provider.py` — Unit tests (format_alert + token cache TTL)
