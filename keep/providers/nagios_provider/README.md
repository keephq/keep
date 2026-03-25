# Nagios Provider

Pull alerts from Nagios into Keep.

## Configuration

| Field | Description | Required |
|-------|-------------|----------|
| `host_url` | Nagios base URL (e.g., `https://nagios.example.com/nagios`) | Yes |
| `api_username` | Nagios username (e.g., `nagiosadmin`) | Yes |
| `api_password` | Nagios password | Yes |
| `verify_ssl` | Verify SSL certificates (default: `true`) | No |

## Features

- Pulls **service problems** (WARNING, CRITICAL, UNKNOWN)
- Pulls **host problems** (DOWN, UNREACHABLE)
- Converts Nagios states to Keep alert statuses and severities
- Supports SSL verification toggle for self-signed certificates

## API Endpoints Used

- `status.cgi` - Fetch current status of hosts and services
- Uses Nagios JSON output format (`jsonoutput` parameter)

## Authentication

Uses HTTP Basic Authentication with the Nagios web interface credentials.

## Usage

```python
from keep.providers.nagios_provider.nagios_provider import NagiosProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.contextmanager.contextmanager import ContextManager

config = ProviderConfig(
    authentication={
        "host_url": "https://nagios.example.com/nagios",
        "api_username": "nagiosadmin",
        "api_password": "your-password",
    }
)

context_manager = ContextManager(tenant_id="test", workflow_id="test")
provider = NagiosProvider(context_manager, "nagios", config)

# Get alerts
alerts = provider.get_alerts()
```
