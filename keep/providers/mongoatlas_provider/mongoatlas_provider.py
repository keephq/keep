import dataclasses
import datetime
import logging
import typing

import pydantic
import requests
from requests.auth import HTTPDigestAuth

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

@pydantic.dataclasses.dataclass
class MongoatlasProviderAuthConfig:
    public_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "MongoDB Atlas Public API Key",
        }
    )
    private_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "MongoDB Atlas Private API Key",
            "sensitive": True,
        }
    )
    group_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "MongoDB Atlas Group (Project) ID",
        }
    )

class MongoatlasProvider(BaseProvider):
    """Pull alerts from MongoDB Atlas."""

    PROVIDER_DISPLAY_NAME = "MongoDB Atlas"
    PROVIDER_CATEGORY = ["Monitoring"]
    
    # Atlas API v1.0 / v2.0
    BASE_URL = "https://cloud.mongodb.com/api/public/v1.0"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MongoatlasProviderAuthConfig(
            **self.config.authentication
        )

    def _get_alerts(self, status: str = "OPEN") -> list[AlertDto]:
        """
        Pull alerts from MongoDB Atlas for the configured group.
        """
        url = f"{self.BASE_URL}/groups/{self.authentication_config.group_id}/alerts"
        params = {"status": status}
        
        try:
            response = requests.get(
                url,
                params=params,
                auth=HTTPDigestAuth(
                    self.authentication_config.public_key,
                    self.authentication_config.private_key
                )
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            self.logger.exception(f"Failed to pull alerts from MongoDB Atlas: {e}")
            return []
        
        alerts = []
        for alert in data.get("results", []):
            alerts.append(self._format_alert(alert))
        return alerts

    def _format_alert(self, alert: dict) -> AlertDto:
        # Map Atlas severity to Keep severity
        # Atlas: INFORMATIONAL, WARNING, CRITICAL
        severity_map = {
            "INFORMATIONAL": AlertSeverity.LOW,
            "WARNING": AlertSeverity.WARNING,
            "CRITICAL": AlertSeverity.CRITICAL,
        }
        
        # Map Atlas status to Keep status
        # Atlas: OPEN, CLOSED, TRACKING
        status_map = {
            "OPEN": AlertStatus.FIRING,
            "CLOSED": AlertStatus.RESOLVED,
            "TRACKING": AlertStatus.PENDING,
        }

        return AlertDto(
            id=alert.get("id"),
            name=alert.get("eventTypeName", "MongoAtlas Alert"),
            status=status_map.get(alert.get("status"), AlertStatus.FIRING),
            severity=severity_map.get(alert.get("severity"), AlertSeverity.INFO),
            last_received=alert.get("created", datetime.datetime.now().isoformat()),
            description=alert.get("description", ""),
            source=["mongoatlas"],
            # Include more metadata if needed
            eventTypeName=alert.get("eventTypeName"),
            targetName=alert.get("targetName"),
            clusterName=alert.get("clusterName"),
        )

    def setup_webhook(self, tenant_id: str, callback_url: str, event_type: str = None, **kwargs):
        # Optional: Implement Atlas Webhook integration
        pass

if __name__ == "__main__":
    # Test stub
    pass
