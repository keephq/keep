"""
SNMP Provider maps normalized SNMP traps/events into Keep alerts.

The provider intentionally does not open UDP sockets. Keep already exposes a
generic provider webhook path, so trap receivers can forward decoded SNMP
payloads as JSON and reuse the existing ingestion, auth, and alert pipeline.
"""

import dataclasses
import json
from typing import Any

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP webhook ingestion does not require provider-side credentials.

    The shared Keep webhook API key still protects the ingestion endpoint.
    """

    default_severity: str = dataclasses.field(
        default="warning",
        metadata={
            "required": False,
            "description": "Default severity when the SNMP payload has no severity",
            "sensitive": False,
        },
    )


class SnmpProvider(BaseProvider):
    """
    Receive SNMP traps/events forwarded as JSON webhooks.
    """

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
Forward decoded SNMP traps to Keep using the provider webhook URL:

`{keep_webhook_api_url}`

The provider accepts common normalized trap fields such as `trap_oid`,
`source_ip`, `agent_address`, `timestamp`, `severity`, `status`, and
`varbinds`. Variable bindings can be either an array of objects with `oid`,
`name`, and `value` keys or a dictionary of OID/name to value.
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["fingerprint"]

    SEVERITY_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "crit": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "major": AlertSeverity.HIGH,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "warn": AlertSeverity.WARNING,
        "minor": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "informational": AlertSeverity.INFO,
        "ok": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
    }

    STATUS_MAP = {
        "resolved": AlertStatus.RESOLVED,
        "resolve": AlertStatus.RESOLVED,
        "recovery": AlertStatus.RESOLVED,
        "recovered": AlertStatus.RESOLVED,
        "clear": AlertStatus.RESOLVED,
        "cleared": AlertStatus.RESOLVED,
        "ok": AlertStatus.RESOLVED,
        "up": AlertStatus.RESOLVED,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "ack": AlertStatus.ACKNOWLEDGED,
        "suppressed": AlertStatus.SUPPRESSED,
        "firing": AlertStatus.FIRING,
        "triggered": AlertStatus.FIRING,
        "problem": AlertStatus.FIRING,
        "down": AlertStatus.FIRING,
        "alarm": AlertStatus.FIRING,
    }

    WELL_KNOWN_TRAP_SEVERITIES = {
        "1.3.6.1.6.3.1.1.5.1": AlertSeverity.INFO,  # coldStart
        "1.3.6.1.6.3.1.1.5.2": AlertSeverity.WARNING,  # warmStart
        "1.3.6.1.6.3.1.1.5.3": AlertSeverity.CRITICAL,  # linkDown
        "1.3.6.1.6.3.1.1.5.4": AlertSeverity.INFO,  # linkUp
        "1.3.6.1.6.3.1.1.5.5": AlertSeverity.WARNING,  # authenticationFailure
        "1.3.6.1.6.3.1.1.5.6": AlertSeverity.INFO,  # egpNeighborLoss
    }

    WELL_KNOWN_TRAP_NAMES = {
        "1.3.6.1.6.3.1.1.5.1": "SNMP coldStart",
        "1.3.6.1.6.3.1.1.5.2": "SNMP warmStart",
        "1.3.6.1.6.3.1.1.5.3": "SNMP linkDown",
        "1.3.6.1.6.3.1.1.5.4": "SNMP linkUp",
        "1.3.6.1.6.3.1.1.5.5": "SNMP authenticationFailure",
        "1.3.6.1.6.3.1.1.5.6": "SNMP egpNeighborLoss",
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SnmpProviderAuthConfig(
            **(self.config.authentication or {})
        )

    def dispose(self):
        pass

    @staticmethod
    def _first_value(event: dict, *keys: str) -> Any:
        for key in keys:
            value = event.get(key)
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _normalize_string(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return str(value)

    @staticmethod
    def _extract_varbinds(event: dict) -> dict[str, Any]:
        raw_varbinds = event.get("varbinds") or event.get("variable_bindings") or {}
        normalized: dict[str, Any] = {}

        if isinstance(raw_varbinds, dict):
            for key, value in raw_varbinds.items():
                normalized[str(key)] = value
            return normalized

        if isinstance(raw_varbinds, list):
            for index, varbind in enumerate(raw_varbinds):
                if not isinstance(varbind, dict):
                    normalized[f"varbind_{index}"] = varbind
                    continue
                key = (
                    varbind.get("name")
                    or varbind.get("oid")
                    or varbind.get("mib")
                    or f"varbind_{index}"
                )
                normalized[str(key)] = varbind.get("value")
            return normalized

        return normalized

    @classmethod
    def _parse_status(cls, event: dict, trap_oid: str | None) -> AlertStatus:
        status = cls._first_value(event, "status", "state", "event_status", "type")
        normalized_status = cls._normalize_string(status)
        if normalized_status:
            mapped = cls.STATUS_MAP.get(normalized_status.lower())
            if mapped:
                return mapped

        if trap_oid == "1.3.6.1.6.3.1.1.5.4":
            return AlertStatus.RESOLVED

        return AlertStatus.FIRING

    @classmethod
    def _parse_severity(
        cls, event: dict, trap_oid: str | None, provider_instance: BaseProvider | None
    ) -> AlertSeverity:
        severity = cls._first_value(event, "severity", "level", "priority")
        normalized_severity = cls._normalize_string(severity)
        if normalized_severity:
            mapped = cls.SEVERITY_MAP.get(normalized_severity.lower())
            if mapped:
                return mapped

        if trap_oid in cls.WELL_KNOWN_TRAP_SEVERITIES:
            return cls.WELL_KNOWN_TRAP_SEVERITIES[trap_oid]

        if provider_instance and hasattr(provider_instance, "authentication_config"):
            default_severity = getattr(
                provider_instance.authentication_config, "default_severity", "warning"
            )
            return cls.SEVERITY_MAP.get(default_severity.lower(), AlertSeverity.WARNING)

        return AlertSeverity.WARNING

    @staticmethod
    def _format_description(event: dict, varbinds: dict[str, Any]) -> str:
        description = SnmpProvider._first_value(
            event, "description", "message", "summary", "details"
        )
        if description:
            return str(description)

        if not varbinds:
            return "SNMP trap received"

        preview = {key: varbinds[key] for key in list(varbinds)[:8]}
        return f"SNMP trap varbinds: {json.dumps(preview, sort_keys=True, default=str)}"

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: BaseProvider = None
    ) -> AlertDto | list[AlertDto]:
        trap_oid = SnmpProvider._normalize_string(
            SnmpProvider._first_value(event, "trap_oid", "snmpTrapOID", "oid")
        )
        source_host = SnmpProvider._normalize_string(
            SnmpProvider._first_value(
                event, "source_ip", "agent_address", "agent", "host", "hostname"
            )
        )
        varbinds = SnmpProvider._extract_varbinds(event)
        trap_name = SnmpProvider.WELL_KNOWN_TRAP_NAMES.get(trap_oid)
        name = (
            SnmpProvider._normalize_string(
                SnmpProvider._first_value(event, "name", "title", "alert_name")
            )
            or trap_name
            or f"SNMP trap {trap_oid or 'unknown'}"
        )
        timestamp = SnmpProvider._first_value(
            event, "timestamp", "received_at", "time", "lastReceived"
        )
        status = SnmpProvider._parse_status(event, trap_oid)
        severity = SnmpProvider._parse_severity(event, trap_oid, provider_instance)
        fingerprint_parts = [
            "snmp",
            source_host or "unknown-source",
            trap_oid or "unknown-trap",
            SnmpProvider._normalize_string(event.get("specific_trap")) or "",
        ]

        labels = {
            "trap_oid": trap_oid,
            "source_host": source_host,
            "generic_trap": SnmpProvider._normalize_string(event.get("generic_trap")),
            "specific_trap": SnmpProvider._normalize_string(event.get("specific_trap")),
        }
        labels = {key: value for key, value in labels.items() if value}

        return AlertDto(
            id=SnmpProvider._normalize_string(
                SnmpProvider._first_value(event, "id", "event_id", "request_id")
            ),
            name=name,
            status=status,
            severity=severity,
            lastReceived=timestamp,
            description=SnmpProvider._format_description(event, varbinds),
            message=SnmpProvider._normalize_string(
                SnmpProvider._first_value(event, "message", "summary")
            ),
            source=["snmp"],
            service=SnmpProvider._normalize_string(
                SnmpProvider._first_value(event, "service", "interface")
            ),
            hostname=source_host,
            trap_oid=trap_oid,
            varbinds=varbinds,
            labels=labels,
            fingerprint=":".join(part for part in fingerprint_parts if part),
            pushed=True,
        )
