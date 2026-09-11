# Discord Provider

Send alert notifications to a Discord channel via an [Incoming Webhook](https://discord.com/developers/docs/resources/webhook#execute-webhook). Supports plain text, rich embeds, interactive components (buttons), file attachments, message editing, and automatic rate-limit handling.

## Setup

1. In the target Discord server, go to **Server Settings → Integrations → Webhooks**.
2. Click **Create Webhook**, name it, and pick the destination channel.
3. Copy the **Webhook URL**.
4. In Keep, create a Discord provider and paste the URL into `webhook_url`.

| Config field | Required | Description |
|---|---|---|
| `webhook_url` | Yes | The Discord webhook URL (sensitive). Must be on `discord.com` or `discordapp.com` - other hosts are rejected at configuration time. |

When the provider is configured, Keep validates the webhook via `validate_scopes()`, which issues a `GET` request to the webhook URL (Discord's "Get Webhook with Token" endpoint). No message is sent during validation.

## Usage

Any field accepted by the [Discord Execute Webhook JSON/form params](https://discord.com/developers/docs/resources/webhook#execute-webhook-jsonform-params) can be passed as a workflow `with:` key and is forwarded to Discord as-is (`embeds`, `username`, `avatar_url`, `allowed_mentions`, `flags`, `thread_name`, `applied_tags`, `poll`, `attachments`). A handful of named parameters get special handling because they can't be expressed as plain JSON, or because they change which HTTP call is made:

| Parameter | Type | Notes |
|---|---|---|
| `content` | `str` | Message text, up to 2000 characters |
| `components` | `list` | Interactive components (buttons, action rows) |
| `files` | `list` | File attachments — see [File Attachments](#file-attachments); up to 10 |
| `message_id` | `str` | Id of a previously sent message. When set, **edits** that message instead of posting a new one |
| `wait` | `bool` | Query param. Waits for Discord to confirm the send and returns the message body (needed to get `message_id` back for later edits) |
| `thread_id` | `str` | Query param. Sends the message into an existing thread |
| `with_components` | `bool` | Query param. Required for non-application-owned webhooks to use interactive components |

`tts` is explicitly **not** supported: it's dropped (with a warning logged) rather than forwarded. It has marginal value for incident notifications (the strongest use case is an always-on NOC voice channel reading P1 alerts aloud) and wasn't worth keeping in the general passthrough surface.

At least one of `content`, `embeds`, `components`, `files`, or `poll` is required when creating a new message. This isn't required when editing (`message_id` set) — Discord edits accept any subset of fields.

### Basic message

```yaml
with:
  content: "Something happened!"
```

### Interactive components (buttons)

```yaml
with:
  content: "Alert triggered"
  components:
    - type: 1 # Action row
      components:
        - type: 2 # Button
          style: 1 # Primary
          label: "Acknowledge"
          custom_id: "ack_button"
```

### Rich embeds

```yaml
with:
  username: "Keep AlertBot"
  embeds:
    - title: "High CPU Usage"
      description: "Server web-01 is at 92% CPU"
      color: 16711680 # 0xFF0000
      fields:
        - name: "Severity"
          value: "Critical"
```

### File Attachments

The `files` parameter accepts a list; each element can be any of:

| Form | Example |
|---|---|
| Dict `{base64, filename}` | `files: [{base64: "{{ steps.render-chart.results.chart_base64 }}", filename: "chart.png"}]` |
| Raw bytes | Programmatic use only (not expressible in YAML) |
| Tuple `(filename, content, mime_type)` | Programmatic use only |

**There is no filesystem-path form**, by design. Discord notifications run in the same shared, long-running process as every other tenant's workflows (see `workflowscheduler.py`'s thread pool) — a "read this path" parameter driven by workflow templating would let alert/event data (which can be externally influenced) trigger an arbitrary local file read. Base64 avoids that entirely: the file never touches disk, and it flows through Keep's existing step-output/templating mechanism (`{{ steps.<name>.results.<key> }}`) exactly like any other string value.

In practice this means a step that generates an artifact (a rendered chart, a log excerpt, a report) returns it as a base64 string in its `results` dict, and the Discord step references that via templating:

```yaml
actions:
  - name: render-chart
    provider:
      type: quickchart # or any step that produces `{"chart_base64": "..."}`
      ...

  - name: notify-with-chart
    provider:
      type: discord
      config: "{{ providers.mydiscord }}"
      with:
        content: "CPU spike detected"
        files:
          - base64: "{{ steps.render-chart.results.chart_base64 }}"
            filename: "cpu-spike.png"
```

Multiple files are sent as `files[0]`, `files[1]`, etc. (Discord's `multipart/form-data` convention). When `files` is present, the request automatically switches from JSON to multipart with a `payload_json` field carrying the rest of the message body.

### Editing messages

Discord lets a webhook edit messages it previously sent — no extra auth needed. Send with `wait: true` to get the message id back, then reuse it:

```yaml
actions:
  - name: notify
    provider:
      type: discord
      config: "{{ providers.mydiscord }}"
      with:
        content: "Investigating..."
        wait: true

  - name: resolve
    provider:
      type: discord
      config: "{{ providers.mydiscord }}"
      with:
        message_id: "{{ steps.notify.results.message_id }}"
        content: "Resolved."
```

`message_id` must be a Discord snowflake (digits only) - it's validated before being interpolated into the request URL.

## Return value

`notify()` returns a dict (never a bare bool/string — this matters if you use `enrich_alert`/`enrich_incident`, which index into the result):

```python
{"success": True}
# or, when Discord returns message data (wait=true, or an edit):
{"success": True, "message_id": "...", "channel_id": "..."}
```

## Rate limiting

Discord webhooks are rate limited (roughly 5 requests / 2 seconds per webhook). On a `429` response, the provider retries automatically — up to `DiscordProvider.MAX_RETRIES` (3) attempts total — honoring the `Retry-After` value Discord reports (response header, falling back to the `retry_after` field in the JSON body), clamped to `DiscordProvider.MAX_RETRY_AFTER_SECONDS` (30s) so a malformed or hostile response can't block a worker thread indefinitely. If retries are exhausted, a `ProviderException` is raised with Discord's rate-limit message.

## Client-side validation

To avoid a round-trip for a predictable `400`, the provider checks Discord's documented hard limits before sending:

| Limit | Constant | Value |
|---|---|---|
| Content length | `MAX_CONTENT_LENGTH` | 2000 characters |
| Embeds per message | `MAX_EMBEDS` | 10 |
| Files per message | `MAX_FILES` | 10 |
| File size (each) | `MAX_FILE_SIZE_BYTES` | 10 MiB (Discord's default, non-boosted limit) |

Exceeding any of these raises a `ProviderException` immediately with a clear message.

`webhook_url` is restricted to `discord.com`/`discordapp.com` hosts at configuration time (`ALLOWED_WEBHOOK_HOSTS`) — an arbitrary HTTPS URL is not accepted as a "Discord webhook," since that would make this provider usable as a generic outbound-request primitive.

## Testing

```bash
pytest tests/test_discord_provider.py -v
```

Tests mock `requests.post/patch/get` and cover: JSON passthrough, `tts` dropping, query params, all file-spec forms (bytes/tuple/base64 dict), guardrails (including per-file size), edit, `message_id` snowflake validation, webhook host validation, `validate_scopes()`, and rate-limit retry (including `Retry-After` clamping).

## Implementation notes

- `_notify()` builds a single `json_body` dict from `content`/`components` plus any other kwargs, so new Discord API fields work automatically without code changes — only file uploads need special handling since Discord requires `multipart/form-data` for those.
- `_send_request()` resolves `requests.post`/`patch` dynamically via `getattr(requests, method)` at call time (rather than binding a reference once), so it keeps working under mocking in tests and any future monkeypatching.
- `_normalize_file()` converts a supported file spec (bytes, tuple, or base64 dict) into a `(filename, content_bytes, content_type)` tuple consumed by `requests`' `files=` parameter. It never touches the filesystem.

## References

- [Discord: Execute Webhook](https://discord.com/developers/docs/resources/webhook#execute-webhook)
- [Discord: Edit Webhook Message](https://discord.com/developers/docs/resources/webhook#edit-webhook-message)
- [Discord: Uploading Files](https://discord.com/developers/docs/reference#uploading-files)
