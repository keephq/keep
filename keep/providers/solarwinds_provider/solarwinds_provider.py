from keep.api.models.alert import AlertDto, AlertSeverity
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderAuthConfig
import requests
import json
from typing import List, Optional
import datetime


class SolarWindsProvider(BaseProvider):
    """
    SolarWinds Provider for Orion Platform (SWIS REST API).
    Supports polling active alerts from Orion.AlertActive and Orion.Nodes.
    """

    def __init__(self, context_manager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = self.config.authentication
        if not self.authentication_config.url:
            raise Exception("SolarWinds URL is required (e.g. https://your-solarwinds-server)")
        if not self.authentication_config.username or not self.authentication_config.password:
            raise Exception("Basic Auth (username + password) is required for SolarWinds")

    @staticmethod
    def get_auth_config() -> ProviderAuthConfig:
        return ProviderAuthConfig(
            description="SolarWinds Orion Basic Auth",
            fields=[
                {"name": "url", "required": True, "type": "text", "hint": "https://your-solarwinds-server"},
                {"name": "username", "required": True, "type": "text"},
                {"name": "password", "required": True, "type": "password"},
            ],
        )

    def _get_alerts(self) -> List[AlertDto]:
        """Poll active alerts via SWIS REST API"""
        url = f"{self.authentication_config.url.rstrip('/')}/SolarWinds/InformationService/v3/Json/Query"
        query = """
        SELECT 
            AlertActive.AlertObjectID,
            AlertActive.AlertName,
            AlertActive.Severity,
            AlertActive.ObjectName,
            AlertActive.ObjectType,
            AlertActive.LastTriggerTime,
            AlertActive.AlertMessage
        FROM Orion.AlertActive
        """

        payload = {"query": query}
        response = requests.post(
            url,
            auth=(self.authentication_config.username, self.authentication_config.password),
            json=payload,
            timeout=15,
            verify=True,
        )
        response.raise_for_status()
        data = response.json()

        alerts = []
        for item in data.get("results", []):
            severity = self._map_severity(item.get("Severity", 0))

            alert = AlertDto(
                id=f"solarwinds-{item.get('AlertObjectID')}",
                name=item.get("AlertName") or item.get("ObjectName"),
                status="firing" if severity in [AlertSeverity.CRITICAL, AlertSeverity.WARNING] else "resolved",
                severity=severity,
                last_received=item.get("LastTriggerTime") or datetime.datetime.now().isoformat(),
                description=item.get("AlertMessage", ""),
                source="solarwinds",
                labels={
                    "object": item.get("ObjectName"),
                    "object_type": item.get("ObjectType"),
                },
            )
            alerts.append(alert)
        return alerts

    def _map_severity(self, severity_code: int) -> AlertSeverity:
        mapping = {
            0: AlertSeverity.OK,
            1: AlertSeverity.WARNING,
            2: AlertSeverity.CRITICAL,
            3: AlertSeverity.CRITICAL,
        }
        return mapping.get(severity_code, AlertSeverity.INFO)

    def pull_alerts(self) -> List[AlertDto]:
        """Main polling method"""
        return self._get_alerts()

    def dispose(self):
        pass


if __name__ == "__main__":
    pass
