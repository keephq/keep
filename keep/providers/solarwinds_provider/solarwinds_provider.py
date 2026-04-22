"""
SolarWinds Provider is a class that allows to pull alerts from SolarWinds via the SWIS API.
"""

import dataclasses
import datetime
import logging

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SolarwindsProviderAuthConfig:
    """
    SolarWinds authentication configuration.
    """

    hostname: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds server hostname or IP address",
            "hint": "solarwinds.example.com",
        },
    )
    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds username",
            "hint": "admin",
        },
    )
    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds password",
            "sensitive": True,
        },
    )
    port: int = dataclasses.field(
        default=17778,
        metadata={
            "required": False,
            "description": "SolarWinds SWIS API port",
            "hint": "17778 (default REST port)",
        },
    )
    use_https: bool = dataclasses.field(
        default=True,
        metadata={
            "required": False,
            "description": "Use HTTPS for the connection",
            "hint": "True",
        },
    )


class SolarwindsProvider(BaseProvider):
    """
    Pull alerts from SolarWinds NPM/NCM via the SWIS REST API.
    """

    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_DISPLAY_NAME = "SolarWinds"
    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated and can query SolarWinds",
            mandatory=True,
            mandatory_for_webhook=False,
            alias="Authenticated",
        ),
    ]
    PROVIDER_TAGS = ["alert"]

    # SolarWinds severity mapping
    # SolarWinds alert severity levels: Critical, Warning, Informational, Notice
    SEVERITY_MAP = {
        "Critical": AlertSeverity.CRITICAL,
        "Warning": AlertSeverity.WARNING,
        "Informational": AlertSeverity.INFO,
        "Notice": AlertSeverity.INFO,
        "High": AlertSeverity.HIGH,
        "Medium": AlertSeverity.WARNING,
        "Low": AlertSeverity.LOW,
    }

    # SolarWinds alert status mapping
    # SolarWinds active alerts are "Active" (firing), otherwise resolved
    STATUS_MAP = {
        "Active": AlertStatus.FIRING,
        "Acknowledged": AlertStatus.ACKNOWLEDGED,
        "Resolved": AlertStatus.RESOLVED,
        "Cleared": AlertStatus.RESOLVED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider. No cleanup needed.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for SolarWinds provider.
        """
        self.authentication_config = SolarwindsProviderAuthConfig(
            **self.config.authentication
        )

    def _get_swis_url(self) -> str:
        """Build the base SWIS REST API URL."""
        scheme = "https" if self.authentication_config.use_https else "http"
        hostname = self.authentication_config.hostname
        port = self.authentication_config.port
        return f"{scheme}://{hostname}:{port}/SolarWinds/InformationService/v3/Json"

    def _get_session(self) -> requests.Session:
        """Create an authenticated requests session."""
        session = requests.Session()
        session.auth = (
            self.authentication_config.username,
            self.authentication_config.password,
        )
        session.verify = self.authentication_config.use_https
        session.headers.update({"Content-Type": "application/json"})
        return session

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate that the SolarWinds credentials work by querying alerts.
        """
        scopes = {}
        try:
            session = self._get_session()
            url = self._get_swis_url()
            # Try a simple SWQL query to verify connectivity and auth
            query = {
                "query": "SELECT TOP 1 AlertActiveID FROM Orion.AlertActive"
            }
            response = session.post(f"{url}/Query", json=query)
            if response.ok:
                scopes["authenticated"] = True
            elif response.status_code in (401, 403):
                scopes["authenticated"] = (
                    f"Authentication failed: {response.status_code} {response.text}"
                )
            else:
                scopes["authenticated"] = (
                    f"Unexpected response: {response.status_code} {response.text}"
                )
        except Exception as e:
            scopes["authenticated"] = f"Connection error: {e}"
            self.logger.exception("Error validating SolarWinds scopes")
        return scopes

    def _query_alerts(self, swql: str) -> list[dict]:
        """
        Execute a SWQL query against the SolarWinds SWIS API and return results.
        """
        session = self._get_session()
        url = self._get_swis_url()
        payload = {"query": swql}
        response = session.post(f"{url}/Query", json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull active and recent alerts from SolarWinds and convert to Keep format.
        """
        alerts = []

        # Get active alerts with detailed info
        active_swql = """
        SELECT
            AlertActive.AlertActiveID AS AlertID,
            AlertDefinitions.Name AS AlertName,
            AlertActive.TriggeredDateTime AS TriggeredAt,
            AlertActive.TriggeredMessage AS TriggerMessage,
            AlertActive.AcknowledgedDateTime AS AcknowledgedAt,
            AlertActive.Acknowledged AS IsAcknowledged,
            AlertActive.ObjectType AS ObjectType,
            AlertActive.NetObjectID AS NetObjectID,
            AlertActive.NetObjectHint AS NetObjectHint,
            Nodes.Caption AS NodeCaption,
            Nodes.NodeID AS NodeID,
            Nodes.IP_Address AS NodeIP,
            Nodes.Status AS RawNodeStatus
        FROM Orion.AlertActive AlertActive
        LEFT JOIN Orion.Nodes Nodes ON AlertActive.NetObjectID = Nodes.NodeID
        WHERE AlertActive.ObjectType = 'Node'
        """

        try:
            self.logger.info("Collecting active alerts from SolarWinds")
            active_results = self._query_alerts(active_swql)
            for row in active_results:
                try:
                    severity = self.SEVERITY_MAP.get(
                        row.get("ObjectType", ""), AlertSeverity.INFO
                    )
                    # Try to infer severity from node status
                    raw_node_status = row.get("RawNodeStatus")
                    if raw_node_status is not None:
                        # SolarWinds node status: 1=Up, 2=Down, 9=Warning
                        try:
                            status_int = int(raw_node_status)
                            if status_int == 2:
                                severity = AlertSeverity.CRITICAL
                            elif status_int == 9:
                                severity = AlertSeverity.WARNING
                            elif status_int == 1:
                                severity = AlertSeverity.INFO
                        except (ValueError, TypeError):
                            pass

                    status = AlertStatus.FIRING
                    if row.get("IsAcknowledged"):
                        status = AlertStatus.ACKNOWLEDGED

                    node_name = row.get("NodeCaption") or row.get("NetObjectHint") or "Unknown Node"
                    node_ip = row.get("NodeIP") or ""

                    alert = AlertDto(
                        id=str(row.get("AlertID", "")),
                        name=row.get("AlertName", "SolarWinds Alert"),
                        description=row.get("TriggerMessage", "") or f"Alert triggered on {node_name}",
                        status=status,
                        severity=severity,
                        lastReceived=row.get("TriggeredAt", datetime.datetime.now(tz=datetime.timezone.utc).isoformat()),
                        source=["solarwinds"],
                        fingerprint=str(row.get("AlertID", "")),
                        environment="production",
                        service=node_name,
                        url=f"https://{self.authentication_config.hostname}/Orion/NetPerfMon/NodeDetails.aspx?NetObject=N:{row.get('NodeID', '')}" if self.authentication_config.use_https else f"http://{self.authentication_config.hostname}/Orion/NetPerfMon/NodeDetails.aspx?NetObject=N:{row.get('NodeID', '')}",
                    )
                    alerts.append(alert)
                except Exception as e:
                    self.logger.warning(
                        f"Failed to parse SolarWinds active alert: {e}",
                        exc_info=True,
                    )
        except Exception as e:
            self.logger.error(f"Failed to get active alerts from SolarWinds: {e}")

        # Get recently resolved alerts
        resolved_swql = """
        SELECT TOP 100
            AlertActiveID AS AlertID,
            AlertName,
            TriggeredMessage,
            TriggeredAt,
            ResolvedAt,
            ObjectType,
            NodeCaption,
            NodeIP
        FROM Orion.AlertHistory
        WHERE EventType = 2
        ORDER BY TimeStamp DESC
        """
        # Try to get resolved alerts - this uses a simplified query
        # since AlertHistory schema may vary across SolarWinds versions
        resolved_swql_simple = """
        SELECT TOP 100
            AlertActiveID AS AlertID,
            AlertName,
            TriggeredMessage,
            TriggeredAt,
            ResolvedAt
        FROM Orion.AlertHistory
        WHERE EventType = 2
        ORDER BY TimeStamp DESC
        """
        try:
            self.logger.info("Collecting resolved alerts from SolarWinds")
            resolved_results = self._query_alerts(resolved_swql_simple)
            for row in resolved_results:
                try:
                    severity = self.SEVERITY_MAP.get(
                        row.get("ObjectType", ""), AlertSeverity.INFO
                    )
                    alert = AlertDto(
                        id=str(row.get("AlertID", "")),
                        name=row.get("AlertName", "SolarWinds Resolved Alert"),
                        description=row.get("TriggerMessage", "") or "Alert resolved",
                        status=AlertStatus.RESOLVED,
                        severity=severity,
                        lastReceived=row.get("ResolvedAt") or row.get("TriggeredAt", datetime.datetime.now(tz=datetime.timezone.utc).isoformat()),
                        source=["solarwinds"],
                        fingerprint=str(row.get("AlertID", "")),
                        environment="production",
                    )
                    alerts.append(alert)
                except Exception as e:
                    self.logger.warning(
                        f"Failed to parse SolarWinds resolved alert: {e}",
                        exc_info=True,
                    )
        except Exception as e:
            self.logger.error(f"Failed to get resolved alerts from SolarWinds: {e}")

        return alerts

    @staticmethod
    def _format_alert(event: dict, provider_instance: "BaseProvider" = None) -> AlertDto:
        """
        Format a SolarWinds webhook alert into a Keep AlertDto.

        This method is used for push/webhook alerts from SolarWinds.
        """
        severity = SolarwindsProvider.SEVERITY_MAP.get(
            event.get("Severity", ""), AlertSeverity.INFO
        )
        status = SolarwindsProvider.STATUS_MAP.get(
            event.get("Status", ""), AlertStatus.FIRING
        )

        return AlertDto(
            id=event.get("AlertID", ""),
            name=event.get("AlertName", "SolarWinds Alert"),
            description=event.get("Message", ""),
            status=status,
            severity=severity,
            lastReceived=event.get("TriggeredAt", datetime.datetime.now(tz=datetime.timezone.utc).isoformat()),
            source=["solarwinds"],
            environment=event.get("Environment", "production"),
            service=event.get("NodeName", ""),
            url=event.get("Url", ""),
        )