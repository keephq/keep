# Nagios Provider for Keep

This provider integrates Nagios monitoring with Keep, allowing you to fetch alerts from your Nagios monitoring infrastructure.

## Supported Nagios Versions

- Nagios Core (with JSON CGI)
- Nagios XI

## Authentication Methods

1. **API Token** (Nagios XI): Use the API token generated from Nagios XI interface
2. **Basic Auth** (Nagios Core): Use username/password for basic HTTP authentication

## Configuration

### Required Parameters

- `host_url`: The URL of your Nagios instance (e.g., `http://nagios.example.com`)

### Optional Parameters

- `api_token`: API token for Nagios XI authentication
- `username`: Username for basic authentication (Nagios Core)
- `password`: Password for basic authentication (Nagios Core)

## Nagios Status Mapping

### Host Status
| Nagios Status | Keep Status | Keep Severity |
|--------------|-------------|---------------|
| UP (0) | RESOLVED | LOW |
| DOWN (2) | FIRING | CRITICAL |
| UNREACHABLE (3) | FIRING | WARNING |

### Service Status
| Nagios Status | Keep Status | Keep Severity |
|--------------|-------------|---------------|
| OK (0) | RESOLVED | LOW |
| WARNING (1) | FIRING | WARNING |
| CRITICAL (2) | FIRING | CRITICAL |
| UNKNOWN (3) | FIRING | INFO |

## Setup

### Nagios Core with JSON CGI

1. Enable the JSON CGI module in Nagios
2. Configure authentication for the CGI scripts
3. Use username/password in the provider configuration

### Nagios XI

1. Generate an API token from the Nagios XI interface
2. Use the API token in the provider configuration

## References

- [Nagios Official Website](https://www.nagios.org/)
- [Nagios Documentation](https://www.nagios.org/documentation/)
