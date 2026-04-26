"""
ElastAlert2 provider for Keep.

ElastAlert2 is a framework for alerting on anomalies, spikes, or other
patterns of interest from data in Elasticsearch. It supports sending alerts
to external services via its HTTP POST alerter.

This provider receives alerts from ElastAlert2's HTTP POST alert type:
https://elastalert2.readthedocs.io/en/latest/ruletypes.html#http-post
"""

import datetime

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class Elastalert2Provider(BaseProvider):
    """Receive alerts from ElastAlert2 into Keep via HTTP POST alerter."""

    PROVIDER_DISPLAY_NAME = "ElastAlert2"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring", "Security"]
    FINGERPRINT_FIELDS = ["rule_name"]

    webhook_description = "This provider receives alerts from ElastAlert2 using the HTTP POST alert type."
    webhook_template = ""
    webhook_markdown = """
## Connecting ElastAlert2 to Keep

1. Open your ElastAlert2 rule YAML file (or the global `config.yaml`).
2. Add (or update) the `alert` and HTTP POST configuration:

```yaml
alert:
  - post

http_post_url: "{keep_webhook_api_url}"
http_post_headers:
  X-API-KEY: "{api_key}"
  Content-Type: application/json
http_post_all_values: true
```

3. `http_post_all_values: true` is recommended — it includes all matched field values in the payload, giving Keep rich context.

4. Reload or restart ElastAlert2 to pick up the new configuration.

Refer to the [ElastAlert2 HTTP Post documentation](https://elastalert2.readthedocs.io/en/latest/ruletypes.html#http-post) for more options.
"""

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "warn": AlertSeverity.WARNING,
        "medium": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "informational": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
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
        Format an ElastAlert2 HTTP POST payload into an AlertDto.

        ElastAlert2 posts the matched document fields plus metadata fields
        like rule_name, alert_type, alert_subject, and alert_text.

        Reference:
        https://elastalert2.readthedocs.io/en/latest/ruletypes.html#http-post
        """
        rule_name = event.get("rule_name", event.get("ruleName", "elastalert2-alert"))
        alert_subject = event.get("alert_subject", rule_name)
        alert_text = event.get("alert_text", event.get("message", alert_subject))

        # Severity — ElastAlert2 doesn't have a native severity field, but users
        # often add one via custom fields or the rule_type.
        raw_severity = (
            event.get("severity")
            or event.get("priority")
            or event.get("alert_priority")
            or "info"
        )
        severity = Elastalert2Provider.SEVERITIES_MAP.get(
            str(raw_severity).lower(), AlertSeverity.INFO
        )

        # Timestamp — ElastAlert2 includes the matched document's @timestamp
        received_time = (
            event.get("@timestamp")
            or event.get("timestamp")
            or datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        )

        # Source index / host for enrichment
        index = event.get("_index", event.get("index", None))
        source_host = event.get("host", event.get("hostname", None))
        if isinstance(source_host, dict):
            source_host = source_host.get("name", str(source_host))

        labels = {}
        if index:
            labels["index"] = index
        if source_host:
            labels["host"] = source_host

        alert = AlertDto(
            id=rule_name,
            name=alert_subject,
            description=alert_text,
            severity=severity,
            # ElastAlert2 has no native "resolved" concept — alerts always fire
            status=AlertStatus.FIRING,
            lastReceived=received_time,
            source=["elastalert2"],
            labels=labels,
            payload=event,
        )
        alert.fingerprint = Elastalert2Provider.get_alert_fingerprint(
            alert, fingerprint_fields=Elastalert2Provider.FINGERPRINT_FIELDS
        )
        return alert

    def dispose(self):
        pass
