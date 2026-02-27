# Nagios Provider

This provider allows you to pull alerts from [Nagios](https://www.nagios.org/), an open-source monitoring system.

## Authentication

The Nagios provider supports two authentication methods:

### 1. NRDP API (Recommended)

[NRDPl](https://github.com/NagiosEnterprises/nrdp) (Nagios Remote Data Processor) is a modern REST API for Nagios.

Required configuration:
- `host_url`: Your Nagios server URL (e.g., `https://nagios.example.com`)
- `nrdp_token`: Your NRDP API token
- `api_type`: Set to `nrdp`

### 2. CGI API (Legacy)

Uses the Nagios Core CGI API with username/password authentication.

Required configuration:
- `host_url`: Your Nagios server URL
- `username`: Nagios CGI username
- `password`: Nagios CGI password
- `api_type`: Set to `cgi`

## Supported Alert Types

- **Host alerts**: Alerts for host states (DOWN, UNREACHABLE)
- **Service alerts**: Alerts for service states (WARNING, CRITICAL, UNKNOWN)

## Alert Severity Mapping

| Nagios State | Severity    |
|--------------|-------------|
| OK (0)       | LOW         |
| WARNING (1)  | WARNING     |
| CRITICAL (2) | CRITICAL    |
| UNKNOWN (3)  | INFO        |

## Installation

No additional Python packages are required. The provider uses standard HTTP requests.

## Example Usage

```python
from keep.providers.nagios_provider.nagios_provider import NagiosProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.contextmanager.contextmanager import ContextManager

config = ProviderConfig(
    description="Nagios Monitoring",
    authentication={
        "host_url": "https://nagios.example.com",
        "nrdp_token": "your-nrdp-token",
        "api_type": "nrdp",
    },
)

context_manager = ContextManager(tenant_id="tenant1", workflow_id="workflow1")
provider = NagiosProvider(
    context_manager=context_manager,
    provider_id="nagios-1",
    config=config,
)

# Get all alerts
alerts = provider._get_alerts()
```

## Configuration

```yaml
authentication:
  host_url: "https://nagios.example.com"
  nrdp_token: "your-nrdp-token"
  api_type: "nrdp"
  verify_ssl: true
```

## Notes

- Only non-OK/down alerts are fetched (resolved alerts are filtered out)
- Alerts include acknowledgment status
- Links to Nagios web interface are provided in alert metadata
