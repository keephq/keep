"""
SNMP Provider is a class that allows to ingest SNMP traps/events into Keep as alerts.
"""

import dataclasses
import datetime
import json
import logging
from typing import Optional

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP authentication configuration.
    """

    community: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMP Community String",
            "hint": "Default: public",
            "sensitive": True,
        },
        default="public",
    )


class SnmpProvider(BaseProvider):
    """
    Receive SNMP traps as alerts in Keep.
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring", "Network"]
    PROVIDER_TAGS = ["alert"]

    # SNMP severity mapping based on standard SNMP trap OIDs and common conventions
    SEVERITY_MAP = {
        # Standard SNMPv1 trap types
        "coldStart": AlertSeverity.INFO,
        "warmStart": AlertSeverity.INFO,
        "linkDown": AlertSeverity.CRITICAL,
        "linkUp": AlertSeverity.INFO,
        "authenticationFailure": AlertSeverity.WARNING,
        "egpNeighborLoss": AlertSeverity.CRITICAL,
        # Common enterprise severity indicators
        "emergency": AlertSeverity.CRITICAL,
        "alert": AlertSeverity.CRITICAL,
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "notice": AlertSeverity.INFO,
        "informational": AlertSeverity.INFO,
        "debug": AlertSeverity.LOW,
        # Numeric mappings
        "0": AlertSeverity.CRITICAL,
        "1": AlertSeverity.CRITICAL,
        "2": AlertSeverity.HIGH,
        "3": AlertSeverity.WARNING,
        "4": AlertSeverity.INFO,
        "5": AlertSeverity.LOW,
    }

    STATUS_MAP = {
        "linkUp": AlertStatus.RESOLVED,
        "up": AlertStatus.RESOLVED,
        "ok": AlertStatus.RESOLVED,
        "resolved": AlertStatus.RESOLVED,
        "clear": AlertStatus.RESOLVED,
        "linkDown": AlertStatus.FIRING,
        "down": AlertStatus.FIRING,
        "failed": AlertStatus.FIRING,
        "failure": AlertStatus.FIRING,
        "error": AlertStatus.FIRING,
        "critical": AlertStatus.FIRING,
        "warning": AlertStatus.FIRING,
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
        Validates the configuration of the SNMP provider.
        """
        self.authentication_config = SnmpProviderAuthConfig(**self.config.authentication)

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate the scopes of the provider.
        """
        return {"authenticated": True}

    @staticmethod
    def _parse_snmp_version(event: dict) -> str:
        """Extract SNMP version from event."""
        return event.get("version", event.get("snmpVersion", "v1"))

    @staticmethod
    def _parse_oid(event: dict) -> str:
        """Extract trap OID from event."""
        # Try various common OID field names
        oid = (
            event.get("trapOid")
            or event.get("oid")
            or event.get("enterprise")
            or event.get("snmpTrapOID")
            or event.get("1.3.6.1.6.3.1.1.4.1.0")
        )
        return oid or "unknown"

    @staticmethod
    def _parse_source(event: dict) -> str:
        """Extract source address from event."""
        return (
            event.get("source")
            or event.get("agentAddress")
            or event.get("agent_addr")
            or event.get("ip")
            or event.get("hostname")
            or "unknown"
        )

    def _parse_severity(self, event: dict) -> AlertSeverity:
        """Parse severity from SNMP event."""
        # Check various severity fields
        severity_fields = [
            "severity",
            "priority",
            "level",
            "alarmSeverity",
            "snmpTrapSeverity",
        ]

        for field in severity_fields:
            value = event.get(field)
            if value:
                severity_str = str(value).lower()
                if severity_str in self.SEVERITY_MAP:
                    return self.SEVERITY_MAP[severity_str]

        # Try to infer from trap OID
        oid = self._parse_oid(event).lower()
        for key, severity in self.SEVERITY_MAP.items():
            if key.lower() in oid:
                return severity

        return AlertSeverity.INFO

    def _parse_status(self, event: dict) -> AlertStatus:
        """Parse status from SNMP event."""
        # Check for explicit status
        status_value = event.get("status", event.get("state", "")).lower()
        if status_value in self.STATUS_MAP:
            return self.STATUS_MAP[status_value]

        # Check trap OID for status indicators
        oid = self._parse_oid(event).lower()
        for key, status in self.STATUS_MAP.items():
            if key in oid:
                return status

        # Default to FIRING for traps
        return AlertStatus.FIRING

    @staticmethod
    def _parse_varbinds(event: dict) -> dict:
        """Extract variable bindings from SNMP event."""
        varbinds = {}

        # Common varbind field names
        varbind_fields = ["varbinds", "variables", "bindings", "oids"]

        for field in varbind_fields:
            if field in event and isinstance(event[field], dict):
                varbinds.update(event[field])

        # Also extract any OID-like keys (x.x.x.x.x format)
        for key, value in event.items():
            if key.count(".") >= 3 and key[0].isdigit():
                varbinds[key] = value

        return varbinds

    @staticmethod
    def _format_description(event: dict, varbinds: dict) -> str:
        """Format alert description from SNMP event."""
        parts = []

        # Add trap type if available
        trap_type = event.get("trapType", event.get("genericTrap", ""))
        if trap_type:
            parts.append(f"Trap Type: {trap_type}")

        # Add specific trap if available
        specific_trap = event.get("specificTrap", "")
        if specific_trap:
            parts.append(f"Specific Trap: {specific_trap}")

        # Add uptime if available
        uptime = event.get("uptime", event.get("sysUpTime", ""))
        if uptime:
            parts.append(f"System Uptime: {uptime}")

        # Add varbinds summary
        if varbinds:
            parts.append(f"Variable Bindings: {len(varbinds)} OID(s)")

        # Add raw message if available
        message = event.get("message", event.get("description", ""))
        if message:
            parts.append(f"Message: {message}")

        return "\n".join(parts) if parts else "SNMP Trap received"

    @staticmethod
    def _parse_timestamp(event: dict) -> str:
        """Parse timestamp from SNMP event."""
        # Try various timestamp fields
        timestamp_fields = [
            "timestamp",
            "time",
            "eventTime",
            "sysUpTime",
            "uptime",
        ]

        for field in timestamp_fields:
            value = event.get(field)
            if value:
                try:
                    # Try to parse as datetime
                    if isinstance(value, (int, float)):
                        return datetime.datetime.fromtimestamp(value).isoformat()
                    return value
                except (ValueError, TypeError):
                    continue

        return datetime.datetime.now().isoformat()

    def _format_alert_id(self, event: dict) -> str:
        """Generate unique alert ID from SNMP event."""
        source = self._parse_source(event)
        oid = self._parse_oid(event)
        specific_trap = event.get("specificTrap", "")

        # Create a fingerprint from source + OID + specific trap
        id_components = f"{source}:{oid}:{specific_trap}"
        return f"snmp-{id_components}"

    def _format_alert_name(self, event: dict) -> str:
        """Format alert name from SNMP event."""
        # Try to get a human-readable name
        name = event.get("name", event.get("alertName", ""))
        if name:
            return name

        # Use trap OID enterprise name if available
        oid = self._parse_oid(event)
        trap_type = event.get("trapType", "")

        if trap_type and trap_type != "enterpriseSpecific":
            return f"SNMP {trap_type}"

        # Extract last part of OID as name
        if oid and oid != "unknown":
            oid_parts = oid.split(".")
            return f"SNMP Trap - {oid_parts[-1] if len(oid_parts) > 1 else oid}"

        return "SNMP Trap"

    def format_alert(self, event: dict) -> AlertDto | list[AlertDto]:
        """
        Format SNMP event into Keep alert.

        Args:
            event: SNMP trap event data

        Returns:
            AlertDto or list of AlertDto
        """
        varbinds = self._parse_varbinds(event)

        alert = AlertDto(
            id=self._format_alert_id(event),
            name=self._format_alert_name(event),
            description=self._format_description(event, varbinds),
            status=self._parse_status(event),
            severity=self._parse_severity(event),
            source=["snmp"],
            lastReceived=self._parse_timestamp(event),
            # SNMP-specific fields
            snmpVersion=self._parse_snmp_version(event),
            snmpOid=self._parse_oid(event),
            snmpSource=self._parse_source(event),
            snmpCommunity=event.get("community", self.authentication_config.community),
            snmpVarbinds=varbinds,
            snmpTrapType=event.get("trapType", event.get("genericTrap", "")),
            snmpSpecificTrap=event.get("specificTrap", ""),
            snmpUptime=event.get("uptime", event.get("sysUpTime", "")),
            # Additional context
            host=self._parse_source(event),
            environment=event.get("environment", ""),
            service=event.get("service", event.get("application", "")),
        )

        return alert

    def get_alerts_configuration(self, alert_id: str | None = None):
        """
        SNMP provider does not support pulling alerts.
        """
        raise NotImplementedError("SNMP provider does not support pulling alerts")

    def deploy_alert(self, alert: dict, alert_id: str | None = None):
        """
        SNMP provider does not support deploying alerts.
        """
        raise NotImplementedError("SNMP provider does not support deploying alerts")

    @classmethod
    def get_webhook_template(cls) -> str:
        """
        Get the webhook template for SNMP integration.
        """
        return """
# SNMP Webhook Integration

This provider receives SNMP traps forwarded as HTTP webhooks.

## Setup Instructions

1. Configure your SNMP trap forwarder (e.g., snmptrapd with snmptt, or a trap-to-HTTP bridge)
2. Point the forwarder to send POST requests to the Keep webhook URL
3. The webhook payload should include SNMP trap data in JSON format

## Example Webhook Payload

```json
{
  "version": "v2c",
  "community": "public",
  "enterprise": "1.3.6.1.4.1.8072.2.3",
  "agentAddress": "192.168.1.100",
  "trapType": "enterpriseSpecific",
  "specificTrap": 1,
  "uptime": "123456789",
  "varbinds": {
    "1.3.6.1.4.1.8072.2.3.2.1": "Test message",
    "1.3.6.1.2.1.1.3.0": "123456789"
  },
  "severity": "warning"
}
```

## Supported Fields

- `version`: SNMP version (v1, v2c, v3)
- `community`: SNMP community string
- `enterprise` / `oid` / `trapOid`: The trap OID
- `agentAddress` / `source` / `ip`: Source of the trap
- `trapType` / `genericTrap`: Generic trap type
- `specificTrap`: Specific trap number
- `uptime` / `sysUpTime`: System uptime
- `varbinds` / `variables` / `bindings`: Variable bindings (OID-value pairs)
- `severity`: Alert severity override
- `status`: Alert status (firing/resolved)
"""
