"""
SolarWinds is a class that provides methods to interact with the SolarWinds API and parse webhook alerts.
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
class SolarWindsProviderAuthConfig:
    """
    SolarWindsProviderAuthConfig holds the authentication information for the SolarWindsProvider.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion Host URL (e.g. https://solarwinds.example.com)",
            "sensitive": False,
            "validation": "any_http_url",
        },
    )

    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Username",
            "sensitive": False,
        },
        default=None,
    )

    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Password",
            "sensitive": True,
        },
        default=None,
    )


class SolarWindsProvider(BaseProvider):
    """Receive alerts from SolarWinds Orion via webhooks and optionally pull from the SWIS API."""

    PROVIDER_DISPLAY_NAME = "SolarWinds"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(name="authenticated", description="User is authenticated"),
    ]
    FINGERPRINT_FIELDS = ["id"]

    # SolarWinds severity levels mapped to Keep AlertSeverity
    SEVERITY_MAP = {
        "CRITICAL": AlertSeverity.CRITICAL,
        "WARNING": AlertSeverity.WARNING,
        "WARNING_ALERT": AlertSeverity.WARNING,
        "OK": AlertSeverity.INFO,
        "INFORMATIONAL": AlertSeverity.INFO,
        "INFO": AlertSeverity.INFO,
        "UNKNOWN": AlertSeverity.INFO,
    }

    # SolarWinds status mapped to Keep AlertStatus
    STATUS_MAP = {
        "ACTIVE": AlertStatus.FIRING,
        "DOWN": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "WARNING": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
        "ACKNOWLEDGED": AlertStatus.ACKNOWLEDGED,
        "RESOLVED": AlertStatus.RESOLVED,
        "UP": AlertStatus.RESOLVED,
        "RECOVERED": AlertStatus.RESOLVED,
        "OK": AlertStatus.RESOLVED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """
        Validates the configuration of the SolarWinds provider.
        """
        self.authentication_config = SolarWindsProviderAuthConfig(
            **self.config.authentication
        )

    def __get_url(self, path: str = "") -> str:
        base = str(self.authentication_config.host_url).rstrip("/")
        if path:
            return f"{base}{path}"
        return base

    def __get_headers(self):
        return {
            "Content-Type": "application/json",
        }

    def __get_auth(self):
        return (
            self.authentication_config.username,
            self.authentication_config.password,
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate the scopes of the provider by querying the SWIS API.
        """
        try:
            # SolarWinds SWIS REST endpoint for a lightweight health check
            url = self.__get_url("/SolarWinds/InformationService/v3/Json/Query")
            params = {"query": "SELECT TOP 1 Name FROM Orion.Nodes"}
            response = requests.get(
                url,
                headers=self.__get_headers(),
                auth=self.__get_auth(),
                params=params,
                verify=False,
                timeout=30,
            )
            if response.ok:
                scopes = {"authenticated": True}
            else:
                scopes = {
                    "authenticated": f"Error validating scopes: {response.status_code} {response.text}"
                }
        except Exception as e:
            scopes = {
                "authenticated": f"Error validating scopes: {e}",
            }

        return scopes

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: BaseProvider = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format incoming SolarWinds webhook payload into Keep AlertDto.

        Expected SolarWinds webhook fields:
        - alert_id / id: unique alert identifier
        - alert_name / name: alert name
        - node_name / host: affected host/node
        - severity: CRITICAL, WARNING, INFORMATIONAL, etc.
        - status: ACTIVE, ACKNOWLEDGED, RESOLVED, etc.
        - message / description: alert details
        - timestamp / last_received: ISO timestamp
        """
        alert_id = event.get("alert_id") or event.get("id") or event.get("AlertID")
        name = (
            event.get("alert_name")
            or event.get("name")
            or event.get("AlertName")
            or "SolarWinds Alert"
        )
        host = (
            event.get("node_name")
            or event.get("host")
            or event.get("NodeName")
            or event.get("Hostname")
            or ""
        )
        severity_str = (
            event.get("severity")
            or event.get("Severity")
            or event.get("alert_severity")
            or "UNKNOWN"
        )
        status_str = (
            event.get("status")
            or event.get("Status")
            or event.get("alert_status")
            or "ACTIVE"
        )
        description = (
            event.get("message")
            or event.get("description")
            or event.get("Message")
            or event.get("AlertMessage")
            or ""
        )
        last_received = (
            event.get("timestamp")
            or event.get("last_received")
            or event.get("Timestamp")
            or event.get("AlertTriggerTime")
            or datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        )

        # Map severity and status
        severity = SolarWindsProvider.SEVERITY_MAP.get(
            str(severity_str).upper(), AlertSeverity.INFO
        )
        status = SolarWindsProvider.STATUS_MAP.get(
            str(status_str).upper(), AlertStatus.FIRING
        )

        return AlertDto(
            id=alert_id,
            name=name,
            description=description,
            severity=severity,
            status=status,
            host=host,
            source=["solarwinds"],
            lastReceived=last_received,
            # Pass through any extra fields for enrichment
            **{
                k: v
                for k, v in event.items()
                if k
                not in {
                    "alert_id",
                    "id",
                    "alert_name",
                    "name",
                    "node_name",
                    "host",
                    "severity",
                    "Severity",
                    "alert_severity",
                    "status",
                    "Status",
                    "alert_status",
                    "message",
                    "description",
                    "Message",
                    "AlertMessage",
                    "timestamp",
                    "last_received",
                    "Timestamp",
                    "AlertTriggerTime",
                }
            },
        )

    def _query(self, **kwargs: dict) -> list[AlertDto]:
        """
        Query method alias for pulling alerts from SolarWinds.
        """
        return self._get_alerts(**kwargs)

    def _get_alerts(self, **kwargs: dict) -> list[AlertDto]:
        """
        Pull active alerts from SolarWinds via the SWIS API.
        """
        alerts = []
        try:
            self.logger.info("Collecting active alerts from SolarWinds")
            url = self.__get_url("/SolarWinds/InformationService/v3/Json/Query")
            # SWQL query for active alerts from Orion.AlertActive
            query = kwargs.get(
                "query",
                "SELECT TOP 100 AlertID, AlertName, NodeName, Severity, ObjectName, "
                "AlertMessage, AlertTriggerTime, AlertDescription, Acknowledged "
                "FROM Orion.AlertActive ORDER BY AlertTriggerTime DESC",
            )
            response = requests.get(
                url,
                headers=self.__get_headers(),
                auth=self.__get_auth(),
                params={"query": query},
                verify=False,
                timeout=60,
            )

            if not response.ok:
                self.logger.error(
                    "Failed to get alerts from SolarWinds: %s %s",
                    response.status_code,
                    response.text,
                )
                raise ProviderException("Failed to get alerts from SolarWinds")

            data = response.json()
            results = data.get("results", data if isinstance(data, list) else [])

            for alert in results:
                if not isinstance(alert, dict):
                    continue
                severity_str = str(alert.get("Severity", "UNKNOWN")).upper()
                status_str = (
                    "ACKNOWLEDGED"
                    if alert.get("Acknowledged")
                    else "ACTIVE"
                )
                alerts.append(
                    AlertDto(
                        id=str(alert.get("AlertID", "")),
                        name=alert.get("AlertName", "SolarWinds Alert"),
                        description=alert.get(
                            "AlertMessage",
                            alert.get("AlertDescription", ""),
                        ),
                        severity=SolarWindsProvider.SEVERITY_MAP.get(
                            severity_str, AlertSeverity.INFO
                        ),
                        status=SolarWindsProvider.STATUS_MAP.get(
                            status_str, AlertStatus.FIRING
                        ),
                        host=alert.get("NodeName", alert.get("ObjectName", "")),
                        source=["solarwinds"],
                        lastReceived=alert.get(
                            "AlertTriggerTime",
                            datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
                        ),
                        acknowledged=alert.get("Acknowledged", False),
                    )
                )
        except Exception as e:
            self.logger.error("Error getting alerts from SolarWinds: %s", e)
            raise ProviderException(f"Error getting alerts from SolarWinds: {e}") from e

        return alerts


if __name__ == "__main__":
    import logging
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

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
        },
    )

    provider = SolarWindsProvider(
        context_manager,
        provider_id="solarwinds",
        config=config,
    )

    provider._get_alerts()
