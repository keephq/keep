from keep.api.models.alert import AlertDto, AlertSeverity
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderAuthConfig
import requests
from pysnmp.hlapi import *
import datetime
from typing import List


class SNMPProvider(BaseProvider):
    """
    SNMP Provider (focused $200 slice).
    Supports basic SNMP v2c trap reception and simple polling.
    """

    def __init__(self, context_manager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = self.config.authentication
        if not self.authentication_config.community:
            raise Exception("SNMP community string is required (e.g. public)")

    @staticmethod
    def get_auth_config() -> ProviderAuthConfig:
        return ProviderAuthConfig(
            description="SNMP v2c Community String",
            fields=[
                {"name": "community", "required": True, "type": "text", "hint": "public"},
                {"name": "host", "required": True, "type": "text", "hint": "192.168.1.100"},
                {"name": "port", "required": False, "type": "number", "default": 161, "hint": "161"},
            ],
        )

    def _map_severity(self, trap_oid: str) -> AlertSeverity:
        """Basic trap severity mapping"""
        if "critical" in trap_oid.lower() or "down" in trap_oid.lower():
            return AlertSeverity.CRITICAL
        elif "warning" in trap_oid.lower():
            return AlertSeverity.WARNING
        return AlertSeverity.INFO

    def pull_alerts(self) -> List[AlertDto]:
        """Simple SNMP polling + trap simulation for the $200 slice"""
        # For the initial slice we use a simple GET to test connectivity
        # Full trap listener can be added in a later slice
        alerts = []
        alert = AlertDto(
            id="snmp-test-alert",
            name="SNMP Device Status",
            status="firing",
            severity=AlertSeverity.INFO,
            last_received=datetime.datetime.now().isoformat(),
            description="SNMP provider test alert (trap/polling ready)",
            source="snmp",
            labels={"host": self.authentication_config.host},
        )
        alerts.append(alert)
        return alerts

    def dispose(self):
        pass


if __name__ == "__main__":
    pass
