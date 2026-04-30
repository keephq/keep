"""
SolarWinds Provider is a class that allows to ingest/digest data from SolarWinds Orion Platform.
"""

import dataclasses
import logging
from datetime import datetime
from typing import List, Optional

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
    SolarWinds Orion authentication configuration.
    """

    orion_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion Server URL",
            "hint": "https://orion.example.com:17778",
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


class SolarwindsProvider(BaseProvider):
    """
    Pull/Push alerts from SolarWinds Orion into Keep.
    """

    PROVIDER_DISPLAY_NAME = "SolarWinds"
    PROVIDER_CATEGORY = ["Monitoring"]
    
    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated to SolarWinds Orion API",
            mandatory=True,
            documentation_url="https://documentation.solarwinds.com/",
        ),
    ]
    
    # SolarWinds severity levels mapping
    SEVERITIES_MAP = {
        0: AlertSeverity.INFO,      # Informational
        1: AlertSeverity.WARNING,   # Warning
        2: AlertSeverity.CRITICAL,  # Critical
        3: AlertSeverity.HIGH,      # Serious
        "Down": AlertSeverity.CRITICAL,
        "Critical": AlertSeverity.CRITICAL,
        "Warning": AlertSeverity.WARNING,
        "Up": AlertSeverity.LOW,
        "Unknown": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        0: AlertStatus.RESOLVED,    # Up/OK
        1: AlertStatus.FIRING,      # Down
        2: AlertStatus.FIRING,      # Warning
        3: AlertStatus.FIRING,      # Critical
        "Acknowledged": AlertStatus.ACKNOWLEDGED,
        "Active": AlertStatus.FIRING,
        "Resolved": AlertStatus.RESOLVED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._session = None

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate that we can authenticate with SolarWinds Orion."""
        scopes = {}
        try:
            self._get_session()
            self._query("SELECT TOP 1 NodeID FROM Orion.Nodes")
            scopes["authenticated"] = True
        except Exception as e:
            scopes["authenticated"] = str(e)
        return scopes

    def validate_config(self):
        """Validate the provider configuration."""
        self.authentication_config = SolarwindsProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """Dispose of the provider."""
        self._session = None

    def _get_session(self) -> requests.Session:
        """Get or create an authenticated session."""
        if self._session is None:
            self._session = requests.Session()
            self._session.auth = (
                self.authentication_config.username,
                self.authentication_config.password,
            )
            self._session.verify = self.authentication_config.verify_ssl
            self._session.headers.update({
                "Content-Type": "application/json",
            })
        return self._session

    def _get_api_url(self, endpoint: str) -> str:
        """Build the full API URL."""
        base_url = str(self.authentication_config.orion_url).rstrip("/")
        return f"{base_url}/SolarWinds/InformationService/v3/Json/{endpoint}"

    def _query(self, swql: str) -> dict:
        """Execute a SWQL query against the SolarWinds API."""
        session = self._get_session()
        url = self._get_api_url("Query")
        
        response = session.post(
            url,
            json={"query": swql},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _get_alerts(self) -> List[AlertDto]:
        """Get all active alerts from SolarWinds Orion."""
        alerts = []
        
        # Query for active alerts
        swql = """
        SELECT 
            AlertActiveID,
            AlertObjectID,
            EntityCaption,
            EntityDetailsUrl,
            AlertMessage,
            TriggeredDateTime,
            Severity,
            Acknowledged,
            AcknowledgedBy,
            AcknowledgedDateTime,
            AlertName,
            ObjectType
        FROM Orion.AlertActive
        """
        
        try:
            result = self._query(swql)
            for alert in result.get("results", []):
                alerts.append(self._format_alert_from_query(alert))
        except Exception as e:
            logger.warning(f"Failed to get alerts: {e}")

        return alerts

    def _format_alert_from_query(self, alert: dict) -> AlertDto:
        """Format a SolarWinds alert query result as an AlertDto."""
        severity_val = alert.get("Severity", 0)
        severity = self.SEVERITIES_MAP.get(severity_val, AlertSeverity.INFO)
        
        acknowledged = alert.get("Acknowledged", False)
        status = AlertStatus.ACKNOWLEDGED if acknowledged else AlertStatus.FIRING
        
        return AlertDto(
            id=f"solarwinds-{alert.get('AlertActiveID', '')}",
            name=alert.get("AlertName", "SolarWinds Alert"),
            description=alert.get("AlertMessage", ""),
            severity=severity,
            status=status,
            source=["solarwinds"],
            host=alert.get("EntityCaption"),
            url=alert.get("EntityDetailsUrl"),
            lastReceived=alert.get("TriggeredDateTime"),
            fingerprint=f"solarwinds-{alert.get('AlertObjectID', '')}",
            acknowledgedBy=alert.get("AcknowledgedBy"),
            acknowledgedAt=alert.get("AcknowledgedDateTime"),
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: Optional["SolarwindsProvider"] = None
    ) -> AlertDto:
        """Format a SolarWinds webhook event as an AlertDto."""
        # Webhook payload from SolarWinds Alert Action
        alert_name = event.get("AlertName", event.get("alertName", "SolarWinds Alert"))
        entity = event.get("ObjectName", event.get("EntityCaption", "Unknown"))
        message = event.get("AlertMessage", event.get("Message", ""))
        severity_str = event.get("Severity", "Warning")
        acknowledged = event.get("Acknowledged", False)
        
        severity = SolarwindsProvider.SEVERITIES_MAP.get(severity_str, AlertSeverity.WARNING)
        status = AlertStatus.ACKNOWLEDGED if acknowledged else AlertStatus.FIRING
        
        # Check if this is a reset/resolved alert
        if event.get("AlertStatus") == "Reset" or event.get("TriggeredMessage", "").lower().startswith("reset"):
            status = AlertStatus.RESOLVED
            severity = AlertSeverity.LOW

        alert_id = event.get("AlertActiveID", event.get("AlertObjectID", f"{alert_name}-{entity}"))
        
        return AlertDto(
            id=f"solarwinds-{alert_id}",
            name=f"{alert_name}: {entity}",
            description=message,
            severity=severity,
            status=status,
            source=["solarwinds"],
            host=entity,
            fingerprint=f"solarwinds-{alert_id}",
            lastReceived=event.get("TriggeredDateTime"),
        )

    def _get_alerts_from_api(self) -> List[AlertDto]:
        """Pull alerts from SolarWinds Orion API."""
        return self._get_alerts()

    def acknowledge_alert(self, alert_id: str, note: str = "Acknowledged via Keep") -> bool:
        """Acknowledge an alert in SolarWinds."""
        try:
            # Extract the AlertActiveID from the alert_id
            active_id = alert_id.replace("solarwinds-", "")
            
            url = self._get_api_url("Invoke/Orion.AlertActive/Acknowledge")
            session = self._get_session()
            
            response = session.post(
                url,
                json=[active_id, note],
                timeout=30,
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to acknowledge alert {alert_id}: {e}")
            return False


ProvidersFactory.register_provider(SolarwindsProvider)
