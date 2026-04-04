"""
SolarWindsProvider integrates Keep with SolarWinds Orion/SWIS platform.
Supports pulling node/alert status via the SolarWinds Information Service (SWIS) API.
"""

import dataclasses
import logging
from datetime import datetime

import pydantic
import requests
from requests.auth import HTTPBasicAuth

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SolarWindsProviderAuthConfig:
    """
    SolarWinds Orion provider authentication configuration.
    Uses the SolarWinds Information Service (SWIS) REST API.
    Reference: https://github.com/solarwinds/OrionSDK/wiki/REST
    """

    hostname: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion server hostname or IP",
            "hint": "e.g. solarwinds.example.com or 192.168.1.10",
        }
    )
    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion username",
        }
    )
    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion password",
            "sensitive": True,
        }
    )
    port: int = dataclasses.field(
        default=17774,
        metadata={
            "required": False,
            "description": "SWIS API port (default: 17774)",
        },
    )
    verify_ssl: bool = dataclasses.field(
        default=False,
        metadata={
            "required": False,
            "description": "Verify SSL certificate (set to false for self-signed certs)",
        },
    )


class SolarWindsProvider(BaseProvider):
    """Get node/alert status from SolarWinds Orion into Keep."""

    PROVIDER_DISPLAY_NAME = "SolarWinds"
    PROVIDER_CATEGORY = ["Monitoring", "Network"]
    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="swis:query",
            description="Required to query SolarWinds SWQL API for alerts and node status",
            mandatory=True,
            mandatory_for_webhook=False,
            documentation_url="https://github.com/solarwinds/OrionSDK/wiki/REST",
            alias="Orion User",
        ),
    ]

    # SolarWinds alert/node status codes mapped to Keep
    SEVERITY_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "major": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "informational": AlertSeverity.INFO,
        "unknown": AlertSeverity.INFO,
        1: AlertSeverity.INFO,      # Up
        2: AlertSeverity.CRITICAL,  # Down
        3: AlertSeverity.WARNING,   # Warning
        14: AlertSeverity.HIGH,     # Critical
        15: AlertSeverity.HIGH,     # Unreachable
        16: AlertSeverity.WARNING,  # Shutdown
    }

    STATUS_MAP = {
        1: AlertStatus.RESOLVED,   # Up
        2: AlertStatus.FIRING,     # Down
        3: AlertStatus.FIRING,     # Warning
        14: AlertStatus.FIRING,    # Critical
        15: AlertStatus.FIRING,    # Unreachable
        16: AlertStatus.FIRING,    # Shutdown
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """Validates required configuration for SolarWinds provider."""
        self.authentication_config = SolarWindsProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    @property
    def __base_url(self):
        host = self.authentication_config.hostname
        port = self.authentication_config.port
        return f"https://{host}:{port}/SolarWinds/InformationService/v3/Json"

    @property
    def __auth(self):
        return HTTPBasicAuth(
            self.authentication_config.username,
            self.authentication_config.password,
        )

    def _swql_query(self, query: str) -> list[dict]:
        """Execute a SWQL query against the SolarWinds SWIS API."""
        url = f"{self.__base_url}/Query"
        payload = {"query": query}
        response = requests.post(
            url,
            auth=self.__auth,
            json=payload,
            verify=self.authentication_config.verify_ssl,
            timeout=20,
        )
        response.raise_for_status()
        return response.json().get("results", [])

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {scope.name: "Invalid" for scope in self.PROVIDER_SCOPES}
        try:
            self._swql_query("SELECT TOP 1 NodeID FROM Orion.Nodes")
            scopes["swis:query"] = True
        except Exception as e:
            scopes["swis:query"] = str(e)
        return scopes

    def get_alerts(self) -> list[AlertDto]:
        """Fetch active alerts and down nodes from SolarWinds Orion."""
        alerts = []

        # Fetch active alerts
        try:
            alert_rows = self._swql_query(
                """
                SELECT AlertID, Name, Severity, Message, AcknowledgedDateTime,
                       TriggeredDateTime, AlertActiveID, ObjectType, RelatedNodeCaption
                FROM Orion.AlertActive
                ORDER BY TriggeredDateTime DESC
                """
            )
            for row in alert_rows:
                alerts.append(self._format_active_alert(row))
        except Exception:
            self.logger.exception("Failed to fetch active alerts from SolarWinds")

        # Fetch down nodes (as supplemental)
        try:
            node_rows = self._swql_query(
                """
                SELECT NodeID, Caption, StatusDescription, Status,
                       LastBoot, ResponseTime, IPAddress
                FROM Orion.Nodes
                WHERE Status != 1
                ORDER BY Status
                """
            )
            for row in node_rows:
                alerts.append(self._format_node_alert(row))
        except Exception:
            self.logger.exception("Failed to fetch node status from SolarWinds")

        return alerts

    def _parse_ts(self, ts: str) -> str | None:
        if not ts:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(ts, fmt).isoformat()
            except Exception:
                continue
        return ts

    def _format_active_alert(self, row: dict) -> AlertDto:
        raw_severity = str(row.get("Severity", "warning")).lower()
        severity = self.SEVERITY_MAP.get(raw_severity, AlertSeverity.WARNING)
        acknowledged = row.get("AcknowledgedDateTime") is not None
        return AlertDto(
            id=str(row.get("AlertID", row.get("AlertActiveID", ""))),
            name=row.get("Name", "SolarWinds Alert"),
            status=AlertStatus.ACKNOWLEDGED if acknowledged else AlertStatus.FIRING,
            severity=severity,
            description=row.get("Message", ""),
            lastReceived=self._parse_ts(row.get("TriggeredDateTime")),
            source=["solarwinds"],
            acknowledged=acknowledged,
            object_type=row.get("ObjectType"),
            related_node=row.get("RelatedNodeCaption"),
            payload=row,
        )

    def _format_node_alert(self, row: dict) -> AlertDto:
        status_code = int(row.get("Status", 2))
        return AlertDto(
            id=f"node-{row.get('NodeID', 'unknown')}",
            name=f"Node {row.get('Caption', 'Unknown')} - {row.get('StatusDescription', 'Down')}",
            status=self.STATUS_MAP.get(status_code, AlertStatus.FIRING),
            severity=self.SEVERITY_MAP.get(status_code, AlertSeverity.CRITICAL),
            description=f"IP: {row.get('IPAddress', 'N/A')} | Response Time: {row.get('ResponseTime', 'N/A')}ms",
            source=["solarwinds"],
            host=row.get("Caption"),
            ip_address=row.get("IPAddress"),
            payload=row,
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "SolarWindsProvider" = None
    ) -> AlertDto:
        """
        Format a SolarWinds webhook notification into Keep AlertDto.
        SolarWinds can forward alerts via HTTP Actions in Alert Manager.
        """
        logger = logging.getLogger(__name__)
        logger.info("Formatting SolarWinds alert")

        raw_severity = str(event.get("Severity", event.get("severity", "warning"))).lower()
        severity = SolarWindsProvider.SEVERITY_MAP.get(raw_severity, AlertSeverity.WARNING)

        acknowledged = event.get("AcknowledgedDateTime") or event.get("Acknowledged")
        status = AlertStatus.ACKNOWLEDGED if acknowledged else AlertStatus.FIRING

        name = event.get("Name") or event.get("AlertName") or event.get("name") or "SolarWinds Alert"
        description = event.get("Message") or event.get("message") or ""

        triggered = event.get("TriggeredDateTime") or event.get("triggered_at")
        last_received = None
        if triggered:
            for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    last_received = datetime.strptime(triggered, fmt).isoformat()
                    break
                except Exception:
                    continue

        return AlertDto(
            id=str(event.get("AlertID") or event.get("id") or name),
            name=name,
            status=status,
            severity=severity,
            description=description,
            lastReceived=last_received,
            source=["solarwinds"],
            acknowledged=bool(acknowledged),
            node=event.get("RelatedNodeCaption") or event.get("node"),
            payload=event,
        )


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(tenant_id="keeptest", workflow_id="test")
    config = ProviderConfig(
        authentication={
            "hostname": os.environ.get("SOLARWINDS_HOST", "solarwinds.example.com"),
            "username": os.environ.get("SOLARWINDS_USER", "admin"),
            "password": os.environ.get("SOLARWINDS_PASS", ""),
            "port": 17774,
            "verify_ssl": False,
        }
    )
    provider = SolarWindsProvider(context_manager, "solarwinds-test", config)
    alerts = provider.get_alerts()
    print(f"Found {len(alerts)} alerts")
    for a in alerts:
        print(a)
