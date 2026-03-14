"""
Apache SkyWalking is an open-source APM and observability platform for
distributed systems, providing monitoring, tracing, and diagnostics.
"""

import logging
from datetime import datetime, timezone

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


class SkywalkingProvider(BaseProvider):
    """Receive alerts from Apache SkyWalking into Keep."""

    PROVIDER_DISPLAY_NAME = "SkyWalking"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["uuid"]

    # SkyWalking scope IDs mapped to human-readable names
    SCOPE_MAP = {
        1: "Service",
        2: "ServiceInstance",
        3: "Endpoint",
        4: "ServiceRelation",
        5: "ServiceInstanceRelation",
        6: "EndpointRelation",
    }

    webhook_description = "Receive alerts from Apache SkyWalking"
    webhook_markdown = """
To configure SkyWalking to send alerts to Keep:

1. Open your SkyWalking backend configuration file `config/alarm-settings.yml`.
2. Add a webhook hook pointing to Keep:

```yaml
webhook:
  keep:
    is-default: true
    urls:
      - {keep_webhook_api_url}
    headers:
      X-API-KEY: {api_key}
```

3. Restart the SkyWalking OAP server.
4. SkyWalking will now send alarm notifications to Keep when rules are triggered.

For more information, see the [SkyWalking Alerting documentation](https://skywalking.apache.org/docs/main/latest/en/setup/backend/backend-alarm/).
"""

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """No validation required for webhook-only provider."""
        pass

    @staticmethod
    def _get_severity_from_tags(tags: list[dict]) -> AlertSeverity:
        """Extract severity from SkyWalking alarm tags.

        SkyWalking alarms can include a 'level' tag with values like
        WARNING, CRITICAL, etc. configured in alarm-settings.yml.
        """
        if not tags:
            return AlertSeverity.WARNING

        for tag in tags:
            key = tag.get("key", "").lower()
            value = tag.get("value", "").upper()

            if key in ("level", "severity", "priority"):
                severity_map = {
                    "CRITICAL": AlertSeverity.CRITICAL,
                    "CRIT": AlertSeverity.CRITICAL,
                    "HIGH": AlertSeverity.HIGH,
                    "WARNING": AlertSeverity.WARNING,
                    "WARN": AlertSeverity.WARNING,
                    "LOW": AlertSeverity.LOW,
                    "INFO": AlertSeverity.INFO,
                    "OK": AlertSeverity.INFO,
                }
                return severity_map.get(value, AlertSeverity.WARNING)

        return AlertSeverity.WARNING

    @staticmethod
    def _get_status(event: dict) -> AlertStatus:
        """Determine alert status from SkyWalking alarm message.

        If recoveryTime is set (non-null), the alarm has been resolved.
        """
        recovery_time = event.get("recoveryTime")
        if recovery_time is not None:
            return AlertStatus.RESOLVED
        return AlertStatus.FIRING

    @staticmethod
    def _parse_timestamp(millis: int | None) -> str | None:
        """Convert millisecond epoch timestamp to ISO format."""
        if millis is None:
            return None
        try:
            dt = datetime.fromtimestamp(millis / 1000, tz=timezone.utc)
            return dt.isoformat()
        except (ValueError, TypeError, OSError):
            return None

    @staticmethod
    def _format_alert(
        event: dict,
        provider_instance: "BaseProvider | None" = None,
    ) -> AlertDto | list[AlertDto]:
        """Format a SkyWalking alarm message into Keep AlertDto.

        SkyWalking sends alerts as a JSON array of AlarmMessage objects:
        [{
            "scopeId": 1,
            "scope": "SERVICE",
            "name": "serviceA",
            "uuid": "uuid1",
            "id0": "12",
            "id1": "",
            "ruleName": "service_resp_time_rule",
            "alarmMessage": "alarmMessage xxxx",
            "startTime": 1560524171000,
            "recoveryTime": null,
            "tags": [{"key": "level", "value": "WARNING"}]
        }]

        This method handles a single event from that array.
        """
        tags = event.get("tags", [])

        # Build tags dict for Keep
        tags_dict = {}
        for tag in tags:
            key = tag.get("key")
            value = tag.get("value")
            if key and value:
                tags_dict[key] = value

        scope = event.get(
            "scope",
            SkywalkingProvider.SCOPE_MAP.get(event.get("scopeId", 0), "Unknown"),
        )

        start_time = SkywalkingProvider._parse_timestamp(event.get("startTime"))
        recovery_time = SkywalkingProvider._parse_timestamp(
            event.get("recoveryTime")
        )

        alert = AlertDto(
            id=event.get("uuid"),
            name=event.get("ruleName"),
            description=event.get("alarmMessage"),
            severity=SkywalkingProvider._get_severity_from_tags(tags),
            status=SkywalkingProvider._get_status(event),
            source=["skywalking"],
            service=event.get("name"),
            lastReceived=start_time,
            startedAt=start_time,
            resolvedAt=recovery_time,
            # SkyWalking-specific fields
            scope=scope,
            scopeId=event.get("scopeId"),
            id0=event.get("id0"),
            id1=event.get("id1"),
            ruleName=event.get("ruleName"),
            tags=tags_dict,
        )

        return alert


if __name__ == "__main__":
    pass
