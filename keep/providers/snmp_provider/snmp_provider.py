"""
SNMP Provider is a class that allows to ingest SNMP traps/events into Keep as alerts.

It works by receiving SNMP trap data forwarded from an external snmptrapd instance
via HTTP webhook. The snmptrapd is configured to forward traps to Keep's webhook
endpoint using a script or native HTTP forwarding.
"""

import dataclasses
import datetime
import hashlib
import json
import logging
from typing import Union

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)

# Well-known SNMP trap OIDs (SNMPv2-MIB::snmpTraps)
WELL_KNOWN_TRAPS = {
    "1.3.6.1.6.3.1.1.5.1": "coldStart",
    "1.3.6.1.6.3.1.1.5.2": "warmStart",
    "1.3.6.1.6.3.1.1.5.3": "linkDown",
    "1.3.6.1.6.3.1.1.5.4": "linkUp",
    "1.3.6.1.6.3.1.1.5.5": "authenticationFailure",
}

# SNMPv1 generic trap type to OID mapping
GENERIC_TRAP_OIDS = {
    0: "1.3.6.1.6.3.1.1.5.1",  # coldStart
    1: "1.3.6.1.6.3.1.1.5.2",  # warmStart
    2: "1.3.6.1.6.3.1.1.5.3",  # linkDown
    3: "1.3.6.1.6.3.1.1.5.4",  # linkUp
    4: "1.3.6.1.6.3.1.1.5.5",  # authenticationFailure
    5: "1.3.6.1.6.3.1.1.5.5",  # egpNeighborLoss (map to authFailure severity)
}


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """SNMP provider authentication configuration."""

    community_string: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "Expected SNMP community string for verification (leave empty to accept all)",
            "sensitive": True,
        },
    )


class SnmpProvider(BaseProvider):
    """Receive SNMP traps/events as Keep alerts via webhook."""

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]

    SEVERITY_MAP = {
        "coldStart": AlertSeverity.INFO,
        "warmStart": AlertSeverity.INFO,
        "linkDown": AlertSeverity.CRITICAL,
        "linkUp": AlertSeverity.INFO,
        "authenticationFailure": AlertSeverity.WARNING,
    }

    STATUS_MAP = {
        "linkUp": AlertStatus.RESOLVED,
    }

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    @staticmethod
    def parse_event_raw_body(raw_body: Union[bytes, dict]) -> dict:
        """Parse incoming SNMP trap webhook payload.

        Accepts JSON payloads forwarded from snmptrapd via HTTP.
        """
        if isinstance(raw_body, dict):
            return raw_body
        if isinstance(raw_body, bytes):
            try:
                return json.loads(raw_body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return {"raw": raw_body.decode("utf-8", errors="replace")}
        return {"raw": str(raw_body)}

    @staticmethod
    def _get_trap_name(event: dict) -> str:
        """Resolve a human-readable trap name from the event."""
        trap_oid = event.get("trap_oid", "")

        # Check well-known OIDs
        if trap_oid in WELL_KNOWN_TRAPS:
            return WELL_KNOWN_TRAPS[trap_oid]

        # Check SNMPv1 generic_trap field
        generic_trap = event.get("generic_trap")
        if generic_trap is not None:
            try:
                generic_int = int(generic_trap)
                oid = GENERIC_TRAP_OIDS.get(generic_int)
                if oid and oid in WELL_KNOWN_TRAPS:
                    return WELL_KNOWN_TRAPS[oid]
            except (ValueError, TypeError):
                pass

        # Fall back to OID or "Unknown Trap"
        if trap_oid:
            return f"trap:{trap_oid}"
        return "Unknown SNMP Trap"

    @staticmethod
    def _get_severity(trap_name: str, event: dict) -> AlertSeverity:
        """Map trap name to severity."""
        severity = SnmpProvider.SEVERITY_MAP.get(trap_name)
        if severity:
            return severity

        # Check if severity is provided in the event
        raw_severity = event.get("severity", "").lower()
        severity_map = {
            "critical": AlertSeverity.CRITICAL,
            "high": AlertSeverity.HIGH,
            "warning": AlertSeverity.WARNING,
            "info": AlertSeverity.INFO,
            "low": AlertSeverity.LOW,
        }
        if raw_severity in severity_map:
            return severity_map[raw_severity]

        # Enterprise-specific traps default to WARNING
        return AlertSeverity.WARNING

    @staticmethod
    def _get_status(trap_name: str) -> AlertStatus:
        """Map trap name to alert status."""
        return SnmpProvider.STATUS_MAP.get(trap_name, AlertStatus.FIRING)

    @staticmethod
    def _build_fingerprint(event: dict, trap_name: str) -> str:
        """Build a deduplication fingerprint from trap OID and source."""
        source_ip = event.get("source_ip", event.get("agent_address", "unknown"))
        trap_oid = event.get("trap_oid", trap_name)
        raw = f"snmp:{source_ip}:{trap_oid}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _format_description(event: dict, trap_name: str) -> str:
        """Build a human-readable description from the trap event."""
        source_ip = event.get("source_ip", event.get("agent_address", "unknown"))
        version = event.get("version", "unknown")
        parts = [f"SNMP trap '{trap_name}' from {source_ip} (SNMPv{version})"]

        varbinds = event.get("varbinds", [])
        if varbinds:
            parts.append(f"Variable bindings ({len(varbinds)}):")
            for vb in varbinds[:10]:  # Limit to first 10
                oid = vb.get("oid", "?")
                value = vb.get("value", "?")
                parts.append(f"  {oid} = {value}")

        return "\n".join(parts)

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """Convert SNMP trap event into AlertDto."""
        trap_name = SnmpProvider._get_trap_name(event)
        severity = SnmpProvider._get_severity(trap_name, event)
        status = SnmpProvider._get_status(trap_name)
        fingerprint = SnmpProvider._build_fingerprint(event, trap_name)
        description = SnmpProvider._format_description(event, trap_name)

        source_ip = event.get("source_ip", event.get("agent_address", "unknown"))
        trap_oid = event.get("trap_oid", "")
        timestamp = event.get(
            "timestamp",
            datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
        )

        # Build labels from trap metadata + varbinds
        labels = {
            "trap_oid": trap_oid,
            "source_ip": source_ip,
            "snmp_version": str(event.get("version", "unknown")),
        }
        community = event.get("community")
        if community:
            labels["community"] = community
        enterprise = event.get("enterprise")
        if enterprise:
            labels["enterprise"] = enterprise

        # Add varbinds as labels
        for vb in event.get("varbinds", []):
            oid = vb.get("oid", "")
            value = vb.get("value", "")
            if oid and value:
                labels[f"varbind:{oid}"] = str(value)

        return AlertDto(
            id=event.get("id", fingerprint[:12]),
            name=f"SNMP Trap: {trap_name}",
            status=status,
            severity=severity,
            lastReceived=timestamp,
            description=description,
            source=["snmp"],
            pushed=True,
            fingerprint=fingerprint,
            labels=labels,
            hostname=source_ip,
            service=source_ip,
            ip_address=source_ip,
        )
