"""
PrtgProvider is a class that allows you to receive alerts from PRTG Network Monitor using webhooks.
"""

import dataclasses

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class PrtgProviderAuthConfig:
    """
    PRTG authentication configuration.
    """
    pass  # Webhook-based, no auth config needed for receiving alerts


class PrtgProvider(BaseProvider):
    """
    Receive alerts from PRTG Network Monitor via webhooks.
    """
    webhook_description = "Send alerts from PRTG to Keep"
    webhook_template = ""
    webhook_markdown = """
To send alerts from PRTG to Keep, follow these steps:

1. In PRTG web interface, go to "Setup" → "Notifications".
2. Click "Add new notification".
3. Set a name (e.g., "Send to Keep").
4. Enable "Execute HTTP Action".
5. Set the URL to: {keep_webhook_api_url}
6. Set the Method to "POST".
7. Set the Content Type to "application/json".
8. In the "Payload" field, use the following template:
```json
{
  "sensor": "%sensor",
  "device": "%device",
  "group": "%group",
  "status": "%status",
  "message": "%message",
  "datetime": "%datetime",
  "sensor_id": "%sensorid",
  "device_id": "%deviceid",
  "group_id": "%groupid",
  "priority": "%priority",
  "lastvalue": "%lastvalue",
  "probe": "%probe"
}
```
9. Save the notification.
10. Add this notification to any sensor's "Notification Triggers".
    """

    PROVIDER_DISPLAY_NAME = "PRTG"
    PROVIDER_TAGS = ["alert", "monitoring"]
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Receive alerts from PRTG via webhooks",
            mandatory=True,
            alias="Webhooks",
        ),
    ]

    # PRTG status to Keep status mapping
    STATUS_MAP = {
        "Up": AlertStatus.RESOLVED,
        "Down": AlertStatus.FIRING,
        "Warning": AlertStatus.FIRING,
        "Paused": AlertStatus.SUPPRESSED,
        "Unknown": AlertStatus.PENDING,
        "Unusual": AlertStatus.FIRING,
        "Partial Down": AlertStatus.FIRING,
    }

    # PRTG priority/severity mapping
    SEVERITY_MAP = {
        "*": AlertSeverity.INFO,      # 0 stars
        "**": AlertSeverity.WARNING,  # 1 star
        "***": AlertSeverity.HIGH,    # 2 stars  
        "****": AlertSeverity.CRITICAL, # 3 stars
        "*****": AlertSeverity.CRITICAL, # 4-5 stars
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for PRTG provider.
        """
        # Webhook-based provider, minimal config validation
        pass

    def validate_scopes(self):
        """
        Validate scopes for the provider.
        """
        return {"read_alerts": True}

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format PRTG webhook event into Keep AlertDto.
        """
        # Extract status
        prtg_status = event.get("status", "Unknown")
        status = PrtgProvider.STATUS_MAP.get(prtg_status, AlertStatus.FIRING)

        # Determine severity based on status and priority
        priority = event.get("priority", "**")
        if prtg_status == "Down":
            severity = AlertSeverity.CRITICAL
        elif prtg_status == "Warning":
            severity = AlertSeverity.WARNING
        elif prtg_status == "Unusual":
            severity = AlertSeverity.WARNING
        else:
            severity = PrtgProvider.SEVERITY_MAP.get(priority, AlertSeverity.INFO)

        # Build alert name
        sensor = event.get("sensor", "Unknown Sensor")
        device = event.get("device", "Unknown Device")
        name = f"{device} - {sensor}"

        return AlertDto(
            id=f"{event.get('sensor_id', 'unknown')}-{event.get('datetime', '')}",
            name=name,
            description=event.get("message", ""),
            status=status,
            severity=severity,
            lastReceived=event.get("datetime"),
            source=["prtg"],
            sensor=event.get("sensor"),
            device=event.get("device"),
            group=event.get("group"),
            probe=event.get("probe"),
            sensorId=event.get("sensor_id"),
            deviceId=event.get("device_id"),
            groupId=event.get("group_id"),
            priority=priority,
            lastValue=event.get("lastvalue"),
        )


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    # Test with sample PRTG webhook payload
    test_event = {
        "sensor": "CPU Load",
        "device": "Server-01",
        "group": "Production",
        "probe": "Local Probe",
        "status": "Down",
        "message": "CPU Load is above 90%",
        "datetime": "2024-01-15 10:30:00",
        "sensor_id": "1234",
        "device_id": "5678",
        "group_id": "9012",
        "priority": "****",
        "lastvalue": "95%"
    }

    config = ProviderConfig(
        description="PRTG Provider",
        authentication={}
    )

    provider = PrtgProvider(context_manager, "prtg", config)
    alert = PrtgProvider._format_alert(test_event)
    print(f"Formatted alert: {alert}")
