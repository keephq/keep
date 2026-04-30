## WeCom (Enterprise WeChat) Provider

[WeCom](https://work.weixin.qq.com/) (企业微信, also known as Enterprise WeChat) is Tencent's business communication platform, widely used in Asia for team collaboration. This provider sends alert notifications to WeCom group chats via the built-in [Group Bot Webhook API](https://developer.work.weixin.qq.com/document/path/90236).

### Authentication

| Field | Description | Required |
|-------|-------------|----------|
| `webhook_url` | WeCom Group Bot Webhook URL | Yes |

**How to obtain the Webhook URL:**

1. Open a group chat in WeCom (desktop or mobile).
2. Click the three-dot `···` menu in the top-right corner.
3. Select **Add Group Bot** → **Create a Bot**.
4. Give the bot a name and click **Confirm**.
5. Copy the **Webhook URL** from the bot detail page.

### Notification

Use the `_notify` action in a workflow to send messages to your WeCom group:

```yaml
actions:
  - name: send-wecom-alert
    provider:
      type: wecom
      config: "{{ providers.wecom-prod }}"
      with:
        message: |
          ## 🚨 Alert: {{ alert.name }}
          **Severity:** {{ alert.severity }}
          **Status:** {{ alert.status }}
          **Description:** {{ alert.description }}
        message_type: markdown
```

**Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `message` | str | required | Message body. Supports Markdown when `message_type="markdown"`. |
| `message_type` | str | `"markdown"` | `"text"` or `"markdown"` |
| `mentioned_list` | list | `[]` | WeCom user IDs to `@mention`, e.g. `["alice", "@all"]` (text type only) |
| `mentioned_mobile_list` | list | `[]` | Phone numbers to `@mention` (text type only) |

### Markdown Support

WeCom Markdown supports a subset of standard Markdown:

- `# Heading` — headings
- `**bold**` — bold text
- `<font color="red">text</font>` — coloured text
- `> quote` — block quotes
- `[link text](url)` — hyperlinks

### Notes

- The `mentioned_list` / `mentioned_mobile_list` parameters are only available when `message_type="text"`.
- The Webhook URL contains a secret key — treat it as a sensitive credential.
