"""
SolarWinds is a class that provides a set of methods to interact with the
SolarWinds Information Service (SWIS) REST API to pull active alerts from
SolarWinds Orion.
"""

import dataclasses
import datetime

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SolarwindsProviderAuthConfig:
    """Authentication for SolarWinds Orion's SWIS REST API.

    SWIS exposes HTTPS Basic auth on port 17778 by default. Use the same
    credentials you would use for the Orion Web Console.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion server base URL (e.g. https://orion.example.com:17778)",
            "sensitive": False,
            "validation": "any_http_url",
        },
    )

    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion username",
            "sensitive": False,
        },
        default=None,
    )

    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion password",
            "sensitive": True,
        },
        default=None,
    )

    verify_ssl: bool = dataclasses.field(
        metadata={
            "required": False,
            "description": "Verify TLS certificates (disable for self-signed certs)",
            "sensitive": False,
        },
        default=True,
    )


class SolarwindsProvider(BaseProvider):
    """Pulls active alerts from SolarWinds Orion via the SWIS REST API."""

    PROVIDER_DISPLAY_NAME = "SolarWinds"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User can authenticate against the SWIS API",
        ),
    ]

    # SolarWinds Orion alert severity values (Orion.AlertConfigurations.Severity):
    # https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-using-the-information-service.htm
    SEVERITY_MAP = {
        0: AlertSeverity.INFO,       # Informational
        1: AlertSeverity.LOW,        # Notice
        2: AlertSeverity.WARNING,    # Warning
        3: AlertSeverity.HIGH,       # Serious
        4: AlertSeverity.CRITICAL,   # Critical
    }

    FINGERPRINT_FIELDS = ["alert_object_id"]

    # SWQL query that returns the currently-active alerts joined with their
    # configuration so we can read severity and configured names.
    ACTIVE_ALERTS_QUERY = (
        "SELECT a.AlertActiveID, a.AlertObjectID, a.TriggeredDateTime, "
        "a.TriggeredMessage, a.Acknowledged, a.AcknowledgedBy, "
        "a.AcknowledgedDateTime, "
        "ao.AlertID, ao.EntityCaption, ao.EntityType, ao.RelatedNodeCaption, "
        "ac.Name AS AlertName, ac.Severity, ac.Description "
        "FROM Orion.AlertActive a "
        "INNER JOIN Orion.AlertObjects ao ON a.AlertObjectID = ao.AlertObjectID "
        "INNER JOIN Orion.AlertConfigurations ac ON ao.AlertID = ac.AlertID"
    )

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

    def __query_url(self) -> str:
        base = str(self.authentication_config.host_url).rstrip("/")
        return f"{base}/SolarWinds/InformationService/v3/Json/Query"

    def __auth(self):
        return (
            self.authentication_config.username,
            self.authentication_config.password,
        )

    def __post_swql(self, query: str) -> dict:
        response = requests.post(
            self.__query_url(),
            json={"query": query},
            auth=self.__auth(),
            verify=self.authentication_config.verify_ssl,
            timeout=30,
        )
        if not response.ok:
            raise ProviderException(
                f"SolarWinds SWIS query failed: {response.status_code} {response.text[:300]}"
            )
        return response.json()

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            self.__post_swql("SELECT TOP 1 NodeID FROM Orion.Nodes")
            return {"authenticated": True}
        except Exception as exc:  # surface the underlying reason for the user
            return {"authenticated": f"Error validating scopes: {exc}"}

    @staticmethod
    def __parse_iso(value):
        if not value:
            return datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        # SWIS returns ISO 8601 with optional Z; let fromisoformat handle both.
        try:
            return datetime.datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            ).isoformat()
        except ValueError:
            return str(value)

    def _get_alerts(self) -> list[AlertDto]:
        try:
            self.logger.info("Pulling active alerts from SolarWinds Orion")
            payload = self.__post_swql(self.ACTIVE_ALERTS_QUERY)
        except Exception as exc:
            self.logger.error("Error querying SolarWinds: %s", exc)
            raise ProviderException(f"Error querying SolarWinds: {exc}") from exc

        results = payload.get("results", payload) or []
        alerts: list[AlertDto] = []
        for row in results:
            severity_int = row.get("Severity")
            severity = self.SEVERITY_MAP.get(severity_int, AlertSeverity.WARNING)

            acknowledged = bool(row.get("Acknowledged"))
            status = AlertStatus.ACKNOWLEDGED if acknowledged else AlertStatus.FIRING

            entity_caption = row.get("EntityCaption") or row.get("RelatedNodeCaption")
            name = row.get("AlertName") or entity_caption or "SolarWinds Alert"
            triggered = self.__parse_iso(row.get("TriggeredDateTime"))

            # Stable id: AlertObjectID is unique per (alert config, entity) pair
            # in Orion, so we can dedupe across pulls without races.
            alert_id = str(
                row.get("AlertObjectID")
                or row.get("AlertActiveID")
                or f"{name}-{triggered}"
            )

            alerts.append(
                AlertDto(
                    id=alert_id,
                    name=name,
                    description=row.get("TriggeredMessage") or row.get("Description"),
                    severity=severity,
                    status=status,
                    source=["solarwinds"],
                    lastReceived=triggered,
                    alert_object_id=row.get("AlertObjectID"),
                    alert_active_id=row.get("AlertActiveID"),
                    alert_id=row.get("AlertID"),
                    entity_type=row.get("EntityType"),
                    entity_caption=entity_caption,
                    related_node_caption=row.get("RelatedNodeCaption"),
                    acknowledged=acknowledged,
                    acknowledged_by=row.get("AcknowledgedBy"),
                    acknowledged_at=self.__parse_iso(row.get("AcknowledgedDateTime"))
                    if row.get("AcknowledgedDateTime")
                    else None,
                )
            )
        return alerts


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")

    host_url = os.environ.get("SOLARWINDS_HOST_URL")
    username = os.environ.get("SOLARWINDS_USERNAME")
    password = os.environ.get("SOLARWINDS_PASSWORD")

    if not host_url:
        raise ProviderException("SOLARWINDS_HOST_URL is not set")

    config = ProviderConfig(
        description="SolarWinds Provider",
        authentication={
            "host_url": host_url,
            "username": username,
            "password": password,
            "verify_ssl": os.environ.get("SOLARWINDS_VERIFY_SSL", "true").lower() != "false",
        },
    )

    provider = SolarwindsProvider(
        context_manager, provider_id="solarwinds", config=config
    )
    provider.validate_config()
    print(provider._get_alerts())
