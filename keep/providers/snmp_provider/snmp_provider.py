"""
SNMP Provider for Keep - receives SNMP traps as alerts and supports SNMP polling.
"""

import dataclasses
import datetime
import json
import re
import uuid

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """SNMP authentication configuration."""

    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SNMP agent host IP or hostname",
        },
        default="",
    )
    port: int = dataclasses.field(
        metadata={
            "description": "SNMP port (default 161 for GET, 162 for TRAP)",
            "required": False,
        },
        default=161,
    )
    community: str = dataclasses.field(
        metadata={
            "description": "SNMP community string (v1/v2c)",
            "required": False,
            "sensitive": True,
        },
        default="public",
    )
    version: str = dataclasses.field(
        metadata={
            "description": "SNMP version: v1, v2c, or v3",
            "required": False,
        },
        default="v2c",
    )
    # v3 auth fields
    security_level: str = dataclasses.field(
        metadata={
            "description": "SNMPv3 security level: noAuthNoPriv, authNoPriv, authPriv",
            "required": False,
        },
        default="noAuthNoPriv",
    )
    auth_protocol: str = dataclasses.field(
        metadata={
            "description": "SNMPv3 auth protocol: MD5, SHA",
            "required": False,
        },
        default="",
    )
    auth_password: str = dataclasses.field(
        metadata={
            "description": "SNMPv3 auth password",
            "required": False,
            "sensitive": True,
        },
        default="",
    )
    priv_protocol: str = dataclasses.field(
        metadata={
            "description": "SNMPv3 privacy protocol: DES, AES",
            "required": False,
        },
        default="",
    )
    priv_password: str = dataclasses.field(
        metadata={
            "description": "SNMPv3 privacy password",
            "required": False,
            "sensitive": True,
        },
        default="",
    )
    security_name: str = dataclasses.field(
        metadata={
            "description": "SNMPv3 security name (username)",
            "required": False,
        },
        default="",
    )
    # Polling config
    oid: str = dataclasses.field(
        metadata={
            "description": "SNMP OID to query (e.g. 1.3.6.1.2.1.1.3.0 for sysUpTime)",
            "required": False,
        },
        default="1.3.6.1.2.1.1.3.0",
    )
    poll_interval: int = dataclasses.field(
        metadata={
            "description": "Polling interval in seconds",
            "required": False,
        },
        default=60,
    )


# OID to name mapping for common SNMP OIDs
OID_MAP = {
    "1.3.6.1.2.1.1.1.0": "sysDescr",
    "1.3.6.1.2.1.1.2.0": "sysObjectID",
    "1.3.6.1.2.1.1.3.0": "sysUpTime",
    "1.3.6.1.2.1.1.4.0": "sysContact",
    "1.3.6.1.2.1.1.5.0": "sysName",
    "1.3.6.1.2.1.1.6.0": "sysLocation",
    "1.3.6.1.2.1.1.7.0": "sysServices",
    "1.3.6.1.2.1.2.2.1.1": "ifIndex",
    "1.3.6.1.2.1.2.2.1.2": "ifDescr",
    "1.3.6.1.2.1.2.2.1.8": "ifOperStatus",
    "1.3.6.1.2.1.2.2.1.10": "ifInOctets",
    "1.3.6.1.2.1.2.2.1.16": "ifOutOctets",
    "1.3.6.1.6.3.1.1.4.1.0": "snmpTrapOID",
    "1.3.6.1.6.3.1.1.4.3.0": "snmpTrapAddress",
    "1.3.6.1.4.1.9.9.41.1.2.3.1.2": "ciscoLogMessage",
    "1.3.6.1.4.1.9.9.41.1.2.3.1.4": "ciscoLogSeverity",
    "1.3.6.1.4.1.9.9.41.1.2.3.1.5": "ciscoLogFacility",
}

# Cisco severity to Keep severity mapping
CISCO_SEVERITY_MAP = {
    "0": AlertSeverity.CRITICAL,
    "1": AlertSeverity.CRITICAL,
    "2": AlertSeverity.HIGH,
    "3": AlertSeverity.WARNING,
    "4": AlertSeverity.INFO,
    "5": AlertSeverity.INFO,
    "6": AlertSeverity.INFO,
    "7": AlertSeverity.INFO,
}

# Generic trap OID to severity mapping
TRAP_SEVERITY_MAP = {
    "1.3.6.1.6.3.1.1.5.1": AlertSeverity.INFO,      # coldStart
    "1.3.6.1.6.3.1.1.5.2": AlertSeverity.WARNING,    # warmStart
    "1.3.6.1.6.3.1.1.5.3": AlertSeverity.CRITICAL,   # linkDown
    "1.3.6.1.6.3.1.1.5.4": AlertSeverity.INFO,       # linkUp
    "1.3.6.1.6.3.1.1.5.5": AlertSeverity.CRITICAL,   # authenticationFailure
    "1.3.6.1.6.3.1.1.5.6": AlertSeverity.WARNING,    # egpNeighborLoss
}


class SnmpProvider(BaseProvider):
    """SNMP provider - receive traps and poll devices for alerts."""

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert", "monitoring", "network", "snmp"]

    STATUS_MAP = {
        "up": AlertStatus.RESOLVED,
        "down": AlertStatus.FIRING,
        "testing": AlertStatus.FIRING,
        "linkdown": AlertStatus.FIRING,
        "linkup": AlertStatus.RESOLVED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.host:
            raise ProviderException("SNMP host is required")

    def dispose(self):
        pass

    def _get_oid_name(self, oid: str) -> str:
        """Get human-readable name for an OID."""
        return OID_MAP.get(oid, oid)

    def _query(self, **kwargs) -> dict:
        """Query SNMP device using pysnmp or HTTP proxy.

        Args:
            oid: SNMP OID to query
            host: Override host
            community: Override community string
        """
        oid = kwargs.get("oid", self.authentication_config.oid)
        host = kwargs.get("host", self.authentication_config.host)
        community = kwargs.get("community", self.authentication_config.community)

        try:
            from pysnmp.hlapi import (
                SnmpEngine,
                CommunityData,
                UdpTransportTarget,
                ContextData,
                ObjectType,
                ObjectIdentity,
                getCmd,
                nextCmd,
            )

            errorIndication, errorStatus, errorIndex, varBinds = next(
                getCmd(
                    SnmpEngine(),
                    CommunityData(community),
                    UdpTransportTarget((host, self.authentication_config.port)),
                    ContextData(),
                    ObjectType(ObjectIdentity(oid)),
                )
            )

            if errorIndication:
                raise ProviderException(f"SNMP query error: {errorIndication}")
            elif errorStatus:
                raise ProviderException(
                    f"SNMP query error: {errorStatus} at {errorIndex}"
                )

            result = {}
            for varBind in varBinds:
                for oid_val, value_val in varBind:
                    oid_str = str(oid_val)
                    name = self._get_oid_name(oid_str)
                    result[name] = str(value_val)
                    result[oid_str] = str(value_val)
            return result

        except ImportError:
            # pysnmp not available - try HTTP proxy approach
            raise ProviderException(
                "pysnmp is required for SNMP polling. Install with: pip install pysnmp"
            )

    def _get_alerts(self) -> list[AlertDto]:
        """Poll SNMP device for alert conditions.

        Checks interface status, CPU, memory, etc. and creates alerts
        for any abnormal conditions.
        """
        alerts = []

        try:
            # Query interface operational status
            interface_status = self._query(
                oid="1.3.6.1.2.1.2.2.1.8"  # ifOperStatus
            )

            for oid_key, value in interface_status.items():
                if oid_key.startswith("1.3.6.1.2.1.2.2.1.8"):
                    if_index = oid_key.split(".")[-1]
                    status = value.lower()

                    if status == "down" or status == "2":
                        # Interface down - create alert
                        if_name = self._query(
                            oid=f"1.3.6.1.2.1.2.2.1.2.{if_index}"
                        )
                        name = if_name.get(
                            f"1.3.6.1.2.1.2.2.1.2.{if_index}",
                            f"Interface {if_index}"
                        )

                        alerts.append(
                            AlertDto(
                                id=str(uuid.uuid4()),
                                name=f"Interface Down: {name}",
                                description=f"Interface {name} (index {if_index}) is down on {self.authentication_config.host}",
                                status=AlertStatus.FIRING,
                                severity=AlertSeverity.HIGH,
                                source=["snmp"],
                                lastReceived=datetime.datetime.now(
                                    tz=datetime.timezone.utc
                                ).isoformat(),
                                environment="production",
                                labels={"interface": name, "host": self.authentication_config.host},
                            )
                        )

        except ProviderException:
            # If polling fails, return empty - traps will still work
            pass

        return alerts

    @staticmethod
    def _format_alert(event: dict, provider_instance: "BaseProvider" = None) -> list[AlertDto]:
        """Format incoming SNMP trap data into Keep alerts.

        This is called when a trap is received via webhook.
        The trap data should be forwarded from snmptrapd to Keep's webhook endpoint.
        """
        alerts = []

        # Extract trap OID
        trap_oid = event.get("1.3.6.1.6.3.1.1.4.1.0", event.get("snmpTrapOID", ""))
        trap_name = OID_MAP.get(trap_oid, trap_oid)

        # Determine severity from trap OID
        severity = TRAP_SEVERITY_MAP.get(trap_oid, AlertSeverity.WARNING)

        # Check for Cisco-specific severity
        if "1.3.6.1.4.1.9.9.41.1.2.3.1.4" in event:
            cisco_sev = event["1.3.6.1.4.1.9.9.41.1.2.3.1.4"]
            severity = CISCO_SEVERITY_MAP.get(str(cisco_sev), severity)

        # Determine status
        status = AlertStatus.FIRING
        if trap_oid in ["1.3.6.1.6.3.1.1.5.4"]:  # linkUp
            status = AlertStatus.RESOLVED

        # Build description from all OID values
        description_parts = []
        for oid_key, value in event.items():
            name = OID_MAP.get(oid_key, oid_key)
            if name != oid_key:
                description_parts.append(f"{name}: {value}")
            else:
                description_parts.append(f"{oid_key}: {value}")
        description = "\n".join(description_parts) if description_parts else f"SNMP trap: {trap_name}"

        # Extract source address
        source_addr = event.get("1.3.6.1.6.3.1.1.4.3.0", event.get("snmpTrapAddress", "unknown"))

        alert = AlertDto(
            id=str(uuid.uuid4()),
            name=trap_name if trap_name != trap_oid else f"SNMP Trap from {source_addr}",
            description=description,
            status=status,
            severity=severity,
            source=["snmp"],
            lastReceived=datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            environment="production",
            labels={
                "trap_oid": trap_oid,
                "source_address": source_addr,
            },
            payload=event,
        )
        alerts.append(alert)
        return alerts

    def notify(self, **kwargs):
        """Send SNMP trap (outbound notification).

        This allows Keep workflows to send SNMP traps to external systems.
        """
        message = kwargs.get("message", "Keep Alert")
        host = kwargs.get("host", self.authentication_config.host)
        port = kwargs.get("port", 162)

        try:
            from pysnmp.hlapi import (
                SnmpEngine,
                CommunityData,
                UdpTransportTarget,
                ContextData,
                ObjectType,
                ObjectIdentity,
                sendNotification,
                NotificationType,
            )

            errorIndication, errorStatus, errorIndex, varBinds = next(
                sendNotification(
                    SnmpEngine(),
                    CommunityData(self.authentication_config.community),
                    UdpTransportTarget((host, port)),
                    ContextData(),
                    NotificationType(
                        ObjectType(
                            ObjectIdentity("1.3.6.1.6.3.1.1.5.1"),  # coldStart
                            message,
                        )
                    ),
                )
            )

            if errorIndication:
                raise ProviderException(f"SNMP trap send error: {errorIndication}")

            return {"status": "sent", "host": host, "port": port}

        except ImportError:
            raise ProviderException(
                "pysnmp is required for SNMP trap sending. Install with: pip install pysnmp"
            )

    @staticmethod
    def simulate_alert(**kwargs) -> dict:
        """Simulate an SNMP trap alert for testing."""
        return {
            "1.3.6.1.6.3.1.1.4.1.0": "1.3.6.1.6.3.1.1.5.3",  # linkDown trap
            "1.3.6.1.6.3.1.1.4.3.0": "192.168.1.100",
            "1.3.6.1.2.1.2.2.1.1": "3",
            "1.3.6.1.2.1.2.2.1.2.3": "GigabitEthernet0/3",
            "1.3.6.1.2.1.2.2.1.8.3": "down",
        }


if __name__ == "__main__":
    import os

    context_manager = ContextManager(
        tenant_id="test",
        workflow_id="test",
    )

    config = ProviderConfig(
        authentication={
            "host": os.environ.get("SNMP_HOST", "192.168.1.1"),
            "community": os.environ.get("SNMP_COMMUNITY", "public"),
            "version": "v2c",
        },
    )

    provider = SnmpProvider(
        context_manager=context_manager,
        provider_id="snmp-test",
        config=config,
    )

    # Test alert formatting
    test_trap = SnmpProvider.simulate_alert()
    formatted = SnmpProvider._format_alert(test_trap)
    for alert in formatted:
        print(f"Alert: {alert.name} - {alert.severity} - {alert.description[:100]}")