"""
SNMP Provider for receiving SNMP traps (v1, v2c, v3) and converting them to Keep alerts.
"""

import dataclasses
import hashlib
import logging
from datetime import datetime, timezone

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)

# Well-known SNMP trap OIDs and their human-readable names
WELL_KNOWN_TRAPS = {
    "1.3.6.1.6.3.1.1.5.1": "coldStart",
    "1.3.6.1.6.3.1.1.5.2": "warmStart",
    "1.3.6.1.6.3.1.1.5.3": "linkDown",
    "1.3.6.1.6.3.1.1.5.4": "linkUp",
    "1.3.6.1.6.3.1.1.5.5": "authenticationFailure",
    "1.3.6.1.6.3.1.1.5.6": "egpNeighborLoss",
}

# Map well-known trap OIDs to default severities
TRAP_SEVERITY_MAP = {
    "1.3.6.1.6.3.1.1.5.1": AlertSeverity.WARNING,   # coldStart
    "1.3.6.1.6.3.1.1.5.2": AlertSeverity.INFO,       # warmStart
    "1.3.6.1.6.3.1.1.5.3": AlertSeverity.CRITICAL,   # linkDown
    "1.3.6.1.6.3.1.1.5.4": AlertSeverity.INFO,       # linkUp
    "1.3.6.1.6.3.1.1.5.5": AlertSeverity.HIGH,       # authenticationFailure
    "1.3.6.1.6.3.1.1.5.6": AlertSeverity.WARNING,    # egpNeighborLoss
}

# Map well-known trap OIDs to alert statuses
TRAP_STATUS_MAP = {
    "1.3.6.1.6.3.1.1.5.1": AlertStatus.FIRING,       # coldStart
    "1.3.6.1.6.3.1.1.5.2": AlertStatus.RESOLVED,     # warmStart
    "1.3.6.1.6.3.1.1.5.3": AlertStatus.FIRING,       # linkDown
    "1.3.6.1.6.3.1.1.5.4": AlertStatus.RESOLVED,     # linkUp
    "1.3.6.1.6.3.1.1.5.5": AlertStatus.FIRING,       # authenticationFailure
    "1.3.6.1.6.3.1.1.5.6": AlertStatus.FIRING,       # egpNeighborLoss
}


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP provider authentication configuration.
    Supports SNMPv1/v2c (community string) and SNMPv3 (user credentials).
    """

    snmp_version: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMP version (v1, v2c, or v3)",
            "hint": "e.g. v2c",
        },
        default="v2c",
    )
    community_string: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Community string for SNMPv1/v2c authentication",
            "hint": "e.g. public",
            "sensitive": True,
        },
        default="public",
    )
    snmpv3_username: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 USM username",
            "hint": "Required for SNMPv3",
        },
        default="",
    )
    snmpv3_auth_protocol: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 authentication protocol (MD5, SHA, SHA224, SHA256, SHA384, SHA512)",
            "hint": "e.g. SHA",
        },
        default="",
    )
    snmpv3_auth_password: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 authentication password",
            "hint": "Required if auth protocol is set",
            "sensitive": True,
        },
        default="",
    )
    snmpv3_priv_protocol: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 privacy protocol (DES, 3DES, AES128, AES192, AES256)",
            "hint": "e.g. AES128",
        },
        default="",
    )
    snmpv3_priv_password: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 privacy password",
            "hint": "Required if privacy protocol is set",
            "sensitive": True,
        },
        default="",
    )


class SnmpProvider(BaseProvider):
    """Receive SNMP traps and convert them to Keep alerts."""

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["trap_oid", "agent_address"]

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
    }

    STATUS_MAP = {
        "firing": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
    }

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send SNMP traps to Keep, configure your SNMP trap forwarder to POST trap data as JSON to the Keep webhook endpoint.

**Webhook URL:** `{keep_webhook_api_url}`
**API Key:** `{api_key}`

### Expected JSON payload format:

```json
{{
  "trap_oid": "1.3.6.1.6.3.1.1.5.3",
  "agent_address": "192.168.1.1",
  "community": "public",
  "snmp_version": "v2c",
  "enterprise": "1.3.6.1.4.1.9.1",
  "uptime": "123456",
  "varbinds": {{
    "1.3.6.1.2.1.2.2.1.1": "2",
    "1.3.6.1.2.1.2.2.1.2": "GigabitEthernet0/1"
  }},
  "description": "Optional human-readable description",
  "severity": "critical"
}}
```

### Using snmptrapd as a forwarder:

You can use `snmptrapd` with a trap handler script that forwards traps to Keep.
See the [Keep documentation](https://docs.keephq.dev/providers/documentation/snmp-provider) for detailed setup instructions.
"""

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
        Validates required configuration for SNMP provider.
        """
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    @staticmethod
    def _get_trap_name(trap_oid: str) -> str:
        """Resolve a trap OID to a human-readable name."""
        return WELL_KNOWN_TRAPS.get(trap_oid, trap_oid)

    @staticmethod
    def _get_trap_severity(event: dict) -> AlertSeverity:
        """Determine alert severity from event data."""
        # First check if severity is explicitly provided
        severity_str = event.get("severity", "").lower()
        if severity_str in SnmpProvider.SEVERITIES_MAP:
            return SnmpProvider.SEVERITIES_MAP[severity_str]

        # Fall back to well-known trap OID mapping
        trap_oid = event.get("trap_oid", "")
        if trap_oid in TRAP_SEVERITY_MAP:
            return TRAP_SEVERITY_MAP[trap_oid]

        return AlertSeverity.WARNING

    @staticmethod
    def _get_trap_status(event: dict) -> AlertStatus:
        """Determine alert status from event data."""
        # First check if status is explicitly provided
        status_str = event.get("status", "").lower()
        if status_str in SnmpProvider.STATUS_MAP:
            return SnmpProvider.STATUS_MAP[status_str]

        # Fall back to well-known trap OID mapping
        trap_oid = event.get("trap_oid", "")
        if trap_oid in TRAP_STATUS_MAP:
            return TRAP_STATUS_MAP[trap_oid]

        return AlertStatus.FIRING

    @staticmethod
    def _generate_trap_id(event: dict) -> str:
        """Generate a unique ID for a trap event."""
        trap_oid = event.get("trap_oid", "")
        agent_address = event.get("agent_address", "")
        uptime = event.get("uptime", "")
        raw = f"{trap_oid}:{agent_address}:{uptime}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @staticmethod
    def _format_varbinds(varbinds: dict) -> str:
        """Format varbinds dict into a readable string."""
        if not varbinds:
            return ""
        parts = [f"{oid}={value}" for oid, value in varbinds.items()]
        return "; ".join(parts)

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format an incoming SNMP trap event into a Keep AlertDto.

        Handles SNMPv1, v2c, and v3 trap payloads sent as JSON
        to the Keep webhook endpoint.
        """
        trap_oid = event.get("trap_oid", "")
        agent_address = event.get("agent_address", "unknown")
        trap_name = SnmpProvider._get_trap_name(trap_oid)
        varbinds = event.get("varbinds", {})

        # Build description from event or generate one
        description = event.get("description", "")
        if not description:
            description = (
                f"SNMP trap {trap_name} ({trap_oid}) "
                f"from {agent_address}"
            )
            if varbinds:
                description += f" - {SnmpProvider._format_varbinds(varbinds)}"

        alert = AlertDto(
            id=SnmpProvider._generate_trap_id(event),
            name=trap_name,
            description=description,
            severity=SnmpProvider._get_trap_severity(event),
            status=SnmpProvider._get_trap_status(event),
            source=["snmp"],
            lastReceived=datetime.now(tz=timezone.utc).isoformat(),
            trap_oid=trap_oid,
            agent_address=agent_address,
            community=event.get("community", ""),
            snmp_version=event.get("snmp_version", ""),
            enterprise=event.get("enterprise", ""),
            uptime=event.get("uptime", ""),
            varbinds=varbinds,
        )

        return alert


if __name__ == "__main__":
    pass
