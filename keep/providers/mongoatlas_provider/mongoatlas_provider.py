import dataclasses
import datetime
import logging
from typing import Optional

import pydantic
import requests
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class MongoAtlasProviderAuthConfig:
    public_key: str = dataclasses.field(
        metadata={"required": True, "description": "MongoDB Atlas Public Key"}
    )
    private_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "MongoDB Atlas Private Key",
            "sensitive": True,
        }
    )
    project_id: str = dataclasses.field(
        metadata={"required": True, "description": "MongoDB Atlas Project ID"}
    )


class MongoAtlasProvider(BaseProvider):
    """Pull alerts from MongoDB Atlas."""

    PROVIDER_DISPLAY_NAME = "MongoDB Atlas"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MongoAtlasProviderAuthConfig(
            **self.config.authentication
        )

    def _get_alerts(self) -> list[AlertDto]:
        self.logger.info("Fetching alerts from MongoDB Atlas")
        url = f"https://cloud.mongodb.com/api/atlas/v1.0/groups/{self.authentication_config.project_id}/alerts"
        response = requests.get(
            url,
            auth=requests.auth.HTTPDigestAuth(
                self.authentication_config.public_key,
                self.authentication_config.private_key,
            ),
        )
        response.raise_for_status()
        alerts_data = response.json().get("results", [])
        alerts = []
        for alert in alerts_data:
            alerts.append(
                AlertDto(
                    id=alert.get("id"),
                    name=alert.get("eventTypeName"),
                    status=AlertStatus.RESOLVED if alert.get("resolved") else AlertStatus.FIRING,
                    severity=self._get_severity(alert.get("status")),
                    last_received=alert.get("created"),
                    description=alert.get("eventTypeName"),
                    source=["mongoatlas"],
                )
            )
        return alerts

    def _get_severity(self, status: str) -> AlertSeverity:
        if status == "OPEN":
            return AlertSeverity.CRITICAL
        return AlertSeverity.INFO

    def test_connection(self):
        url = f"https://cloud.mongodb.com/api/atlas/v1.0/groups/{self.authentication_config.project_id}"
        response = requests.get(
            url,
            auth=requests.auth.HTTPDigestAuth(
                self.authentication_config.public_key,
                self.authentication_config.private_key,
            ),
        )
        response.raise_for_status()


if __name__ == "__main__":
    # Test logic
    pass
