"""
SolarWinds Provider is a class that allows to ingest/digest data from SolarWinds Orion.
"""

import dataclasses
import datetime
import logging
import os
import random

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
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
            "description": "SolarWinds SWIS URL",
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
            "hint": "Password",
            "sensitive": True,
        }
    )
    verify: bool = dataclasses.field(
        metadata={
            "description": "Verify SSL certificates",
            "hint": "Set to false to allow self-signed certificates (common in SWIS)",
            "sensitive": False,
        },
        default=False,
    )


class SolarwindsProvider(BaseProvider):
    """
    Pull/Push alerts from SolarWinds into Keep.
    """

    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]

    SEVERITIES_MAP = {
        0: AlertSeverity.INFO,      # Informational
        1: AlertSeverity.WARNING,   # Warning
        2: AlertSeverity.CRITICAL,  # Critical
        3: AlertSeverity.HIGH,      # Serious
        4: AlertSeverity.INFO,      # Notice
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

    def _get_alerts(self) -> list[AlertDto]:
        # SolarWinds SWIS API query for active alerts
        url = f"{self.authentication_config.host_url}/SolarWinds/InformationService/v3/Json/Query"
        
        # Querying the Orion.AlertActive entity
        query = "SELECT AlertActiveID, AlertObjectID, Acknowledged, TriggeredDateTime, TriggeredMessage, ObjectName, RelatedNodeCaption, Severity FROM Orion.AlertActive"
        
        response = requests.get(
            url,
            params={"query": query},
            auth=(self.authentication_config.username, self.authentication_config.password),
            verify=self.authentication_config.verify,
        )
        
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        
        formatted_alerts = []
        for alert in results:
            alert_id = str(alert.get("AlertActiveID"))
            message = alert.get("TriggeredMessage", "SolarWinds Alert")
            severity_code = alert.get("Severity", 0)
            severity = self.SEVERITIES_MAP.get(severity_code, AlertSeverity.INFO)
            is_acknowledged = alert.get("Acknowledged", False)
            
            status = AlertStatus.ACKNOWLEDGED if is_acknowledged else AlertStatus.FIRING
            
            triggered_time = alert.get("TriggeredDateTime", "")
            try:
                # SWIS usually returns ISO format but with potential timezone issues
                last_received = datetime.datetime.fromisoformat(triggered_time.replace("Z", "+00:00")).isoformat()
            except Exception:
                last_received = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
                
            service = alert.get("RelatedNodeCaption") or alert.get("ObjectName") or "SolarWinds Node"

            formatted_alerts.append(
                AlertDto(
                    id=alert_id,
                    name=alert.get("ObjectName", message),
                    status=status,
                    lastReceived=last_received,
                    source=["solarwinds"],
                    message=message,
                    severity=severity,
                    environment="unknown",
                    service=service,
                    hostname=alert.get("RelatedNodeCaption", ""),
                )
            )
        return formatted_alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        # Standard format for SolarWinds alerts coming from webhooks
        return AlertDto(
            id=event.get("AlertID", str(random.randint(1000, 9999))),
            name=event.get("AlertName", "SolarWinds Alert"),
            status=AlertStatus.FIRING,
            lastReceived=datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            source=["solarwinds"],
            message=event.get("Message", ""),
            severity=SolarwindsProvider.SEVERITIES_MAP.get(event.get("Severity", 0), AlertSeverity.INFO),
            environment="unknown",
            hostname=event.get("NodeName", ""),
            service=event.get("NodeName", ""),
        )

if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    
    # Simple test with dummy config
    provider_config = {
        "authentication": {
            "host_url": "https://localhost:17778",
            "username": "admin",
            "password": "password",
            "verify": False
        },
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="solarwinds",
        provider_type="solarwinds",
        provider_config=provider_config,
    )
    print("Provider initialized successfully")
