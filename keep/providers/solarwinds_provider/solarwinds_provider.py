"""
SolarWinds Provider is a class that allows to ingest/digest data from SolarWinds Orion.
"""

import dataclasses
import datetime
import logging
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SolarwindsProviderAuthConfig:
    """
    SolarWinds authentication configuration.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion Server URL",
            "hint": "https://solarwinds.example.com:17778",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Username",
            "sensitive": False,
        }
    )
    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Password",
            "sensitive": True,
        }
    )
    verify: bool = dataclasses.field(
        metadata={
            "description": "Verify SSL certificates",
            "hint": "Set to false to allow self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )


class SolarwindsProvider(BaseProvider):
    """Pull/Push alerts from SolarWinds Orion into Keep."""

    PROVIDER_DISPLAY_NAME = "SolarWinds"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["id"]

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send alerts from SolarWinds Orion to Keep:

1. In the SolarWinds Orion Web Console, navigate to **Alerts & Activity > Alerts**.
2. Edit or create an alert, then go to the **Trigger Actions** tab.
3. Add a new **Send a GET or POST Request to a URL** action.
4. Set the URL to: `{keep_webhook_api_url}`
5. Set the HTTP method to **POST** and content type to **application/json**.
6. Add the header `X-API-KEY` with value `{api_key}`.
7. Configure the body with the following JSON template:
```json
{{
    "AlertActiveID": "${{N=Alerting;M=AlertActiveID}}",
    "AlertName": "${{N=Alerting;M=AlertName}}",
    "AlertDescription": "${{N=Alerting;M=AlertDescription}}",
    "AlertMessage": "${{N=Alerting;M=AlertMessage}}",
    "Severity": "${{N=Alerting;M=Severity}}",
    "Acknowledged": "${{N=Alerting;M=Acknowledged}}",
    "ObjectType": "${{N=Alerting;M=ObjectType}}",
    "TriggeredDateTime": "${{N=Alerting;M=AlertTriggerTime}}",
    "NodeName": "${{N=SwisEntity;M=Caption}}",
    "EntityType": "${{N=Alerting;M=EntityType}}",
    "status": "firing"
}}
```
8. Repeat for the **Reset Actions** tab, changing `"status": "firing"` to `"status": "resolved"`.
    """

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is Authenticated",
            mandatory=True,
        ),
        ProviderScope(
            name="read_alerts",
            description="Read active alerts from SolarWinds",
            mandatory=True,
            documentation_url="https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-managing-alerts-sw1498.htm",
        ),
    ]

    # SolarWinds severity levels
    # https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-alerts-severity-levels-sw712.htm
    SEVERITIES_MAP = {
        0: AlertSeverity.INFO,        # Informational
        1: AlertSeverity.WARNING,     # Warning
        2: AlertSeverity.CRITICAL,    # Critical
        3: AlertSeverity.HIGH,        # Serious
    }

    SEVERITY_STR_MAP = {
        "informational": AlertSeverity.INFO,
        "warning": AlertSeverity.WARNING,
        "critical": AlertSeverity.CRITICAL,
        "notice": AlertSeverity.LOW,
        "serious": AlertSeverity.HIGH,
        "info": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "firing": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
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
        Validates required configuration for SolarWinds provider.
        """
        self.authentication_config = SolarwindsProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate that the configured credentials have the necessary permissions.
        """
        validated_scopes = {}
        try:
            self._swis_query("SELECT TOP 1 NodeID FROM Orion.Nodes")
            validated_scopes["authenticated"] = True
        except Exception as e:
            validated_scopes["authenticated"] = str(e)

        try:
            self._swis_query("SELECT TOP 1 AlertActiveID FROM Orion.AlertActive")
            validated_scopes["read_alerts"] = True
        except Exception as e:
            validated_scopes["read_alerts"] = str(e)

        return validated_scopes

    def _swis_query(self, query: str, params: Optional[dict] = None) -> dict:
        """
        Execute a SWQL query against the SolarWinds Information Service (SWIS) REST API.

        Documentation: https://github.com/solarwinds/OrionSDK/wiki/About-SWIS

        Args:
            query: The SWQL query string.
            params: Optional query parameters.

        Returns:
            The parsed JSON response.
        """
        url = (
            f"{self.authentication_config.host_url}"
            f"/SolarWinds/InformationService/v3/Json/Query"
        )
        request_params = {"query": query}
        if params:
            request_params["parameters"] = params

        response = requests.get(
            url,
            params=request_params,
            auth=(
                self.authentication_config.username,
                self.authentication_config.password,
            ),
            verify=self.authentication_config.verify,
            headers={"Content-Type": "application/json"},
        )

        try:
            response.raise_for_status()
        except requests.HTTPError:
            self.logger.error(
                "Error while querying SolarWinds SWIS API",
                extra={
                    "status_code": response.status_code,
                    "response": response.text,
                    "tenant_id": self.context_manager.tenant_id,
                },
            )
            raise

        return response.json()

    def _get_alerts(self) -> list[AlertDto]:
        """
        Get active alerts from SolarWinds via the SWIS API.

        Queries Orion.AlertActive joined with Orion.AlertObjects and
        Orion.AlertConfigurations for comprehensive alert information.
        """
        self.logger.info("Collecting active alerts from SolarWinds")

        query = """
            SELECT
                aa.AlertActiveID,
                aa.AlertObjectID,
                aa.TriggeredDateTime,
                aa.TriggeredMessage,
                aa.Acknowledged,
                aa.AcknowledgedBy,
                aa.AcknowledgedDateTime,
                ac.Name AS AlertName,
                ac.Description AS AlertDescription,
                ac.Severity,
                ac.ObjectType,
                ao.EntityUri,
                ao.EntityType,
                ao.RelatedNodeCaption
            FROM Orion.AlertActive aa
            INNER JOIN Orion.AlertObjects ao
                ON aa.AlertObjectID = ao.AlertObjectID
            INNER JOIN Orion.AlertConfigurations ac
                ON ao.AlertID = ac.AlertID
            WHERE ac.Enabled = true
        """

        try:
            response = self._swis_query(query)
        except Exception:
            self.logger.error("Failed to get alerts from SolarWinds")
            raise

        formatted_alerts = []
        for alert in response.get("results", []):
            try:
                formatted_alerts.append(self._parse_swis_alert(alert))
            except Exception:
                self.logger.error(
                    "Failed to format SolarWinds alert",
                    extra={"alert_active_id": alert.get("AlertActiveID")},
                )
                continue

        self.logger.info(
            "Collected alerts from SolarWinds",
            extra={"alert_count": len(formatted_alerts)},
        )
        return formatted_alerts

    def _parse_swis_alert(self, alert: dict) -> AlertDto:
        """Parse a single SWIS query result row into an AlertDto."""
        severity_value = alert.get("Severity", 0)
        severity = self.SEVERITIES_MAP.get(severity_value, AlertSeverity.INFO)

        acknowledged = alert.get("Acknowledged", False)
        status = AlertStatus.ACKNOWLEDGED if acknowledged else AlertStatus.FIRING

        last_received = self._parse_datetime(alert.get("TriggeredDateTime"))

        return AlertDto(
            id=str(alert.get("AlertActiveID", "")),
            name=alert.get("AlertName", "Unknown Alert"),
            description=alert.get("AlertDescription", ""),
            message=alert.get("TriggeredMessage", ""),
            status=status,
            severity=severity,
            lastReceived=last_received,
            source=["solarwinds"],
            service=alert.get("RelatedNodeCaption", ""),
            acknowledged=acknowledged,
            acknowledgedBy=alert.get("AcknowledgedBy"),
            entity_type=alert.get("EntityType", ""),
            object_type=alert.get("ObjectType", ""),
            alert_object_id=str(alert.get("AlertObjectID", "")),
            entity_uri=alert.get("EntityUri", ""),
        )

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> str:
        """Parse a datetime string, returning ISO format or current UTC time."""
        if value and isinstance(value, str):
            try:
                return datetime.datetime.fromisoformat(
                    value.replace("Z", "+00:00")
                ).isoformat()
            except (ValueError, AttributeError):
                pass
        return datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format an incoming SolarWinds webhook event into an AlertDto.

        SolarWinds sends alerts via HTTP POST when configured with a
        "Send a GET or POST Request to a URL" trigger/reset action.
        """
        alert_id = event.get("AlertActiveID", event.get("id", ""))
        name = event.get("AlertName", event.get("name", "SolarWinds Alert"))
        description = event.get(
            "AlertDescription", event.get("description", "")
        )
        message = event.get("AlertMessage", event.get("message", name))

        # Severity mapping — handle both integer and string values
        severity_raw = event.get("Severity", event.get("severity", 0))
        if isinstance(severity_raw, str):
            if severity_raw.isdigit():
                severity = SolarwindsProvider.SEVERITIES_MAP.get(
                    int(severity_raw), AlertSeverity.INFO
                )
            else:
                severity = SolarwindsProvider.SEVERITY_STR_MAP.get(
                    severity_raw.lower(), AlertSeverity.INFO
                )
        else:
            severity = SolarwindsProvider.SEVERITIES_MAP.get(
                severity_raw, AlertSeverity.INFO
            )

        # Status mapping
        status_raw = event.get("status", "").lower()
        acknowledged = event.get(
            "Acknowledged", event.get("acknowledged", False)
        )
        # Normalize string booleans from webhook templates
        if isinstance(acknowledged, str):
            acknowledged = acknowledged.lower() in ("true", "1", "yes")

        if status_raw in SolarwindsProvider.STATUS_MAP:
            status = SolarwindsProvider.STATUS_MAP[status_raw]
        elif acknowledged:
            status = AlertStatus.ACKNOWLEDGED
        else:
            status = AlertStatus.FIRING

        last_received = SolarwindsProvider._parse_datetime(
            event.get("TriggeredDateTime", event.get("lastReceived"))
        )

        node_name = event.get(
            "NodeName",
            event.get("RelatedNodeCaption", event.get("service", "")),
        )

        return AlertDto(
            id=str(alert_id),
            name=name,
            description=description,
            message=message,
            status=status,
            severity=severity,
            lastReceived=last_received,
            source=["solarwinds"],
            pushed=True,
            service=node_name,
            environment=event.get("environment", "unknown"),
            acknowledged=acknowledged,
            entity_type=event.get("EntityType", ""),
            object_type=event.get("ObjectType", ""),
            url=event.get("url"),
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    host_url = os.environ.get("SOLARWINDS_HOST_URL")
    username = os.environ.get("SOLARWINDS_USERNAME")
    password = os.environ.get("SOLARWINDS_PASSWORD")

    provider_config = {
        "authentication": {
            "host_url": host_url,
            "username": username,
            "password": password,
            "verify": False,
        },
    }

    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="solarwinds",
        provider_type="solarwinds",
        provider_config=provider_config,
    )
    alerts = provider.get_alerts()
    print(alerts)
