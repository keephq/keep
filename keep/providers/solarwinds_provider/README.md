# SolarWinds Provider

Receive and normalize alerts from **SolarWinds Orion** (NPM, SAM, IPAM, and other modules) into Keep's unified alert feed via HTTP webhook.

## How it works

SolarWinds Orion evaluates alert conditions on a configurable polling interval. When an alert fires (or resets), Orion can POST a JSON body to an external HTTP endpoint. This provider registers a Keep webhook URL and converts each incoming payload into a `AlertDto`.

```
SolarWinds Orion alert fires
        │
        │  HTTP POST (JSON)
        ▼
   Keep webhook endpoint
        │
        │  SolarwindsProvider._format_alert()
        ▼
      AlertDto → Keep alert feed
```

## Supported alert fields

| SolarWinds field | Keep AlertDto field | Notes |
|---|---|---|
| `AlertActiveID` | `id` | Unique active-alert identifier |
| `AlertName` | `name` | Human-readable alert name |
| `AlertDescription` | `description` | Full description (falls back to `AlertMessage`) |
| `Severity` | `severity` | Integer 0–3 or string; see table below |
| `Acknowledged` | `status` | `true` → Acknowledged; `false` → Firing |
| `TimeOfAlert` | `lastReceived` | ISO-8601; Z suffix accepted |
| `AlertDetailsUrl` | `url` | Deep-link into Orion web console |
| `NodeName` / `NodeCaption` | `host` | Source node |
| `IP_Address` | (extra) | Available in payload extras |

### Severity mapping

| Orion integer | Orion label | Keep severity |
|:---:|---|---|
| 0 | Information | `INFO` |
| 1 | Warning | `WARNING` |
| 2 | Critical | `CRITICAL` |
| 3 | Fatal | `CRITICAL` |

## Setup

See the **webhook_markdown** field in `solarwinds_provider.py` for full step-by-step Orion configuration instructions, or open the provider page inside Keep and click **"How to connect"**.

## Mock data

`alerts_mock.py` contains six realistic payloads that cover all severity levels, both boolean and string `Acknowledged` values, and the integer-as-string edge case some older Orion versions emit. Run it directly to test the round-trip:

```bash
python -m keep.providers.solarwinds_provider.alerts_mock
```

## Development

```bash
# Install Keep in editable mode from the repo root
pip install -e ".[dev]"

# Run the mock round-trip
python -m keep.providers.solarwinds_provider.alerts_mock

# Run provider tests (once added to tests/providers/)
pytest tests/providers/test_solarwinds_provider.py -v
```
