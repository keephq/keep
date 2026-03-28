"""
ElastAlert2Provider receives alerts from ElastAlert2 via its HTTP POST alerter.

ElastAlert2 (https://github.com/jertel/elastalert2) is a framework for
alerting on anomalies, spikes, or other patterns in data stored in Elasticsearch
and OpenSearch. Keep integrates as an HTTP POST receiver.

Configuration in ElastAlert2 rule file (`my_rule.yaml`):

    alert:
      - post
    http_post_url: "https://<keep-host>/alerts/event/elastalert2?api_key=<api-key>"
    http_post_include_fields:
      - "@timestamp"
      - "message"
      - "host.name"
    http_post_payload: {}
    http_post_all_values: true

References:
  - https://elastalert2.readthedocs.io/en/latest/ruletypes.html#http-post
  - https://github.com/jertel/elastalert2
"""

from datetime import datetime, timezone

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class Elastalert2Provider(BaseProvider):
    """Receive alerts from ElastAlert2 via the HTTP POST alerter."""

    PROVIDER_DISPLAY_NAME = "ElastAlert2"
    PROVIDER_CATEGORY = ["Monitoring", "Security"]
    PROVIDER_TAGS = ["alert", "siem"]

    # ElastAlert2 uses HTTP POST with a JSON body — no auth config required on the
    # Keep side (the URL contains the API key as a query parameter).
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
## Setting up ElastAlert2 to send alerts to Keep

1. In your ElastAlert2 rule file (`rules/my_rule.yaml`), add the following:

```yaml
alert:
  - post

# Keep webhook URL — the API key is passed as a query parameter
http_post_url: "{keep_webhook_api_url}"

# Send all fields from the matched document
http_post_all_values: true

# Optionally include specific fields from the ES document
# http_post_include_fields:
#   - "@timestamp"
#   - "message"
#   - "host.name"
#   - "log.level"

# Optional: add extra static fields to every alert
http_post_payload:
  environment: "production"
```

2. Restart ElastAlert2.

3. Keep will now receive alerts whenever a rule fires. Each alert will include:
   - `rule_name` — the name of the ElastAlert2 rule
   - `alert_text` — the human-readable alert message
   - `num_hits` — number of matching documents
   - Any fields included from the matched Elasticsearch document
"""

    # Severity mapping from ElastAlert2 alert_priority (1–5 scale used by some rules)
    # or log.level / level fields often present in the source document
    SEVERITIES_MAP: dict[str, AlertSeverity] = {
        # alert_priority scale
        "1": AlertSeverity.CRITICAL,
        "2": AlertSeverity.HIGH,
        "3": AlertSeverity.WARNING,
        "4": AlertSeverity.INFO,
        "5": AlertSeverity.LOW,
        # log.level / level strings
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "high": AlertSeverity.HIGH,
        "warn": AlertSeverity.WARNING,
        "warning": AlertSeverity.WARNING,
        "medium": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "information": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
        "debug": AlertSeverity.LOW,
    }

    FINGERPRINT_FIELDS = ["rule_name", "name"]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """No authentication config is required for the ElastAlert2 provider."""
        pass

    def dispose(self):
        """Nothing to dispose."""
        pass

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """Convert an ElastAlert2 HTTP POST payload into an AlertDto.

        ElastAlert2 sends a flat JSON object. Required fields set by the
        alerter itself:

          - rule_name        — the rule that fired
          - alert_text       — the rendered alert message
          - alert_text_type  — formatting type (default "alert_text_only")
          - num_hits         — number of matching ES documents
          - num_matches      — number of rule matches

        Additional document fields (e.g. @timestamp, message, host.name,
        log.level) are included when `http_post_all_values: true` or listed
        under `http_post_include_fields`.
        """
        rule_name = event.get("rule_name", "elastalert2")
        alert_text = event.get("alert_text", event.get("message", rule_name))
        num_hits = event.get("num_hits", 0)

        # Timestamp: prefer the document's @timestamp, fall back to now
        raw_ts = event.get("@timestamp") or event.get("timestamp")
        try:
            last_received = (
                datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
                if raw_ts
                else datetime.now(tz=timezone.utc)
            )
        except ValueError:
            last_received = datetime.now(tz=timezone.utc)

        # Severity — check alert_priority first, then log.level / level
        severity_raw = (
            str(event.get("alert_priority", ""))
            or event.get("log.level", "")
            or event.get("level", "")
            or event.get("severity", "")
        ).lower().strip()

        severity = Elastalert2Provider.SEVERITIES_MAP.get(
            severity_raw, AlertSeverity.INFO
        )

        # Build description — include num_hits context
        description = alert_text
        if num_hits:
            description = f"{alert_text} ({num_hits} matching document(s))"

        alert = AlertDto(
            name=rule_name,
            description=description,
            severity=severity,
            status=AlertStatus.FIRING,
            source=["elastalert2"],
            lastReceived=last_received.isoformat(),
            # Preserve the full original payload for workflow access
            labels={
                k: str(v)
                for k, v in event.items()
                if k
                not in (
                    "rule_name",
                    "alert_text",
                    "alert_text_type",
                    "num_hits",
                    "num_matches",
                )
                and not isinstance(v, (dict, list))
            },
        )

        alert.fingerprint = Elastalert2Provider.get_alert_fingerprint(
            alert, fingerprint_fields=Elastalert2Provider.FINGERPRINT_FIELDS
        )

        return alert


if __name__ == "__main__":
    pass
