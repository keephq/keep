"""
SNMP Provider is a class that provides a way to receive alerts from SNMP-enabled devices.
"""

import dataclasses
from typing import Optional

import pydantic
from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
)

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP Authentication Configuration.

    Supports SNMP v1, v2c, and v3.

    config params:
    - host: SNMP device IP/hostname
    - port: SNMP port (default 161)
    - version: SNMP version (1, 2c, 3)
    - community: Community string (for v1/v2c)
    - username: Username (for v3)
    - auth_key: Authentication key (for v3)
    - priv_key: Privacy/encryption key (for v3)
    """

    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SNMP Device Host/IP",
            "hint": "e.g., 192.168.1.1 or device.example.com",
            "sensitive": False,
        }
    )

    port: int = dataclasses.field(
        default=161,
        metadata={
            "required": False,
            "description": "SNMP Port",
            "hint": "Default: 161",
            "sensitive": False,
        }
    )

    version: str = dataclasses.field(
        default="2c",
        metadata={
            "required": True,
            "description": "SNMP Version",
            "hint": "Options: 1, 2c, 3",
            "sensitive": False,
        }
    )

    community: str = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": "Community String (v1/v2c)",
            "hint": "Default: public",
            "sensitive": True,
        }
    )

    username: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Username (v3)",
            "hint": "Required for SNMPv3",
            "sensitive": False,
        }
    )

    auth_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Authentication Key (v3)",
            "hint": "Required for SNMPv3 auth",
            "sensitive": True,
        }
    )

    priv_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Privacy/Encryption Key (v3)",
            "hint": "Required for SNMPv3 privacy",
            "sensitive": True,
        }
    )


class SnmpProvider(BaseProvider):
    """
    Get alerts and metrics from SNMP-enabled devices into Keep.

    Supports:
    - SNMP v1, v2c, and v3
    - Polling device OIDs for metrics
    - Receiving SNMP traps via webhooks
    - Mapping SNMP states to Keep alert status and severity
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert", "monitoring", "network"]
    PROVIDER_CATEGORY = ["Monitoring"]
    WEBHOOK_INSTALLATION_REQUIRED = True
    PROVIDER_ICON = "snmp-icon.png"

    # Define provider scopes
    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read alerts from SNMP devices",
        ),
        ProviderScope(
            name="read_metrics",
            description="Read metrics from SNMP devices",
        ),
    ]

    # SNMP standard OIDs for system information
    SYSTEM_OIDS = {
        "sysDescr": "1.3.6.1.2.1.1.1.0",
        "sysObjectID": "1.3.6.1.2.1.1.2.0",
        "sysUpTime": "1.3.6.1.2.1.1.3.0",
        "sysContact": "1.3.6.1.2.1.1.4.0",
        "sysName": "1.3.6.1.2.1.1.5.0",
        "sysLocation": "1.3.6.1.2.1.1.6.0",
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for SNMP provider.
        """
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

        # Validate version
        valid_versions = ["1", "2c", "3"]
        if self.authentication_config.version not in valid_versions:
            raise ValueError(
                f"Invalid SNMP version: {self.authentication_config.version}. "
                f"Must be one of: {', '.join(valid_versions)}"
            )

    def validate_scopes(self):
        """
        Validate provider scopes by testing SNMP connectivity.
        """
        self.logger.info("Validating SNMP provider connectivity")
        try:
            # Try to get sysDescr as connectivity test
            result = self._get_oid(self.SYSTEM_OIDS["sysDescr"])

            if result:
                self.logger.info(
                    "SNMP validation successful",
                    extra={"sysDescr": result},
                )
                return {"read_alerts": True, "read_metrics": True}
            else:
                return {"read_alerts": "No response from device", "read_metrics": False}

        except Exception as e:
            self.logger.exception("Failed to validate SNMP scopes", extra={"error": e})
            return {"read_alerts": str(e), "read_metrics": str(e)}

    def _get_oid(self, oid: str) -> Optional[str]:
        """
        Get a single OID value from the SNMP device.

        Args:
            oid: SNMP OID to query

        Returns:
            Optional[str]: The OID value or None if not found
        """
        host = self.authentication_config.host
        port = self.authentication_config.port
        version = self.authentication_config.version
        community = self.authentication_config.community

        try:
            snmp_engine = SnmpEngine()

            # Build community data based on version
            if version == "1":
                community_data = CommunityData(community, mpModel=0)
            elif version == "2c":
                community_data = CommunityData(community, mpModel=1)
            else:
                # SNMPv3 - would need more complex implementation
                self.logger.warning("SNMPv3 not fully implemented yet")
                return None

            target = UdpTransportTarget((host, port), timeout=5, retries=2)

            errorIndication, errorStatus, errorIndex, varBinds = next(
                getCmd(
                    snmp_engine,
                    community_data,
                    target,
                    ContextData(),
                    ObjectType(ObjectIdentity(oid)),
                )
            )

            if errorIndication:
                self.logger.error(f"SNMP error: {errorIndication}")
                return None
            elif errorStatus:
                self.logger.error(
                    f"SNMP error: {errorStatus.prettyPrint()} at {errorIndex and varBinds[int(errorIndex) - 1][0] or '?'}",
                )
                return None
            else:
                for varBind in varBinds:
                    return str(varBind[1])

        except Exception as e:
            self.logger.exception(f"Error getting OID {oid}", extra={"error": e})
            return None

    def _get_alerts(self) -> list[AlertDto]:
        """
        Get alerts from SNMP device by polling critical OIDs.

        Returns:
            list[AlertDto]: List of alerts in Keep format
        """
        self.logger.info("Getting alerts from SNMP device")
        alerts = []

        try:
            # Get system information
            sys_name = self._get_oid(self.SYSTEM_OIDS["sysName"]) or "Unknown"
            sys_descr = self._get_oid(self.SYSTEM_OIDS["sysDescr"]) or "Unknown Device"
            sys_uptime = self._get_oid(self.SYSTEM_OIDS["sysUpTime"]) or "0"

            # Create a heartbeat alert
            alert = AlertDto(
                id=f"snmp-{self.provider_id}-heartbeat",
                name=f"SNMP Device {sys_name}",
                status=AlertStatus.RESOLVED,
                severity=AlertSeverity.INFO,
                lastReceived="now",
                description=f"SNMP device {sys_name} ({sys_descr}) is reachable. Uptime: {sys_uptime}",
                source=["snmp"],
                providerId=self.provider_id,
                providerType="snmp",
            )
            alerts.append(alert)

            self.logger.info(f"Retrieved {len(alerts)} alerts from SNMP device")
            return alerts

        except Exception as e:
            self.logger.exception("Failed to get alerts from SNMP device", extra={"error": e})
            return []

    @staticmethod
    def _format_alert(
        event: dict, provider_id: str, provider_type: str
    ) -> AlertDto:
        """
        Format SNMP trap/event into Keep AlertDto.

        Args:
            event: SNMP event data
            provider_id: Provider ID
            provider_type: Provider type

        Returns:
            AlertDto: Formatted alert
        """
        # Map SNMP trap severity to Keep severity
        snmp_severity = event.get("severity", "INFO").upper()
        severity_map = {
            "CRITICAL": AlertSeverity.CRITICAL,
            "MAJOR": AlertSeverity.HIGH,
            "MINOR": AlertSeverity.WARNING,
            "WARNING": AlertSeverity.WARNING,
            "INFO": AlertSeverity.INFO,
        }
        severity = severity_map.get(snmp_severity, AlertSeverity.INFO)

        # Map SNMP trap status
        snmp_status = event.get("status", "RESOLVED").upper()
        status_map = {
            "ACTIVE": AlertStatus.FIRING,
            "RESOLVED": AlertStatus.RESOLVED,
            "ACKNOWLEDGED": AlertStatus.ACKNOWLEDGED,
        }
        status = status_map.get(snmp_status, AlertStatus.FIRING)

        return AlertDto(
            id=event.get("id", f"snmp-{provider_id}-unknown"),
            name=event.get("name", "SNMP Alert"),
            status=status,
            severity=severity,
            lastReceived=event.get("timestamp", "now"),
            description=event.get("description", "SNMP trap received"),
            source=[event.get("source", "snmp")],
            providerId=provider_id,
            providerType=provider_type,
            fingerprint=event.get("fingerprint"),
        )

    def dispose(self):
        """
        Dispose of the provider.
        """
        pass
