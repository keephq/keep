"""
SolarWinds provider for Keep.

SolarWinds is a network/infrastructure monitoring platform. This provider
uses the SolarWinds Information Service (SWIS) REST API to pull active
alerts from an Orion server.

API Reference:
    https://github.com/solarwinds/OrionSDK/wiki/About-SWIS
    https://github.com/solarwinds/OrionSDK/wiki/REST
    https://github.com/solarwinds/OrionSDK/wiki/Alerts
"""

import dataclasses
import datetime
import typing
import urllib.parse

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SolarwindsProviderAuthConfig:
    """SolarWinds authentication configuration."""

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion Server URL",
            "hint": "https://solarwinds.example.com:17774",
            "sensitive": False,
            "validation": "any_http_url",
        },
    )

    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds API Username",
            "sensitive": False,
        },
    )

    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds API Password",
            "sensitive": True,
        },
    )

    ssl_verify: typing.Optional[bool] = dataclasses.field(
        metadata={
            "required": False,
            "description": "Verify SSL certificates (disable for self-signed certs)",
            "sensitive": False,
        },
        default=True,
    )


class SolarwindsProvider(BaseProvider):
    """Pull alerts from SolarWinds Orion into Keep."""

    PROVIDER_DISPLAY_NAME = "SolarWinds"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["alert_active_id"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated and can query SWIS",
        ),
    ]

    # SolarWinds AlertConfigurations.Severity mapping:
    # 0 = Information, 1 = Warning, 2 = Critical, 3 = Serious, 4 = Notice
    SEVERITY_MAP = {
        0: AlertSeverity.INFO,
        1: AlertSeverity.WARNING,
        2: AlertSeverity.CRITICAL,
        3: AlertSeverity.HIGH,
        4: AlertSeverity.LOW,
    }

    # SWIS REST API base path
    SWIS_API_PATH = "/SolarWinds/InformationService/v3/Json"

    # SWQL query to fetch active alerts with details
    ACTIVE_ALERTS_QUERY = (
        "SELECT "
        "aa.AlertActiveID, "
        "aa.AlertObjectID, "
        "aa.TriggeredDateTime, "
        "aa.TriggeredMessage, "
        "aa.Acknowledged, "
        "aa.AcknowledgedBy, "
        "aa.AcknowledgedDateTime, "
        "ao.EntityCaption, "
        "ao.EntityDetailsUrl, "
        "ao.EntityType, "
        "ao.RelatedNodeCaption, "
        "ao.RelatedNodeDetailsUrl, "
        "ac.AlertID, "
        "ac.Name AS AlertName, "
        "ac.Description AS AlertDescription, "
        "ac.Severity "
        "FROM Orion.AlertActive aa "
        "INNER JOIN Orion.AlertObjects ao ON aa.AlertObjectID = ao.AlertObjectID "
        "INNER JOIN Orion.AlertConfigurations ac ON ao.AlertID = ac.AlertID"
    )

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """Validate the SolarWinds provider configuration."""
        self.authentication_config = SolarwindsProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate that we can authenticate and query the SWIS API."""
        try:
            # Run a lightweight query to check connectivity and auth
            self.__execute_swql("SELECT TOP 1 AlertID FROM Orion.AlertConfigurations")
            return {"authenticated": True}
        except Exception as e:
            return {"authenticated": f"Error validating scopes: {e}"}

    def __get_base_url(self) -> str:
        """Build the SWIS REST API base URL."""
        host_url = str(self.authentication_config.host_url).rstrip("/")
        return f"{host_url}{self.SWIS_API_PATH}"

    def __execute_swql(self, query: str) -> list[dict]:
        """
        Execute a SWQL query against the SWIS REST API.

        Args:
            query: A SWQL query string.

        Returns:
            A list of result dictionaries.

        Raises:
            Exception: If the query fails.
        """
        url = f"{self.__get_base_url()}/Query"
        params = {"query": query}

        self.logger.debug(
            "Executing SWQL query",
            extra={"query": query, "url": url},
        )

        response = requests.get(
            url,
            params=params,
            auth=(
                self.authentication_config.username,
                self.authentication_config.password,
            ),
            verify=self.authentication_config.ssl_verify,
            timeout=30,
        )

        if not response.ok:
            self.logger.error(
                "SWIS query failed: %s %s",
                response.status_code,
                response.text,
            )
            raise Exception(
                f"SWIS query failed with status {response.status_code}: {response.text}"
            )

        data = response.json()
        return data.get("results", [])

    def _get_alerts(self) -> list[AlertDto]:
        """Pull active alerts from SolarWinds."""
        alerts = []

        try:
            self.logger.info("Collecting active alerts from SolarWinds")
            results = self.__execute_swql(self.ACTIVE_ALERTS_QUERY)

            for result in results:
                try:
                    alert = self._format_alert(result, self)
                    alerts.append(alert)
                except Exception as e:
                    self.logger.warning(
                        "Failed to format SolarWinds alert: %s",
                        e,
                        extra={"alert_data": result},
                    )

            self.logger.info(
                "Collected %d alerts from SolarWinds",
                len(alerts),
            )
        except Exception as e:
            self.logger.error("Error getting alerts from SolarWinds: %s", e)

        return alerts

    @staticmethod
    def _format_alert(
        event: dict,
        provider_instance: "SolarwindsProvider" = None,
    ) -> AlertDto:
        """
        Format a SolarWinds alert into a Keep AlertDto.

        Args:
            event: A dictionary from the SWIS query result.
            provider_instance: The provider instance (optional).

        Returns:
            An AlertDto representing the SolarWinds alert.
        """
        # Determine severity
        raw_severity = event.get("Severity")
        if isinstance(raw_severity, int):
            severity = SolarwindsProvider.SEVERITY_MAP.get(
                raw_severity, AlertSeverity.INFO
            )
        else:
            severity = AlertSeverity.INFO

        # Determine status: acknowledged → ACKNOWLEDGED, otherwise → FIRING
        acknowledged = event.get("Acknowledged")
        if acknowledged:
            status = AlertStatus.ACKNOWLEDGED
        else:
            status = AlertStatus.FIRING

        # Parse triggered date/time
        triggered_dt = event.get("TriggeredDateTime")
        if triggered_dt:
            try:
                last_received = str(triggered_dt)
            except Exception:
                last_received = datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat()
        else:
            last_received = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Build alert URL from EntityDetailsUrl if available
        url = None
        entity_details_url = event.get("EntityDetailsUrl")
        if entity_details_url and provider_instance:
            host_url = str(
                provider_instance.authentication_config.host_url
            ).rstrip("/")
            # Remove port from host URL for the web console URL
            # SWIS API runs on port 17774, but the web console is typically on port 443
            try:
                parsed = urllib.parse.urlparse(host_url)
                web_host = f"{parsed.scheme}://{parsed.hostname}"
                url = f"{web_host}{entity_details_url}"
            except Exception:
                url = None

        # Build the name from alert name and entity
        alert_name = event.get("AlertName", "Unknown Alert")
        entity_caption = event.get("EntityCaption", "")
        name = f"{alert_name}: {entity_caption}" if entity_caption else alert_name

        return AlertDto(
            id=str(event.get("AlertActiveID", "")),
            name=name,
            status=status,
            severity=severity,
            lastReceived=last_received,
            description=event.get("TriggeredMessage")
            or event.get("AlertDescription")
            or "",
            source=["solarwinds"],
            url=url,
            alert_active_id=str(event.get("AlertActiveID", "")),
            alert_object_id=str(event.get("AlertObjectID", "")),
            alert_id=str(event.get("AlertID", "")),
            entity_caption=entity_caption,
            entity_type=event.get("EntityType", ""),
            related_node=event.get("RelatedNodeCaption", ""),
            acknowledged_by=event.get("AcknowledgedBy", ""),
            fingerprint=str(event.get("AlertActiveID", "")),
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

    if not host_url:
        raise Exception("SOLARWINDS_HOST_URL is not set")

    config = ProviderConfig(
        description="SolarWinds Provider",
        authentication={
            "host_url": host_url,
            "username": username,
            "password": password,
            "ssl_verify": False,
        },
    )

    provider = SolarwindsProvider(
        context_manager,
        provider_id="solarwinds",
        config=config,
    )

    alerts = provider._get_alerts()
    for alert in alerts:
        print(alert)
