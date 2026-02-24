"""
SolarWinds Provider for Keep.

Supports both pull (SWIS REST API with SWQL queries) and push
(webhook via SolarWinds alert actions) modes.

- Pull: Queries active alerts from Orion via the SWIS REST API.
- Push: Receives alerts via webhook from SolarWinds HTTP POST alert actions.
"""

import dataclasses

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

# SWQL query to fetch all active alerts with their associated objects and
# configuration details. Joins AlertActive (instances), AlertObjects (the
# entity that triggered), and AlertConfigurations (the alert definition).
ACTIVE_ALERTS_QUERY = """\
SELECT
    aa.AlertActiveID,
    aa.TriggeredDateTime,
    aa.TriggeredMessage,
    aa.Acknowledged,
    aa.AcknowledgedBy,
    aa.AcknowledgedDateTime,
    aa.AcknowledgedNote,
    ao.EntityCaption,
    ao.EntityType,
    ao.EntityNetObjectId,
    ao.RelatedNodeCaption,
    ao.RelatedNodeId,
    ac.AlertID,
    ac.Name AS AlertName,
    ac.Description AS AlertDescription,
    ac.Severity,
    ac.ObjectType,
    ac.Category
FROM Orion.AlertActive aa
INNER JOIN Orion.AlertObjects ao ON aa.AlertObjectID = ao.AlertObjectID
INNER JOIN Orion.AlertConfigurations ac ON aa.AlertID = ac.AlertID
WHERE ac.Enabled = true
ORDER BY aa.TriggeredDateTime DESC\
"""


@pydantic.dataclasses.dataclass
class SolarwindsProviderAuthConfig:
    """
    Authentication configuration for SolarWinds Orion SWIS REST API.

    Uses HTTP Basic Auth against the SWIS endpoint (port 17774).
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion Host URL",
            "hint": "e.g. https://orion.example.com:17774",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )

    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion Username",
            "sensitive": False,
        }
    )

    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion Password",
            "sensitive": True,
        }
    )

    verify_ssl: bool = dataclasses.field(
        default=True,
        metadata={
            "required": False,
            "description": "Verify SSL certificate (disable for self-signed certs)",
            "sensitive": False,
        },
    )


class SolarwindsProvider(BaseProvider):
    """
    Get alerts from SolarWinds Orion into Keep.

    Supports:
    - Pulling active alerts via SWIS REST API (SWQL queries)
    - Receiving real-time alerts via webhook (SolarWinds HTTP POST alert actions)
    """

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send alerts from SolarWinds Orion to Keep in real-time, configure an
HTTP POST alert action:

1. In the Orion web console, go to **Alerts & Activity > Alerts > Manage Alerts**.
2. Edit the alert definition you want to forward to Keep.
3. Under **Trigger Actions**, click **Add Action** and select
   **Send a GET or POST Request to a URL**.
4. Configure the action:
   - **URL**: `{keep_webhook_api_url}`
   - **Method**: `POST`
   - **Content Type**: `application/json`
   - **Header Name**: `X-API-KEY`
   - **Header Value**: `{api_key}`
   - **Body**:
```json
{{
  "alert_name": "${{N=Alerting;M=AlertName}}",
  "alert_message": "${{N=Alerting;M=AlertMessage}}",
  "severity": "${{N=Alerting;M=Severity}}",
  "alert_active_id": "${{N=Alerting;M=AlertActiveID}}",
  "alert_object_id": "${{N=Alerting;M=AlertObjectID}}",
  "alert_id": "${{N=Alerting;M=AlertID}}",
  "object_name": "${{N=SwisEntity;M=Caption}}",
  "object_type": "${{N=Alerting;M=ObjectType}}",
  "node_name": "${{N=SwisEntity;M=Node.Caption}}",
  "ip_address": "${{N=SwisEntity;M=IP_Address}}",
  "triggered_datetime": "${{N=Alerting;M=AlertTriggerTime;F=DateTime}}",
  "acknowledged": "${{N=Alerting;M=Acknowledged}}",
  "acknowledged_by": "${{N=Alerting;M=AcknowledgedBy}}",
  "notification_type": "PROBLEM"
}}
```
5. Optionally, add a **Reset Action** with the same configuration but set
   `"notification_type": "RECOVERY"` in the body to auto-resolve alerts.
6. For detailed setup instructions, see
   [Keep documentation](https://docs.keephq.dev/providers/documentation/solarwinds-provider).
    """

    PROVIDER_DISPLAY_NAME = "SolarWinds"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["alert_id", "object_name"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read active alerts from SolarWinds Orion via SWIS API",
        ),
    ]

    # SolarWinds severity integers: lower = more severe
    SEVERITY_MAP = {
        0: AlertSeverity.CRITICAL,  # Critical
        1: AlertSeverity.HIGH,  # Serious
        2: AlertSeverity.WARNING,  # Warning
        3: AlertSeverity.INFO,  # Informational
        4: AlertSeverity.LOW,  # Notice
        # String variants (from webhook payloads where severity may be a string)
        "0": AlertSeverity.CRITICAL,
        "1": AlertSeverity.HIGH,
        "2": AlertSeverity.WARNING,
        "3": AlertSeverity.INFO,
        "4": AlertSeverity.LOW,
        "Critical": AlertSeverity.CRITICAL,
        "Serious": AlertSeverity.HIGH,
        "Warning": AlertSeverity.WARNING,
        "Informational": AlertSeverity.INFO,
        "Notice": AlertSeverity.LOW,
    }

    # Notification type to status mapping (for webhooks)
    NOTIFICATION_TYPE_MAP = {
        "PROBLEM": AlertStatus.FIRING,
        "RECOVERY": AlertStatus.RESOLVED,
        "ACKNOWLEDGEMENT": AlertStatus.ACKNOWLEDGED,
    }

    SWIS_BASE_PATH = "/SolarWinds/InformationService/v3/Json"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = SolarwindsProviderAuthConfig(
            **self.config.authentication
        )

    def _swis_url(self, path: str) -> str:
        """Build a full SWIS REST API URL."""
        host = str(self.authentication_config.host_url).rstrip("/")
        return f"{host}{self.SWIS_BASE_PATH}{path}"

    def _swis_auth(self) -> tuple[str, str]:
        """Return Basic Auth credentials tuple."""
        return (
            self.authentication_config.username,
            self.authentication_config.password,
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        self.logger.info("Validating SolarWinds provider scopes")
        try:
            # Run a lightweight query to verify connectivity and credentials
            response = requests.post(
                url=self._swis_url("/Query"),
                auth=self._swis_auth(),
                json={"query": "SELECT TOP 1 AlertActiveID FROM Orion.AlertActive"},
                verify=self.authentication_config.verify_ssl,
            )

            if response.status_code == 200:
                self.logger.info("SolarWinds scope validation successful")
                return {"read_alerts": True}

            response.raise_for_status()

        except Exception as e:
            self.logger.exception("Failed to validate SolarWinds scopes")
            return {"read_alerts": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        self.logger.info("Getting alerts from SolarWinds Orion")

        try:
            response = requests.post(
                url=self._swis_url("/Query"),
                auth=self._swis_auth(),
                json={"query": ACTIVE_ALERTS_QUERY},
                verify=self.authentication_config.verify_ssl,
            )

            if response.status_code != 200:
                response.raise_for_status()

            data = response.json()
            results = data.get("results", [])

            alerts = []
            for alert in results:
                severity_raw = alert.get("Severity", 3)
                acknowledged = alert.get("Acknowledged", False)

                if acknowledged:
                    status = AlertStatus.ACKNOWLEDGED
                else:
                    status = AlertStatus.FIRING

                alerts.append(
                    AlertDto(
                        id=str(alert.get("AlertActiveID")),
                        name=alert.get("AlertName"),
                        description=alert.get("TriggeredMessage", ""),
                        alert_description=alert.get("AlertDescription"),
                        status=status,
                        severity=self.SEVERITY_MAP.get(
                            severity_raw, AlertSeverity.INFO
                        ),
                        lastReceived=alert.get("TriggeredDateTime"),
                        alert_id=str(alert.get("AlertID")),
                        object_name=alert.get("EntityCaption"),
                        object_type=alert.get("ObjectType", alert.get("EntityType")),
                        node_name=alert.get("RelatedNodeCaption"),
                        node_id=alert.get("RelatedNodeId"),
                        entity_type=alert.get("EntityType"),
                        category=alert.get("Category"),
                        acknowledged=acknowledged,
                        acknowledged_by=alert.get("AcknowledgedBy"),
                        acknowledged_datetime=alert.get("AcknowledgedDateTime"),
                        acknowledged_note=alert.get("AcknowledgedNote"),
                        source=["solarwinds"],
                    )
                )

            return alerts

        except Exception as e:
            self.logger.exception("Failed to get alerts from SolarWinds")
            raise Exception(f"Failed to get alerts from SolarWinds: {e}")

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a SolarWinds webhook payload into a Keep AlertDto.

        Handles both trigger (PROBLEM) and reset (RECOVERY) actions.
        """
        notification_type = event.get("notification_type", "PROBLEM")
        severity_raw = event.get("severity", 3)
        acknowledged = str(event.get("acknowledged", "false")).lower() in (
            "true",
            "1",
            "yes",
        )

        # Determine status
        if acknowledged:
            status = AlertStatus.ACKNOWLEDGED
        else:
            status = SolarwindsProvider.NOTIFICATION_TYPE_MAP.get(
                notification_type, AlertStatus.FIRING
            )

        # Build a meaningful ID for fingerprinting
        alert_active_id = event.get("alert_active_id")
        alert_id = event.get("alert_id")
        object_name = event.get("object_name", "unknown")

        alert = AlertDto(
            id=str(alert_active_id) if alert_active_id else f"{alert_id}_{object_name}",
            name=event.get("alert_name", "SolarWinds Alert"),
            description=event.get("alert_message", ""),
            status=status,
            severity=SolarwindsProvider.SEVERITY_MAP.get(
                severity_raw, AlertSeverity.INFO
            ),
            lastReceived=event.get("triggered_datetime"),
            alert_id=str(alert_id) if alert_id else None,
            alert_object_id=event.get("alert_object_id"),
            object_name=object_name,
            object_type=event.get("object_type"),
            node_name=event.get("node_name"),
            ip_address=event.get("ip_address"),
            acknowledged=acknowledged,
            acknowledged_by=event.get("acknowledged_by"),
            notification_type=notification_type,
            source=["solarwinds"],
        )

        return alert


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    host_url = os.environ.get("SOLARWINDS_HOST_URL")
    username = os.environ.get("SOLARWINDS_USERNAME")
    password = os.environ.get("SOLARWINDS_PASSWORD")

    config = ProviderConfig(
        description="SolarWinds Provider",
        authentication={
            "host_url": host_url,
            "username": username,
            "password": password,
            "verify_ssl": False,
        },
    )

    provider = SolarwindsProvider(context_manager, "solarwinds", config)
    alerts = provider._get_alerts()
    print(f"Got {len(alerts)} alerts")
    for alert in alerts:
        print(f"  {alert.node_name}: {alert.name} - {alert.status} ({alert.severity})")
