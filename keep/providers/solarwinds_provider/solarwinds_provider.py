"""
Solarwinds Provider for Keep - receive alerts from SolarWinds monitoring platform.
"""

import dataclasses

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SolarwindsProviderAuthConfig:
    """
    SolarWinds provider auth config.
    Uses Orion SDK REST API for communication.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion Host URL",
            "hint": "e.g. https://solarwinds.example.com",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )

    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion username",
            "sensitive": False,
        }
    )

    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion password",
            "sensitive": True,
        }
    )


class SolarwindsProvider(BaseProvider):
    """
    Get alerts from SolarWinds into Keep.

    Uses SolarWinds Orion REST API (SWIS - SolarWinds Information Service)
    to query active alerts and also supports webhook-based alert forwarding.
    """

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send alerts from SolarWinds to Keep:

1. In the Orion Web Console, go to **Settings > All Settings > Alerts & Reports > Manage Alerts**
2. Edit (or create) the alert you want forwarded
3. Add a **Trigger Action** of type "Send a GET or POST Request to a URL"
4. Configure:
   - **URL**: `{keep_webhook_api_url}`
   - **Method**: POST
   - **Content Type**: application/json
   - **Headers**: `X-API-KEY: <your Keep API key>`
   - **Body**:
```json
{{
  "alert_id": "${{AlertID}}",
  "alert_name": "${{AlertName}}",
  "severity": "${{Severity}}",
  "node_name": "${{NodeName}}",
  "ip_address": "${{IP_Address}}",
  "object_type": "${{ObjectType}}",
  "message": "${{AlertMessage}}",
  "trigger_time": "${{AlertTriggerTime}}",
  "acknowledged": "${{Acknowledged}}",
  "acknowledged_by": "${{AcknowledgedBy}}"
}}
```
5. Save the alert definition
    """

    PROVIDER_DISPLAY_NAME = "SolarWinds"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    WEBHOOK_INSTALLATION_REQUIRED = True
    PROVIDER_ICON = "solarwinds-icon.png"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read alerts from SolarWinds Orion",
        ),
    ]

    # SolarWinds severity mapping
    SEVERITY_MAP = {
        "Critical": AlertSeverity.CRITICAL,
        "Serious": AlertSeverity.HIGH,
        "Warning": AlertSeverity.WARNING,
        "Informational": AlertSeverity.INFO,
        "Notice": AlertSeverity.INFO,
        # Numeric values (0-4)
        0: AlertSeverity.INFO,
        1: AlertSeverity.WARNING,
        2: AlertSeverity.HIGH,
        3: AlertSeverity.CRITICAL,
        4: AlertSeverity.CRITICAL,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SolarwindsProviderAuthConfig(
            **self.config.authentication
        )

    def _get_session(self) -> requests.Session:
        """Create authenticated session for SolarWinds API."""
        session = requests.Session()
        session.auth = (
            self.authentication_config.username,
            self.authentication_config.password,
        )
        session.headers.update({"Content-Type": "application/json"})
        session.verify = False  # SolarWinds often uses self-signed certs
        return session

    def validate_scopes(self):
        """Validate by querying SolarWinds API."""
        self.logger.info("Validating SolarWinds provider scopes")
        try:
            session = self._get_session()
            # Test connectivity with a simple SWIS query
            response = session.get(
                f"{self.authentication_config.host_url}/SolarWinds/InformationService/v3/Json/Query",
                params={"query": "SELECT TOP 1 AlertActiveID FROM Orion.AlertActive"},
            )

            if response.status_code == 200:
                self.logger.info("SolarWinds scope validation success")
                return {"read_alerts": True}
            else:
                return {"read_alerts": f"HTTP {response.status_code}: {response.text[:200]}"}

        except Exception as e:
            self.logger.exception("Failed to validate SolarWinds scopes")
            return {"read_alerts": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        """Get active alerts from SolarWinds via SWIS query."""
        self.logger.info("Getting alerts from SolarWinds")

        try:
            session = self._get_session()
            query = """
                SELECT aa.AlertActiveID, aa.AlertObjectID, aa.TriggeredDateTime,
                       aa.Acknowledged, aa.AcknowledgedBy, aa.AcknowledgedDateTime,
                       ad.Name AS AlertName, ad.Description AS AlertDescription,
                       ad.Severity,
                       n.Caption AS NodeName, n.IP_Address
                FROM Orion.AlertActive aa
                JOIN Orion.AlertObjects ao ON aa.AlertObjectID = ao.AlertObjectID
                JOIN Orion.AlertConfigurations ad ON ao.AlertID = ad.AlertID
                LEFT JOIN Orion.Nodes n ON ao.EntityNetObjectID = 'N:' + ToString(n.NodeID)
                ORDER BY aa.TriggeredDateTime DESC
            """

            response = session.get(
                f"{self.authentication_config.host_url}/SolarWinds/InformationService/v3/Json/Query",
                params={"query": query},
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])

            return [
                AlertDto(
                    id=str(alert.get("AlertActiveID")),
                    name=alert.get("AlertName", "Unknown Alert"),
                    status=AlertStatus.ACKNOWLEDGED
                    if alert.get("Acknowledged")
                    else AlertStatus.FIRING,
                    severity=self.SEVERITY_MAP.get(
                        alert.get("Severity"), AlertSeverity.WARNING
                    ),
                    description=alert.get("AlertDescription", ""),
                    hostname=alert.get("NodeName"),
                    ip_address=alert.get("IP_Address"),
                    source=["solarwinds"],
                    timestamp=alert.get("TriggeredDateTime"),
                    acknowledged=alert.get("Acknowledged"),
                    acknowledged_by=alert.get("AcknowledgedBy"),
                )
                for alert in results
            ]

        except Exception as e:
            self.logger.exception("Failed to get alerts from SolarWinds")
            raise Exception(f"Failed to get alerts from SolarWinds: {e}")

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """Format SolarWinds webhook payload to Keep alert."""

        alert_id = event.get("alert_id", event.get("AlertID", ""))
        alert_name = event.get("alert_name", event.get("AlertName", "SolarWinds Alert"))
        severity_raw = event.get("severity", event.get("Severity", "Warning"))
        node_name = event.get("node_name", event.get("NodeName", ""))
        ip_addr = event.get("ip_address", event.get("IP_Address", ""))
        message = event.get("message", event.get("AlertMessage", ""))
        trigger_time = event.get("trigger_time", event.get("AlertTriggerTime", ""))
        acknowledged = event.get("acknowledged", event.get("Acknowledged", False))
        ack_by = event.get("acknowledged_by", event.get("AcknowledgedBy", ""))

        # Determine status
        if acknowledged and str(acknowledged).lower() not in ("false", "0", "no", ""):
            status = AlertStatus.ACKNOWLEDGED
        else:
            status = AlertStatus.FIRING

        severity = SolarwindsProvider.SEVERITY_MAP.get(severity_raw, AlertSeverity.WARNING)
        # Try numeric conversion
        if isinstance(severity_raw, str) and severity_raw.isdigit():
            severity = SolarwindsProvider.SEVERITY_MAP.get(
                int(severity_raw), AlertSeverity.WARNING
            )

        return AlertDto(
            id=str(alert_id) if alert_id else alert_name,
            name=alert_name,
            status=status,
            severity=severity,
            description=message,
            hostname=node_name,
            ip_address=ip_addr if ip_addr else None,
            source=["solarwinds"],
            timestamp=trigger_time if trigger_time else None,
            acknowledged=acknowledged,
            acknowledged_by=ack_by if ack_by else None,
        )


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    config = ProviderConfig(
        description="SolarWinds Provider",
        authentication={
            "host_url": os.environ.get("SOLARWINDS_URL", "https://solarwinds.example.com"),
            "username": os.environ.get("SOLARWINDS_USER", "admin"),
            "password": os.environ.get("SOLARWINDS_PASSWORD", ""),
        },
    )

    provider = SolarwindsProvider(context_manager, "solarwinds", config)
