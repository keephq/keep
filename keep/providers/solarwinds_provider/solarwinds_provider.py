"""
SolarwindsProvider is a class that allows you to pull network alerts from SolarWinds Orion.
"""

import dataclasses
import datetime
import logging
from typing import Optional

import pydantic
import requests
from requests.auth import HTTPBasicAuth

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SolarwindsProviderAuthConfig:
    """
    SolarWinds Orion authentication configuration.

    The provider uses the SolarWinds Information Service (SWIS) REST API.
    """

    orion_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion server base URL",
            "hint": "https://orion.example.com",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion username",
            "hint": "admin",
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
    verify_ssl: bool = dataclasses.field(
        metadata={
            "description": "Verify SSL certificates",
            "hint": "Set to false to allow self-signed certificates",
            "sensitive": False,
        },
        default=False,
    )


class SolarwindsProvider(BaseProvider):
    """Pull network and infrastructure alerts from SolarWinds Orion into Keep."""

    PROVIDER_DISPLAY_NAME = "SolarWinds"
    PROVIDER_CATEGORY = ["Monitoring", "Network"]
    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="alerts:read",
            description="Query active alerts via the SolarWinds SWIS REST API",
            mandatory=True,
            documentation_url="https://support.solarwinds.com/SuccessCenter/s/article/Use-the-SolarWinds-API",
        ),
    ]

    # Map SolarWinds alert severity to Keep severity
    # SolarWinds uses integer severity levels: 1=Information, 2=Warning, 3=Serious, 4=Critical
    SEVERITY_MAP = {
        1: AlertSeverity.INFO,
        2: AlertSeverity.WARNING,
        3: AlertSeverity.HIGH,
        4: AlertSeverity.CRITICAL,
    }

    # Acknowledged alerts → ACKNOWLEDGED status; all others are FIRING
    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """Validate the SolarWinds provider configuration."""
        self.authentication_config = SolarwindsProviderAuthConfig(
            **self.config.authentication
        )

    def _base_url(self) -> str:
        return str(self.authentication_config.orion_url).rstrip("/")

    def _auth(self) -> HTTPBasicAuth:
        return HTTPBasicAuth(
            self.authentication_config.username,
            self.authentication_config.password,
        )

    def _swis_query(self, swql: str) -> list[dict]:
        """Execute a SWIS (SolarWinds Query Language) query and return results."""
        url = f"{self._base_url()}/SolarWinds/InformationService/v3/Json/Query"
        response = requests.get(
            url,
            auth=self._auth(),
            params={"query": swql},
            verify=self.authentication_config.verify_ssl,
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("results", [])

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes: dict[str, bool | str] = {"alerts:read": False}
        try:
            results = self._swis_query(
                "SELECT TOP 1 AlertID FROM Orion.AlertActive"
            )
            scopes["alerts:read"] = True
        except Exception as e:
            scopes["alerts:read"] = str(e)
        return scopes

    def _get_alerts(self) -> list[AlertDto]:
        """Pull active alerts from SolarWinds Orion via SWIS."""
        swql = (
            "SELECT aa.AlertID, aa.AlertActiveID, aa.TriggeredDateTime, aa.Acknowledged, "
            "aa.AcknowledgedBy, aa.AcknowledgedDateTime, aa.NumberOfNotes, "
            "ad.Name, ad.Severity, ad.Message, ad.Description, "
            "aa.ObjectType, aa.EntityCaption, aa.EntityDetailsUrl "
            "FROM Orion.AlertActive aa "
            "JOIN Orion.AlertConfigurations ad ON aa.AlertID = ad.AlertID "
            "ORDER BY aa.TriggeredDateTime DESC"
        )
        try:
            rows = self._swis_query(swql)
        except Exception as e:
            self.logger.error("Failed to query SolarWinds alerts", extra={"error": str(e)})
            return []

        alerts = []
        for row in rows:
            alerts.append(self._format_alert(row))
        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """Convert a SolarWinds SWIS row into an AlertDto."""
        alert_id = str(event.get("AlertActiveID") or event.get("AlertID", "unknown"))
        name = event.get("Name", "Unknown Alert")
        message = event.get("Message", "")
        description = event.get("Description", "")
        severity_int = int(event.get("Severity") or 1)
        acknowledged = bool(event.get("Acknowledged") or False)
        triggered_raw = event.get("TriggeredDateTime", "")
        object_type = event.get("ObjectType", "")
        entity_caption = event.get("EntityCaption", "")
        entity_url = event.get("EntityDetailsUrl", "")
        ack_by = event.get("AcknowledgedBy", "")

        severity = SolarwindsProvider.SEVERITY_MAP.get(severity_int, AlertSeverity.INFO)
        status = AlertStatus.ACKNOWLEDGED if acknowledged else AlertStatus.FIRING

        try:
            # SolarWinds returns timestamps in format like "2024-01-01T12:00:00.0000000"
            last_received = (
                datetime.datetime.fromisoformat(triggered_raw.split(".")[0])
                .replace(tzinfo=datetime.timezone.utc)
                .isoformat()
            )
        except (ValueError, AttributeError):
            last_received = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

        labels = {
            "object_type": object_type,
            "entity": entity_caption,
        }
        if acknowledged and ack_by:
            labels["acknowledged_by"] = ack_by
        if entity_url:
            labels["entity_url"] = entity_url

        alert = AlertDto(
            id=alert_id,
            name=name,
            description=message or description,
            severity=severity,
            status=status,
            lastReceived=last_received,
            source=["solarwinds"],
            service=entity_caption,
            labels=labels,
            payload=event,
        )
        alert.fingerprint = SolarwindsProvider.get_alert_fingerprint(
            alert, fingerprint_fields=["id"]
        )
        return alert

    def dispose(self):
        pass

    def notify(self, **kwargs):
        raise NotImplementedError("SolarWinds provider does not support notify()")


if __name__ == "__main__":
    import os

    config = ProviderConfig(
        authentication={
            "orion_url": os.environ.get("SOLARWINDS_URL", "https://orion.example.com"),
            "username": os.environ.get("SOLARWINDS_USERNAME", "admin"),
            "password": os.environ.get("SOLARWINDS_PASSWORD", ""),
            "verify_ssl": False,
        }
    )
    from keep.contextmanager.contextmanager import ContextManager

    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")
    provider = SolarwindsProvider(context_manager, "solarwinds-prod", config)
    print(provider.get_alerts())
