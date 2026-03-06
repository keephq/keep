# Webhook Provider

The Webhook Provider allows you to send webhook notifications to any HTTP endpoint with support for custom headers, authentication, and HTTP methods.

## Authentication Configuration

The Webhook Provider supports the following authentication methods:

### Bearer Token Authentication
```yaml
authentication:
  bearer_token: "your-bearer-token-here"
```

### Basic Authentication
```yaml
authentication:
  basic_auth_username: "your-username"
  basic_auth_password: "your-password"
```

### No Authentication (Public Endpoints)
```yaml
authentication: {}
```

## Usage Examples

### Basic Webhook Notification

```yaml
workflow:
  id: webhook-example
  description: Send webhook notification
  triggers:
    - type: alert
  actions:
    - name: send-webhook
      provider:
        type: webhook
        config: "{{ providers.webhook }}"
        with:
          url: "https://api.example.com/webhooks/alerts"
          method: "POST"
          body:
            message: "Alert triggered"
            severity: "{{ alert.severity }}"
```

### With Custom Headers

```yaml
workflow:
  id: webhook-with-headers
  description: Send webhook with custom headers
  triggers:
    - type: alert
  actions:
    - name: send-webhook
      provider:
        type: webhook
        config: "{{ providers.webhook }}"
        with:
          url: "https://api.example.com/webhooks/alerts"
          method: "POST"
          headers:
            X-Custom-Header: "custom-value"
            X-Alert-Source: "keep"
          body:
            message: "Alert triggered"
            severity: "{{ alert.severity }}"
```

### Using PUT Method

```yaml
workflow:
  id: webhook-put-example
  description: Send webhook using PUT method
  triggers:
    - type: alert
  actions:
    - name: update-webhook
      provider:
        type: webhook
        config: "{{ providers.webhook }}"
        with:
          url: "https://api.example.com/webhooks/alerts/{{ alert.id }}"
          method: "PUT"
          body:
            status: "acknowledged"
            updated_at: "{{ now }}"
```

### With Bearer Token Authentication

```yaml
workflow:
  id: webhook-auth-example
  description: Send authenticated webhook
  triggers:
    - type: alert
  actions:
    - name: send-secure-webhook
      provider:
        type: webhook
        config: "{{ providers.webhook-with-auth }}"
        with:
          url: "https://api.example.com/webhooks/alerts"
          method: "POST"
          body:
            message: "Secure alert notification"
```

## Supported Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | The webhook URL to send the request to |
| `method` | string | No | POST | HTTP method: POST, PUT, or PATCH |
| `headers` | dict/string | No | {} | Custom headers to include in the request |
| `body` | dict/string | No | null | The request body/payload |
| `timeout` | int | No | 30 | Request timeout in seconds |

## Response Format

The provider returns a dictionary with the following information:

```python
{
    "status_code": 200,
    "response_text": "{\"status\": \"ok\"}",
    "success": True
}
```

## Error Handling

The provider raises `ProviderException` in the following cases:

- URL is not provided
- Invalid HTTP method (only POST, PUT, PATCH are supported)
- Failed to parse headers JSON
- Webhook request fails (network error, timeout, non-2xx response)

## Notes

- The provider automatically sets `Content-Type: application/json` if not specified in headers
- Bearer token authentication takes precedence over Basic authentication
- Headers and body can be provided as either a dictionary or a JSON string
- The provider follows redirects automatically (handled by the `requests` library)
