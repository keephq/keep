"""
PRTG (Paessler Router Traffic Grapher) is a network monitoring tool that provides
real-time monitoring of servers, applications, and network devices.
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
    PRTG uses HTTP Action notifications to push alerts to external systems.
    No authentication is required on the receiving end — PRTG sends the data
    via HTTP POST to the configured webhook URL.
    """

    pass


class PrtgProvider(BaseProvider):
    """Receive alerts from PRTG Network Monitor via HTTP Action notifications."""

    PROVIDER_DISPLAY_NAME = "PRTG"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="connected",
            description="Provider is connected and can receive alerts",
            mandatory=False,
            mandatory_for_webhook=False,
            alias="Connected",
        ),
    ]

    webhook_description = "PRTG sends alert notifications via HTTP Action (HTTP POST)."
    webhook_template = ""
    webhook_markdown = """
To send alerts from PRTG to Keep, configure an HTTP Action notification in PRTG:

1. In PRTG, go to **Setup** → **Account Settings** → **Notification Templates**.
2. Click **Add Notification Template**.
3. Set a name, e.g. "Keep".
4. Enable **Execute HTTP Action**.
5. Set **URL** to: `{keep_webhook_api_url}`
6. Set **HTTP Method** to: `POST`
7. Set **Payload** to the following JSON:
```json
{{
  "host": "%%host",
  "name": "%%name",
  "sensor": "%%sensor",
  "message": "%%message",
  "status": "%%status",
  "lastvalue": "%%lastvalue",
  "device": "%%device",
  "group": "%%group",
  "probe": "%%probe",
  "link": "%%link",
  "id": "%%id",
  "sensorid": "%%sensorid",
  "datetime": "%%datetime",
  "down": "%%down",
  "sensor_type": "%%sensor_type",
  "tags": "%%tags",
  "priority": "%%priority"
}}
```
8. Click **Save**.
9. Assign this notification template to your sensors/devices via **Notification Triggers**.
"""

    SEVERITIES_MAP = {
        "1": AlertSeverity.INFO,       # Info
        "2": AlertSeverity.WARNING,    # Warning
        "3": AlertSeverity.WARNING,    # Unusual
        "4": AlertSeverity.HIGH,       # High
        "5": AlertSeverity.CRITICAL,   # Down / Critical
    }

    STATUS_MAP = {
        "Up": AlertStatus.RESOLVED,
        "Warning": AlertStatus.FIRING,
        "Down": AlertStatus.FIRING,
        "Paused": AlertStatus.SUPPRESSED,
        "Unknown": AlertStatus.FIRING,
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
        self.authentication_config = PrtgProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate scopes for PRTG provider.
        PRTG is a webhook-only provider, so we just confirm connectivity.
        """
        return {"connected": True}

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format a PRTG alert event into an AlertDto.

        PRTG sends alerts via HTTP POST with the following fields (using %% placeholders):
        - host: The hostname or IP of the monitored device
        - name: The name of the sensor
        - sensor: The sensor name
        - message: The alert message
        - status: The current status (Up, Down, Warning, Paused, Unknown)
        - lastvalue: The last measured value
        - device: The device name
        - group: The group name
        - probe: The probe name
        - link: URL to the sensor in PRTG
        - id: The sensor ID
        - sensorid: The sensor ID (alternative)
        - datetime: The date and time of the alert
        - down: Duration the sensor has been down
        - sensor_type: The type of sensor
        - tags: Tags associated with the sensor
        - priority: Priority level (1-5)
        """
        # Extract key fields
        sensor_name = event.get("sensor") or event.get("name") or "Unknown Sensor"
        device_name = event.get("device") or event.get("host") or "Unknown Device"
        message = event.get("message") or ""
        status = event.get("status") or "Unknown"
        link = event.get("link") or ""
        sensor_id = event.get("sensorid") or event.get("id") or ""
        priority = event.get("priority") or ""

        # Build alert name: "Device - Sensor"
        alert_name = f"{device_name} - {sensor_name}"

        # Map severity from PRTG priority (1-5) or status
        severity = PrtgProvider.SEVERITIES_MAP.get(
            str(priority),
            # Fallback: map from status
            {
                "Down": AlertSeverity.CRITICAL,
                "Warning": AlertSeverity.WARNING,
                "Up": AlertSeverity.INFO,
                "Paused": AlertSeverity.INFO,
                "Unknown": AlertSeverity.INFO,
            }.get(status, AlertSeverity.INFO),
        )

        # Map status
        alert_status = PrtgProvider.STATUS_MAP.get(status, AlertStatus.FIRING)

        # Build the AlertDto
        # AlertDto uses Config with extra = Extra.allow, so additional
        # PRTG-specific fields are stored as extra attributes.
        alert = AlertDto(
            id=sensor_id,
            name=alert_name,
            message=message,
            severity=severity,
            status=alert_status,
            url=link,
            lastReceived=event.get("datetime"),
            source=["prtg"],
            # PRTG-specific extra fields (allowed by Extra.allow)
            sensor=sensor_name,
            device=device_name,
            group=event.get("group"),
            probe=event.get("probe"),
            lastvalue=event.get("lastvalue"),
            down=event.get("down"),
            sensor_type=event.get("sensor_type"),
            tags=event.get("tags"),
            priority=priority,
        )

        return alert


if __name__ == "__main__":
    pass