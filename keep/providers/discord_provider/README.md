# Discord Provider

Send alert messages to Discord via webhook.

## Authentication

```yaml
authentication:
  webhook_url: "https://discord.com/api/webhooks/..."
```

## Usage Examples

### Basic Message

```yaml
workflow:
  id: discord-example
  triggers:
    - type: alert
  actions:
    - name: notify-discord
      provider:
        type: discord
        config: "{{ providers.discord }}"
        with:
          message: "🚨 Alert: {{ alert.name }} - {{ alert.severity }}"
```

### With Embed

```yaml
actions:
  - name: notify-discord-embed
    provider:
      type: discord
      config: "{{ providers.discord }}"
      with:
        message: "Alert triggered"
        embeds:
          - title: "{{ alert.name }}"
            description: "{{ alert.message }}"
            color: 16711680  # Red
            fields:
              - name: Severity
                value: "{{ alert.severity }}"
                inline: true
```

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| message | string | No* | Message content (Markdown supported) |
| embeds | list | No* | Discord embed objects |
| username | string | No | Override webhook username |
| avatar_url | string | No | Override webhook avatar URL |

*Either `message` or `embeds` is required

## Response

```python
{
    "status_code": 204,
    "success": True
}
```
