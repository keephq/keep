"""
SolarWinds Orion Provider is a class that allows to ingest/digest data from SolarWinds.
"""

import dataclasses
import datetime
import logging
from typing import Union

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SolarWindsProviderAuthConfig:
    """
    SolarWinds Orion authentication configuration.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion Web Console URL",
            "hint": "https://solarwinds.example.com",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Username",
            "hint": "admin",
            "sensitive": False,
        }
    )
    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Password",
            "hint": "********",
            "sensitive": True,
        }
    )
    verify_ssl: bool = dataclasses.field(
        metadata={
            "description": "Verify SSL certificates",
            "hint": "Set to false for self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )


class SolarWindsProvider(BaseProvider):
    """
    Pull alerts from SolarWinds Orion into Keep.
    """

    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_DISPLAY_NAME = "SolarWinds"
    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read",
            description="Read access to SolarWinds alerts and events",
            mandatory=True,
            mandatory_for_webhook=True,
        ),
    ]

    # SolarWinds Orion alert severity mapping
    SEVERITY_MAP = {
        0: AlertSeverity.LOW,       # Informational
        1: AlertSeverity.WARNING,   # Warning
        2: AlertSeverity.CRITICAL,  # Critical
        3: AlertSeverity.HIGH,      # Serious
        4: AlertSeverity.LOW,       # Notice
    }

    STATUS_MAP = {
        "Active": AlertStatus.FIRING,
        "Acknowledged": AlertStatus.ACKNOWLEDGED,
        "Resolved": AlertStatus.RESOLVED,
        "None": AlertStatus.PENDING,
    }

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self._host_url = self.config.authentication.get("host_url", "").rstrip("/")
        self._username = self.config.authentication.get("username", "")
        self._password = self.config.authentication.get("password", "")
        self._verify = self.config.authentication.get("verify_ssl", True)
        self._session = None

    def dispose(self):
        if self._session:
            self._session.close()

    def validate_config(self):
        self.authentication_config = SolarWindsProviderAuthConfig(
            **self.config.authentication
        )

    def _get_session(self) -> requests.Session:
        """Get or create authenticated session."""
        if self._session is None:
            self._session = requests.Session()
            self._session.auth = (self._username, self._password)
            self._session.verify = self._verify
            self._session.headers.update({
                "Content-Type": "application/json",
                "Accept": "application/json",
            })
        return self._session

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            session = self._get_session()
            # Try to query the SWIS API
            response = session.get(
                f"{self._host_url}/SolarWinds/InformationService/v3/Json/Query",
                params={"query": "SELECT TOP 1 AccountID FROM Orion.Accounts"},
                timeout=10,
            )
            if response.status_code == 200:
                return {"read": True}
            return {"read": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"read": str(e)}

    def _query_swis(self, query: str) -> list[dict]:
        """Execute a SWIS query."""
        session = self._get_session()
        response = session.get(
            f"{self._host_url}/SolarWinds/InformationService/v3/Json/Query",
            params={"query": query},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])

    @staticmethod
    def _convert_severity(level: int) -> AlertSeverity:
        """Convert SolarWinds severity level to Keep severity."""
        return SolarWindsProvider.SEVERITY_MAP.get(level, AlertSeverity.HIGH)

    @staticmethod
    def _convert_status(status: str) -> AlertStatus:
        """Convert SolarWinds status to Keep alert status."""
        return SolarWindsProvider.STATUS_MAP.get(status, AlertStatus.PENDING)

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull active alerts from SolarWinds Orion.
        """
        alerts = []

        # Fetch active alerts using SWIS
        try:
            alert_data = self._query_swis(
                "SELECT AlertActiveID, AlertDefID, Name, Severity, "
                "Status, TimeStamp, ObjectType, ObjectName, "
                "AlertMessage, TriggeredMessage "
                "FROM Orion.AlertActive "
                "ORDER BY TimeStamp DESC"
            )

            for item in alert_data:
                alert_id = str(item.get("AlertActiveID", ""))
                name = item.get("Name", "Unknown Alert")
                severity = item.get("Severity", 2)
                status = item.get("Status", "Active")
                message = item.get("AlertMessage", "") or item.get("TriggeredMessage", "")
                timestamp = item.get("TimeStamp", "")
                object_name = item.get("ObjectName", "")

                # Parse timestamp
                last_received = datetime.datetime.utcnow().isoformat()
                if timestamp:
                    try:
                        # SolarWinds returns ISO format
                        last_received = timestamp
                    except Exception:
                        pass

                alert = AlertDto(
                    id=f"solarwinds:{alert_id}",
                    name=name,
                    status=self._convert_status(status),
                    severity=self._convert_severity(severity),
                    lastReceived=last_received,
                    source=["solarwinds"],
                    message=message or f"Alert: {name}",
                    description=message or name,
                    fingerprints=[f"solarwinds:{alert_id}"],
                )
                alerts.append(alert)

        except Exception as e:
            logger.error(f"Error fetching SolarWinds alerts: {e}")

        # Also fetch recent events
        try:
            event_data = self._query_swis(
                "SELECT TOP 50 EventID, EventTime, EventType, "
                "Message, NodeID, NetworkNode, "
                "ObjectName, Severity "
                "FROM Orion.Events "
                "WHERE Acknowledged IS NULL "
                "ORDER BY EventTime DESC"
            )

            for event in event_data:
                event_id = str(event.get("EventID", ""))
                message = event.get("Message", "")
                severity = event.get("Severity", 2)
                event_time = event.get("EventTime", "")

                alert = AlertDto(
                    id=f"solarwinds:event:{event_id}",
                    name=f"SolarWinds Event: {message[:80]}",
                    status=AlertStatus.FIRING,
                    severity=self._convert_severity(severity),
                    lastReceived=event_time or datetime.datetime.utcnow().isoformat(),
                    source=["solarwinds"],
                    message=message,
                    description=message,
                    fingerprints=[f"solarwinds:event:{event_id}"],
                )
                alerts.append(alert)

        except Exception as e:
            logger.warning(f"Could not fetch SolarWinds events: {e}")

        return alerts


if __name__ == "__main__":
    import os

    config = ProviderConfig(
        authentication={
            "host_url": os.environ.get("SOLARWINDS_HOST", "https://solarwinds.example.com"),
            "username": os.environ.get("SOLARWINDS_USER", "admin"),
            "password": os.environ.get("SOLARWINDS_PASS", ""),
        }
    )

    context_manager = ContextManager(tenant_id="test", workflow_id="test")
    provider = SolarWindsProvider(context_manager, "solarwinds-test", config)

    scopes = provider.validate_scopes()
    print(f"Scopes: {scopes}")

    if scopes.get("read"):
        alerts = provider.get_alerts()
        print(f"Found {len(alerts)} alerts:")
        for alert in alerts:
            print(f"  [{alert.severity}] {alert.name}")
