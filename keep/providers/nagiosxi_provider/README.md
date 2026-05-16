## Nagios XI Provider

Nagios XI provider for Keep pulls host and service status from the Nagios XI REST API using API key authentication.

### Supported Features

- **Polling**: Periodically fetches host and service status from Nagios XI and maps them to Keep alerts.
- **Host Status**: Maps Nagios host states (UP/DOWN/UNREACHABLE) to Keep alert statuses and severities.
- **Service Status**: Maps Nagios service states (OK/WARNING/CRITICAL/UNKNOWN) to Keep alert statuses and severities.

### State Mapping

| Nagios Host State | Keep Status | Keep Severity |
|-------------------|-------------|----------------|
| 0 (UP)            | RESOLVED    | LOW            |
| 1 (DOWN)          | FIRING      | CRITICAL       |
| 2 (UNREACHABLE)   | FIRING      | WARNING        |

| Nagios Service State | Keep Status | Keep Severity |
|-----------------------|-------------|----------------|
| 0 (OK)                | RESOLVED    | LOW            |
| 1 (WARNING)           | FIRING      | WARNING        |
| 2 (CRITICAL)          | FIRING      | CRITICAL       |
| 3 (UNKNOWN)           | FIRING      | INFO           |

### Configuration

| Parameter | Description | Required |
|-----------|-------------|----------|
| `host_url` | Nagios XI base URL (e.g. `https://nagios.example.com/nagios`) | Yes |
| `api_key`  | Nagios XI API key | Yes |

### How to get the API Key

1. Log in to your Nagios XI web interface.
2. Navigate to **Admin** > **Backends** > **API Keys** (or **Configure** > **API Keys** in older versions).
3. Click **Add New API Key**, provide a description, and save.
4. Copy the generated API key for use in Keep.

### How to debug with local Nagios XI

Start a Nagios XI Docker instance:

```bash
docker run -d \
  --name=nagiosxi \
  -p 8080:80 \
  -p 8443:443 \
  ghcr.io/nagiosenterprises/nagiosxi:latest
```

Wait 2-3 minutes for initialization, then access the web UI at `https://localhost:8443/nagiosxi/`.

Default login credentials: `nagiosadmin` / `nagiosadmin` (you will be prompted to change the password on first login).

After logging in, generate an API key from the Admin panel and configure Keep with:

- **host_url**: `https://localhost:8443/nagios`
- **api_key**: Your generated API key

### Troubleshooting

- **Connection refused**: Ensure Nagios XI is running and the host URL is correct. The URL should end with `/nagios` (not `/nagiosxi`).
- **401 Unauthorized**: Verify your API key is valid and has not expired. Regenerate the key if needed.
- **Empty results**: Make sure hosts and services are configured in Nagios XI. A fresh installation may not have any monitored objects.
- **SSL certificate errors**: If using a self-signed certificate, the provider will fail TLS verification. Consider using a valid certificate or testing with HTTP instead of HTTPS.
- **Timeout errors**: Increase the polling interval or check network connectivity between Keep and the Nagios XI server.
