"""
SNMP Provider is a webhook-first provider for decoded SNMP trap events.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
from typing import Any

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class SnmpProvider(BaseProvider):
    """
    Get decoded SNMP traps into Keep via webhook forwarding.

    SNMP devices usually emit UDP traps, while Keep providers ingest HTTP webhook
    events. Run snmptrapd, snmptt, Telegraf, or another relay to decode traps and
    forward JSON payloads to Keep's `/alerts/event/snmp` endpoint.
    """

    webhook_description = (
        "Forward decoded SNMP trap JSON to Keep's SNMP webhook endpoint."
    )
    webhook_template = """
curl -X POST "{keep_webhook_api_url}" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: {api_key}" \
  -d '{"source_ip":"10.0.0.15","generic_trap":"linkDown","trap_oid":"1.3.6.1.6.3.1.1.5.3"}'
"""
    webhook_markdown = """
Configure an SNMP trap receiver such as snmptrapd, snmptt, Telegraf, or a small
bridge script to decode UDP traps and POST JSON to `{keep_webhook_api_url}` with
the `X-API-KEY` header set to `{api_key}`.
"""

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    WEBHOOK_INSTALLATION_REQUIRED = True
    PROVIDER_DOCS_SLUG = "snmp-provider"
    FINGERPRINT_FIELDS = ["id"]

    HOST_KEYS = (
        "host",
        "hostname",
        "source_ip",
        "agent_address",
        "source",
        "agent",
        "ip",
    )
    TRAP_OID_KEYS = ("trap_oid", "snmpTrapOID", "snmp_trap_oid", "oid", "trapOid")
    GENERIC_TRAP_KEYS = (
        "generic_trap",
        "trap_type",
        "genericTrap",
        "generic_trap_type",
    )
    VARBIND_KEYS = ("varbinds", "vars", "variable_bindings", "bindings")
    TIMESTAMP_KEYS = (
        "timestamp",
        "time",
        "received_at",
        "lastReceived",
        "last_received",
    )
    EVENT_ID_KEYS = ("id", "event_id", "trap_id", "notification_id")

    GENERIC_TRAP_NUMBERS = {
        "0": "coldStart",
        "1": "warmStart",
        "2": "linkDown",
        "3": "linkUp",
        "4": "authenticationFailure",
        "5": "egpNeighborLoss",
        "6": "enterpriseSpecific",
    }

    TRAP_OID_TO_NAME = {
        "1.3.6.1.6.3.1.1.5.1": "coldStart",
        "1.3.6.1.6.3.1.1.5.2": "warmStart",
        "1.3.6.1.6.3.1.1.5.3": "linkDown",
        "1.3.6.1.6.3.1.1.5.4": "linkUp",
        "1.3.6.1.6.3.1.1.5.5": "authenticationFailure",
        "1.3.6.1.6.3.1.1.5.6": "egpNeighborLoss",
    }

    TRAP_DEFAULTS = {
        "coldStart": (AlertStatus.FIRING, AlertSeverity.INFO),
        "warmStart": (AlertStatus.FIRING, AlertSeverity.INFO),
        "linkDown": (AlertStatus.FIRING, AlertSeverity.CRITICAL),
        "linkUp": (AlertStatus.RESOLVED, AlertSeverity.INFO),
        "authenticationFailure": (AlertStatus.FIRING, AlertSeverity.WARNING),
        "egpNeighborLoss": (AlertStatus.FIRING, AlertSeverity.CRITICAL),
        "enterpriseSpecific": (AlertStatus.FIRING, AlertSeverity.INFO),
    }

    STATUS_ALIASES = {
        "firing": AlertStatus.FIRING,
        "triggered": AlertStatus.FIRING,
        "active": AlertStatus.FIRING,
        "problem": AlertStatus.FIRING,
        "down": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "resolve": AlertStatus.RESOLVED,
        "ok": AlertStatus.RESOLVED,
        "up": AlertStatus.RESOLVED,
        "cleared": AlertStatus.RESOLVED,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "ack": AlertStatus.ACKNOWLEDGED,
        "suppressed": AlertStatus.SUPPRESSED,
        "pending": AlertStatus.PENDING,
        "maintenance": AlertStatus.MAINTENANCE,
    }

    SEVERITY_ALIASES = {
        "critical": AlertSeverity.CRITICAL,
        "crit": AlertSeverity.CRITICAL,
        "fatal": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "error": AlertSeverity.HIGH,
        "err": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "warn": AlertSeverity.WARNING,
        "minor": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "informational": AlertSeverity.INFO,
        "notice": AlertSeverity.INFO,
        "normal": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
        "debug": AlertSeverity.LOW,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        pass

    @staticmethod
    def _format_alert(
        event: dict | list[dict], provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        if isinstance(event, list):
            return [SnmpProvider._format_single_alert(item) for item in event]

        return SnmpProvider._format_single_alert(event or {})

    @staticmethod
    def _format_single_alert(event: dict[str, Any]) -> AlertDto:
        event = event if isinstance(event, dict) else {}
        host = str(
            SnmpProvider._first_present(event, SnmpProvider.HOST_KEYS, "unknown")
        )
        varbinds = SnmpProvider._normalize_varbinds(
            SnmpProvider._first_present(event, SnmpProvider.VARBIND_KEYS, [])
        )
        trap_oid = SnmpProvider._extract_trap_oid(event, varbinds)
        generic_trap = SnmpProvider._normalize_generic_trap(
            SnmpProvider._first_present(event, SnmpProvider.GENERIC_TRAP_KEYS)
        )
        trap_name = SnmpProvider._trap_name_from_oid_or_type(
            event=event, trap_oid=trap_oid, generic_trap=generic_trap
        )
        status, severity = SnmpProvider.TRAP_DEFAULTS.get(
            trap_name, (AlertStatus.FIRING, AlertSeverity.INFO)
        )
        status = SnmpProvider._normalize_status(event.get("status"), status)
        severity = SnmpProvider._normalize_severity(event.get("severity"), severity)
        labels = SnmpProvider._build_labels(event, host, trap_oid, trap_name, varbinds)
        alert_id = SnmpProvider._stable_id(
            event=event,
            host=host,
            trap_oid=trap_oid,
            generic_trap=trap_name,
            varbinds=varbinds,
        )
        last_received = SnmpProvider._normalize_timestamp(
            SnmpProvider._first_present(event, SnmpProvider.TIMESTAMP_KEYS)
        )
        varbind_summary = SnmpProvider._summarize_varbinds(varbinds)
        message_parts = [f"{trap_name} from {host}"]
        if trap_oid:
            message_parts.append(f"trap_oid={trap_oid}")
        if varbind_summary:
            message_parts.append(f"varbinds: {varbind_summary}")
        message = "; ".join(message_parts)

        return AlertDto(
            id=alert_id,
            name=f"SNMP {trap_name} on {host}",
            description=f"SNMP trap {trap_name} received from {host}.",
            message=message,
            host=host,
            hostname=host,
            service=host,
            source=["snmp"],
            status=status,
            severity=severity,
            lastReceived=last_received,
            pushed=True,
            labels=labels,
            fingerprint=alert_id,
            trap_oid=trap_oid,
            generic_trap=trap_name,
            specific_trap=event.get("specific_trap") or event.get("specificTrap"),
            enterprise_oid=event.get("enterprise_oid") or event.get("enterpriseOid"),
            snmp_varbinds=varbinds,
            snmp_event=event,
        )

    @staticmethod
    def _first_present(event: dict[str, Any], keys: tuple[str, ...], default=None):
        for key in keys:
            value = event.get(key)
            if value is not None and value != "":
                return value
        return default

    @staticmethod
    def _normalize_status(value: Any, default: AlertStatus) -> AlertStatus:
        if isinstance(value, AlertStatus):
            return value
        if value is None:
            return default
        normalized = str(value).strip().lower().replace("_", "-")
        normalized = normalized.replace("-", "_")
        return SnmpProvider.STATUS_ALIASES.get(normalized, default)

    @staticmethod
    def _normalize_severity(value: Any, default: AlertSeverity) -> AlertSeverity:
        if isinstance(value, AlertSeverity):
            return value
        if value is None:
            return default
        if isinstance(value, int):
            try:
                return AlertSeverity.from_number(value)
            except ValueError:
                return default
        normalized = str(value).strip().lower().replace("_", " ").replace("-", " ")
        return SnmpProvider.SEVERITY_ALIASES.get(normalized, default)

    @staticmethod
    def _normalize_generic_trap(value: Any) -> str | None:
        if value is None:
            return None
        value = str(value).strip()
        if not value:
            return None
        return SnmpProvider.GENERIC_TRAP_NUMBERS.get(value, value)

    @staticmethod
    def _extract_trap_oid(
        event: dict[str, Any], varbinds: list[dict[str, Any]]
    ) -> str | None:
        trap_oid = SnmpProvider._first_present(event, SnmpProvider.TRAP_OID_KEYS)
        if trap_oid:
            return str(trap_oid)

        for varbind in varbinds:
            oid = str(varbind.get("oid") or "")
            name = str(varbind.get("name") or "")
            if oid == "1.3.6.1.6.3.1.1.4.1.0" or name == "snmpTrapOID.0":
                value = varbind.get("value")
                return str(value) if value is not None else None
        return None

    @staticmethod
    def _trap_name_from_oid_or_type(
        event: dict[str, Any], trap_oid: str | None, generic_trap: str | None
    ) -> str:
        explicit_name = SnmpProvider._first_present(
            event, ("trap_name", "trapName", "trap", "event_name")
        )
        if explicit_name:
            return str(explicit_name)
        if generic_trap:
            return generic_trap
        if trap_oid:
            return SnmpProvider.TRAP_OID_TO_NAME.get(str(trap_oid), "SNMP Trap")
        return "SNMP Trap"

    @staticmethod
    def _normalize_varbinds(value: Any) -> list[dict[str, Any]]:
        if value is None:
            return []

        normalized = []
        if isinstance(value, dict):
            iterable = [
                {"oid": oid, "value": binding_value}
                for oid, binding_value in value.items()
            ]
        elif isinstance(value, list):
            iterable = value
        else:
            return [{"name": "value", "value": value}]

        for item in iterable:
            if isinstance(item, dict):
                if "oid" in item or "name" in item or "value" in item:
                    normalized.append(
                        {
                            "oid": item.get("oid")
                            or item.get("object")
                            or item.get("key"),
                            "name": item.get("name") or item.get("label"),
                            "value": (
                                item.get("value")
                                if "value" in item
                                else item.get("val", item.get("data"))
                            ),
                        }
                    )
                elif len(item) == 1:
                    oid, binding_value = next(iter(item.items()))
                    normalized.append({"oid": oid, "value": binding_value})
            elif isinstance(item, (tuple, list)) and len(item) >= 2:
                normalized.append({"oid": item[0], "value": item[1]})
            else:
                normalized.append({"value": item})

        return [
            {
                key: SnmpProvider._stringify_label_value(val)
                for key, val in binding.items()
                if val is not None and val != ""
            }
            for binding in normalized
        ]

    @staticmethod
    def _build_labels(
        event: dict[str, Any],
        host: str,
        trap_oid: str | None,
        trap_name: str,
        varbinds: list[dict[str, Any]],
    ) -> dict[str, str]:
        labels = {
            "snmp_host": host,
            "snmp_trap": trap_name,
        }
        optional_label_fields = {
            "snmp_version": event.get("version"),
            "snmp_community": event.get("community"),
            "snmp_source_ip": event.get("source_ip"),
            "snmp_agent_address": event.get("agent_address"),
            "snmp_enterprise_oid": event.get("enterprise_oid")
            or event.get("enterpriseOid"),
            "snmp_trap_oid": trap_oid,
            "snmp_generic_trap": SnmpProvider._normalize_generic_trap(
                SnmpProvider._first_present(event, SnmpProvider.GENERIC_TRAP_KEYS)
            ),
            "snmp_specific_trap": event.get("specific_trap")
            or event.get("specificTrap"),
        }
        labels.update(
            {
                key: SnmpProvider._stringify_label_value(value)
                for key, value in optional_label_fields.items()
                if value is not None and value != ""
            }
        )

        for varbind in varbinds:
            value = varbind.get("value")
            if value is None:
                continue
            name = varbind.get("name")
            oid = varbind.get("oid")
            if name:
                labels[SnmpProvider._dedupe_label_key(labels, name)] = value
            if oid:
                oid_key = "oid_" + SnmpProvider._sanitize_label_key(oid)
                labels[SnmpProvider._dedupe_label_key(labels, oid_key)] = value

        return labels

    @staticmethod
    def _sanitize_label_key(value: Any) -> str:
        key = re.sub(r"[^A-Za-z0-9_]+", "_", str(value).strip())
        key = re.sub(r"_+", "_", key).strip("_")
        return key or "value"

    @staticmethod
    def _dedupe_label_key(labels: dict[str, str], key: Any) -> str:
        sanitized = SnmpProvider._sanitize_label_key(key)
        if sanitized not in labels:
            return sanitized
        counter = 2
        while f"{sanitized}_{counter}" in labels:
            counter += 1
        return f"{sanitized}_{counter}"

    @staticmethod
    def _stable_id(
        event: dict[str, Any],
        host: str,
        trap_oid: str | None,
        generic_trap: str,
        varbinds: list[dict[str, Any]],
    ) -> str:
        explicit_id = SnmpProvider._first_present(event, SnmpProvider.EVENT_ID_KEYS)
        if explicit_id:
            return str(explicit_id)

        specific_trap = event.get("specific_trap") or event.get("specificTrap")
        stable_payload = {
            "host": host,
            "trap_oid": trap_oid,
            "generic_trap": generic_trap,
            "specific_trap": specific_trap,
            "varbinds": sorted(
                varbinds, key=lambda item: (item.get("oid", ""), item.get("name", ""))
            ),
        }
        digest = hashlib.sha256(
            json.dumps(stable_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return f"snmp-{digest}"

    @staticmethod
    def _normalize_timestamp(value: Any) -> str:
        if value is None or value == "":
            return datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        if isinstance(value, (int, float)):
            return datetime.datetime.fromtimestamp(
                float(value), tz=datetime.timezone.utc
            ).isoformat()
        if isinstance(value, datetime.datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=datetime.timezone.utc)
            return value.astimezone(datetime.timezone.utc).isoformat()

        timestamp = str(value).strip()
        if timestamp.isdigit():
            return datetime.datetime.fromtimestamp(
                float(timestamp), tz=datetime.timezone.utc
            ).isoformat()
        try:
            parsed = datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=datetime.timezone.utc)
            return parsed.astimezone(datetime.timezone.utc).isoformat()
        except ValueError:
            return datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

    @staticmethod
    def _summarize_varbinds(varbinds: list[dict[str, Any]]) -> str:
        summary_parts = []
        for varbind in varbinds[:5]:
            key = varbind.get("name") or varbind.get("oid") or "value"
            summary_parts.append(f"{key}={varbind.get('value')}")
        return ", ".join(summary_parts)

    @staticmethod
    def _stringify_label_value(value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, sort_keys=True)
        return str(value)
