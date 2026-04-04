# Nagios Provider

The Nagios Provider integrates Keep with [Nagios](https://www.nagios.org), the industry-standard monitoring solution for infrastructure, network, and application health.

## Features

- **Pull host and service alerts** — fetches all non-OK states (DOWN, UNREACHABLE, WARNING, CRITICAL, UNKNOWN) directly from Nagios XI API
- **Webhook/passive check support** — receive Nagios alert notifications into Keep via EventBroker or custom scripts
- Full state and severity mapping aligned with Keep's alert model

## Supported Nagios Editions

| Edition       | API Support                  |
|---------------|------------------------------|
| Nagios XI     | ✅ Full REST API (`/api/v1`) |
| Nagios Core   | ✅ Via NCPA or custom scripts|

## Authentication

### Nagios XI (API Key - Recommended)
1. Log in to Nagios XI → **Admin** → **API Keys**
2. Copy your API key

### Nagios XI (Username/Password)
Use your Nagios XI username and password directly.

## Configuration

| Field            | Required | Description                                                        |
|------------------|----------|--------------------------------------------------------------------|
| `nagios_base_url`| ✅ Yes   | Base URL, e.g. `https://nagios.example.com/nagiosxi`               |
| `api_key`        | ❌ No    | Nagios XI API key (preferred over username/password)               |
| `username`       | ❌ No    | Nagios username (if API key not provided)                          |
| `password`       | ❌ No    | Nagios password                                                    |
| `verify_ssl`     | ❌ No    | Verify SSL certificates (default: `true`)                          |

## Alert State Mapping

### Host States
| Nagios State | Keep Status  | Keep Severity |
|--------------|--------------|---------------|
| UP (0)       | RESOLVED     | INFO          |
| DOWN (1)     | FIRING       | CRITICAL      |
| UNREACHABLE (2) | FIRING    | HIGH          |

### Service States
| Nagios State | Keep Status  | Keep Severity |
|--------------|--------------|---------------|
| OK (0)       | RESOLVED     | INFO          |
| WARNING (1)  | FIRING       | WARNING       |
| CRITICAL (2) | FIRING       | CRITICAL      |
| UNKNOWN (3)  | FIRING       | HIGH          |

## References

- [Nagios XI REST API](https://www.nagios.org/ncpa/help/2.1/api.html)
- [Nagios Documentation](https://www.nagios.org/documentation/)
- [Nagios XI API Keys](https://assets.nagios.com/downloads/nagiosxi/docs/Using-The-Nagios-XI-API.pdf)
