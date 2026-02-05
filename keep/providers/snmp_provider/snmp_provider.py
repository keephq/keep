import logging
import asyncio
from typing import List, Optional
from pydantic import Field, dataclasses as pydantic_dataclasses
from pysnmp.hlapi import *
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.providers.base.base_provider import BaseTopologyProvider, ProviderHealthMixin
from keep.providers.models.provider_config import ProviderConfig

@pydantic_dataclasses.dataclass
class SnmpProviderAuthConfig:
    host: str = Field(description="Target SNMP Host/IP for polling")
    port: int = Field(default=161, description="SNMP Port (default 161)")
    trap_port: int = Field(default=162, description="Port to listen for Traps (default 162)")
    community: str = Field(default="public", description="SNMP Community String", sensitive=True)
    version: int = Field(default=2, description="SNMP Version (1, 2, or 3)")
    oids: List[str] = Field(default_factory=list, description="List of OIDs to poll")

class SnmpProvider(BaseTopologyProvider, ProviderHealthMixin):
    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring", "Network"]

    def __init__(self, context_manager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.auth_config = SnmpProviderAuthConfig(**self.config.authentication)

    def _get_alerts(self) -> List[AlertDto]:
        """Polls specified OIDs for current status."""
        alerts = []
        for oid in self.auth_config.oids:
            try:
                errorIndication, errorStatus, errorIndex, varBinds = next(
                    getCmd(SnmpEngine(),
                           CommunityData(self.auth_config.community),
                           UdpTransportTarget((self.auth_config.host, self.auth_config.port)),
                           ContextData(),
                           ObjectType(ObjectIdentity(oid)))
                )
                if not errorIndication and not errorStatus:
                    for varBind in varBinds:
                        alerts.append(self._format_alert(varBind, "polling"))
            except Exception as e:
                self.logger.error(f"Failed to poll SNMP OID {oid}: {e}")
        return alerts

    def _format_alert(self, var_bind, method: str) -> AlertDto:
        oid, value = var_bind
        return AlertDto(
            id=f"snmp-{self.auth_config.host}-{oid}",
            name=f"SNMP {method.capitalize()}: {oid}",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.INFO,
            message=f"Value: {str(value)} (Method: {method})",
            source=["snmp"],
            tags={"oid": str(oid), "host": self.auth_config.host}
        )

    def validate_health(self):
        """Standard Keep health check."""
        try:
            # Simple SysContact poll to verify connectivity
            next(getCmd(SnmpEngine(), CommunityData(self.auth_config.community),
                        UdpTransportTarget((self.auth_config.host, self.auth_config.port)),
                        ContextData(), ObjectType(ObjectIdentity('1.3.6.1.2.1.1.4.0'))))
            return True
        except Exception:
            return False
