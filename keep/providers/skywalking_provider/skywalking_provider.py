"""
Apache SkyWalking Provider is a class that allows to ingest/digest data from SkyWalking.
"""

import logging
from datetime import datetime, timezone

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


class SkywalkingProvider(BaseProvider):
    """Receive alerts from Apache SkyWalking via webhook."""

    PROVIDER_DISPLAY_NAME = "Apache SkyWalking"
    PROVIDER_CATEGORY = ["Monitoring", "APM"]
    PROVIDER_TAGS = ["alert"]
    FINGERPRINT_FIELDS = ["id"]

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
    To configure SkyWalking to send alerts to Keep:

    1. Edit `alarm-settings.yml` in your SkyWalking OAP server config directory.
    2. Add a webhook hook configuration:

    ```yaml
    hooks:
      webhooks:
        keep:
          is-default: true
          text-template: "Alarm: %s"
          webhooks:
            - url: {keep_webhook_api_url}
              method: POST
              headers:
                X-API-KEY: {api_key}
                Content-Type: application/json
    ```

    3. Restart the SkyWalking OAP server.
    4. Configure alert rules to use this webhook hook.

    For more details, see the [SkyWalking Alarm documentation](https://skywalking.apache.org/docs/main/latest/en/setup/backend/backend-alarm/).
    """

    SEVERITIES_MAP = {
        "CRITICAL": AlertSeverity.CRITICAL,
        "HIGH": AlertSeverity.HIGH,
        "WARNING": AlertSeverity.WARNING,
        "WARN": AlertSeverity.WARNING,
        "INFO": AlertSeverity.INFO,
        "DEBUG": AlertSeverity.INFO,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        No validation required for SkyWalking webhook provider.
        """
        pass

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: BaseProvider = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format SkyWalking alarm webhook payload into Keep AlertDto.
        
        SkyWalking webhook payload format:
        {
            "scopeId": 1,
            "scope": "SERVICE",
            "name": "service_name",
            "id0": "c2VydmljZTE=.1",
            "id1": "",
            "ruleName": "service_resp_time_rule",
            "alarmMessage": "Alarm: Service service_name response time is higher than 1000ms in 3 minutes of last 10 minutes.",
            "tags": [
                {
                    "key": "level",
                    "value": "WARNING"
                }
            ],
            "startTime": 1704067200000
        }
        """
        logger.info(f"Formatting SkyWalking alert: {event}")

        # Extract tags into a dict for easier access
        tags = {}
        raw_tags = event.get("tags", [])
        if isinstance(raw_tags, list):
            for tag in raw_tags:
                if isinstance(tag, dict) and "key" in tag and "value" in tag:
                    tags[tag["key"]] = tag["value"]

        # Determine severity from tags or default to WARNING
        severity_str = tags.get("level", "WARNING").upper()
        severity = SkywalkingProvider.SEVERITIES_MAP.get(severity_str, AlertSeverity.WARNING)

        # Parse timestamp (SkyWalking sends milliseconds)
        start_time_ms = event.get("startTime")
        if start_time_ms:
            try:
                # Convert milliseconds to seconds
                start_time = datetime.fromtimestamp(start_time_ms / 1000, tz=timezone.utc).isoformat()
            except (ValueError, TypeError):
                logger.warning(f"Failed to parse startTime: {start_time_ms}")
                start_time = datetime.now(timezone.utc).isoformat()
        else:
            start_time = datetime.now(timezone.utc).isoformat()

        # Build the alert
        scope = event.get("scope", "UNKNOWN")
        name = event.get("name", "Unknown")
        rule_name = event.get("ruleName", "")
        alarm_message = event.get("alarmMessage", "")

        # Create alert ID from scope, name and rule
        alert_id = f"{scope}:{name}:{rule_name}" if rule_name else f"{scope}:{name}"

        alert = AlertDto(
            id=alert_id,
            name=rule_name or f"SkyWalking {scope} Alert",
            description=alarm_message,
            severity=severity,
            status=AlertStatus.FIRING,
            source=["skywalking"],
            scope=scope,
            service=name if scope == "SERVICE" else None,
            endpoint=name if scope == "ENDPOINT" else None,
            instance=name if scope == "SERVICE_INSTANCE" else None,
            rule_name=rule_name,
            scope_id=event.get("scopeId"),
            entity_id=event.get("id0"),
            tags=tags,
            lastReceived=start_time,
            startedAt=start_time,
        )

        return alert


if __name__ == "__main__":
    pass
