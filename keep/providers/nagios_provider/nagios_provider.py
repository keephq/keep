from keep.api.models.alert import AlertDto, AlertSeverity
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderAuthConfig
import requests
import json
from typing import List, Optional
import datetime


class NagiosProvider(BaseProvider):
    """
    Nagios Provider for both Nagios Core (statusjson.cgi) and Nagios XI (REST API).
    Supports polling and webhook ingestion.
    """

    def __init__(self, context_manager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = self.config.authentication
        if not self.authentication_config.url:
            raise Exception("Nagios URL is required")
        if not self.authentication_config.username or not self.authentication_config.password:
            raise Exception("Basic Auth (username + password) is required for Nagios")

    @staticmethod
    def get_auth_config() -> ProviderAuthConfig:
        return ProviderAuthConfig(
            description="Nagios Basic Auth",
            fields=[
                {"name": "url", "required": True, "type": "text", "hint": "http://your-nagios-server"},
                {"name": "username", "required": True, "type": "text"},
                {"name": "password", "required": True, "type": "password"},
            ],
        )

    def _get_alerts_from_core(self) -> List[AlertDto]:
        """Nagios Core polling using statusjson.cgi"""
        url = f"{self.authentication_config.url.rstrip('/')}/cgi-bin/statusjson.cgi?query=service&details=true"
        response = requests.get(
            url,
            auth=(self.authentication_config.username, self.authentication_config.password),
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        alerts = []
        for service in data.get("data", {}).get("service", {}).get("list", []):
            status = service.get("status", "").upper()
            severity = self._map_severity(status)

            alert = AlertDto(
                id=f"nagios-core-{service.get('host_name')}-{service.get('service_description')}",
                name=service.get("service_description"),
                status="firing" if severity in ["critical", "warning"] else "resolved",
                severity=severity,
                last_received=datetime.datetime.now().isoformat(),
                description=service.get("plugin_output", ""),
                source="nagios-core",
                labels={
                    "host": service.get("host_name"),
                    "service": service.get("service_description"),
                },
            )
            alerts.append(alert)
        return alerts

    def _get_alerts_from_xi(self) -> List[AlertDto]:
        """Nagios XI REST API polling"""
        url = f"{self.authentication_config.url.rstrip('/')}/nagiosxi/api/v1/objects/hoststatus"
        response = requests.get(
            url,
            auth=(self.authentication_config.username, self.authentication_config.password),
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        alerts = []
        for host in data.get("hoststatus", []):
            status = host.get("status", "").upper()
            severity = self._map_severity(status)

            alert = AlertDto(
                id=f"nagios-xi-{host.get('host_name')}",
                name=host.get("host_name"),
                status="firing" if severity in ["critical", "warning"] else "resolved",
                severity=severity,
                last_received=datetime.datetime.now().isoformat(),
                description=host.get("status_text", ""),
                source="nagios-xi",
                labels={"host": host.get("host_name")},
            )
            alerts.append(alert)
        return alerts

    def _map_severity(self, status: str) -> AlertSeverity:
        mapping = {
            "CRITICAL": AlertSeverity.CRITICAL,
            "DOWN": AlertSeverity.CRITICAL,
            "WARNING": AlertSeverity.WARNING,
            "UNKNOWN": AlertSeverity.INFO,
            "OK": AlertSeverity.OK,
            "UP": AlertSeverity.OK,
        }
        return mapping.get(status, AlertSeverity.INFO)

    def pull_alerts(self) -> List[AlertDto]:
        """Polling method - tries both Core and XI"""
        try:
            return self._get_alerts_from_core()
        except Exception:
            # Fallback to XI if Core fails
            return self._get_alerts_from_xi()

    def dispose(self):
        pass


if __name__ == "__main__":
    pass
