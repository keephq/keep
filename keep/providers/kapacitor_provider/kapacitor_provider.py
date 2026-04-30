"""
Kapacitor provider for Keep.

Kapacitor is InfluxData's data processing engine used to process streaming and
batch data from InfluxDB. It supports alerting via its alert node and can POST
alert payloads to a webhook endpoint.

This provider receives alerts from Kapacitor's HTTP Post event handler:
https://docs.influxdata.com/kapacitor/v1/reference/event_handlers/post/
"""

import datetime

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class KapacitorProvider(BaseProvider):
    """Receive alerts from Kapacitor into Keep via HTTP Post event handler."""

    PROVIDER_DISPLAY_NAME = "Kapacitor"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["id"]

    webhook_description = "This provider receives alerts from Kapacitor using the HTTP Post event handler."
    webhook_template = ""
    webhook_markdown = """
## Connecting Kapacitor to Keep

Kapacitor uses **HTTP Post** event handlers to forward alerts to external services.

1. Open (or create) your TICKscript that defines your alert logic.
2. Add an `.httpPost()` call at the end of your alert chain, pointing to the Keep webhook URL:

```javascript
stream
  |from()
    .measurement('cpu')
  |alert()
    .crit(lambda: "usage_idle" < 10)
    .httpPost('{keep_webhook_api_url}')
```

3. Alternatively, configure a **global HTTP Post handler** in `kapacitor.conf` or via the Kapacitor API:

```yaml
[[httppost]]
  endpoint = "keep"
  url = "{keep_webhook_api_url}"
  headers = {{"X-API-KEY" = "{api_key}"}}
  alert-template = ""
```

4. Reference the handler in your TICKscript:

```javascript
|alert()
  .id('{{ .Name }}/{{ .TaskName }}')
  .post('keep')
```

5. For authentication, add the Keep API key as the `X-API-KEY` header in your handler configuration.

Refer to the [Kapacitor HTTP Post documentation](https://docs.influxdata.com/kapacitor/v1/reference/event_handlers/post/) for details.
"""

    SEVERITIES_MAP = {
        "ok": AlertSeverity.INFO,
        "info": AlertSeverity.INFO,
        "warning": AlertSeverity.WARNING,
        "critical": AlertSeverity.CRITICAL,
    }

    STATUS_MAP = {
        "ok": AlertStatus.RESOLVED,
        "info": AlertStatus.FIRING,
        "warning": AlertStatus.FIRING,
        "critical": AlertStatus.FIRING,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """No config required for webhook-only provider."""
        pass

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a Kapacitor HTTP Post alert payload into an AlertDto.

        Kapacitor POST payload reference:
        https://docs.influxdata.com/kapacitor/v1/reference/event_handlers/post/#body
        """
        level = event.get("level", "info").lower()
        severity = KapacitorProvider.SEVERITIES_MAP.get(level, AlertSeverity.INFO)
        status = KapacitorProvider.STATUS_MAP.get(level, AlertStatus.FIRING)

        # Kapacitor uses 'id' as the alert identifier (e.g. "cpu/cpu_alert")
        alert_id = event.get("id", event.get("taskName", "kapacitor-alert"))
        name = event.get("name", alert_id)
        message = event.get("message", event.get("details", name))

        # Timestamps come as RFC3339 strings
        received_time = event.get("time", None)
        if received_time is None:
            received_time = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

        # Extract extra metadata
        data = event.get("data", {})
        tags = {}
        if isinstance(data, dict):
            series = data.get("series", [])
            if series and isinstance(series, list):
                tags = series[0].get("tags", {})

        alert = AlertDto(
            id=alert_id,
            name=name,
            description=message,
            severity=severity,
            status=status,
            lastReceived=received_time,
            source=["kapacitor"],
            labels=tags,
            payload=event,
        )
        alert.fingerprint = KapacitorProvider.get_alert_fingerprint(
            alert, fingerprint_fields=KapacitorProvider.FINGERPRINT_FIELDS
        )
        return alert

    def dispose(self):
        pass
