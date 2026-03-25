"""
SNMP provider that ingests forwarded SNMP trap payloads via Keep webhooks.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class SnmpProvider(BaseProvider):
    """Get forwarded SNMP trap payloads into Keep."""

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send forwarded SNMP trap data to Keep:

1. Configure your SNMP receiver or forwarder to `POST` JSON to `{keep_webhook_api_url}`.
2. Add an `x-api-key` header with a valid Keep API key.
3. Forward either a single JSON object per trap or a JSON array for batches.
4. Include `trap_oid` (or `oid`) and `source_address` in each payload.
5. Add `entity_id` for interface-level traps so deduplication stays stable across repeated notifications.
"""

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]

    OID_NAME_MAP = {
        "1.3.6.1.6.3.1.1.5.1": "coldStart",
        "1.3.6.1.6.3.1.1.5.2": "warmStart",
        "1.3.6.1.6.3.1.1.5.3": "linkDown",
        "1.3.6.1.6.3.1.1.5.4": "linkUp",
        "1.3.6.1.6.3.1.1.5.5": "authenticationFailure",
        "1.3.6.1.6.3.1.1.5.6": "egpNeighborLoss",
    }

    OID_SEVERITY_MAP = {
        "1.3.6.1.6.3.1.1.5.1": AlertSeverity.WARNING,
        "1.3.6.1.6.3.1.1.5.2": AlertSeverity.WARNING,
        "1.3.6.1.6.3.1.1.5.3": AlertSeverity.CRITICAL,
        "1.3.6.1.6.3.1.1.5.4": AlertSeverity.INFO,
        "1.3.6.1.6.3.1.1.5.5": AlertSeverity.HIGH,
        "1.3.6.1.6.3.1.1.5.6": AlertSeverity.WARNING,
    }

    ENTITY_ID_HINTS = ("ifIndex", "ifName", "ifDescr")

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """SNMP forwarded webhook provider requires no local configuration."""
        return

    def dispose(self):
        """SNMP forwarded webhook provider does not hold external resources."""
        return

    @staticmethod
    def parse_event_raw_body(raw_body: bytes | dict | list[dict]) -> dict | list[dict]:
        if isinstance(raw_body, (dict, list)):
            return raw_body
        return json.loads(raw_body)

    @classmethod
    def _format_alert(
        cls, event: dict | list[dict], provider_instance: BaseProvider = None
    ) -> AlertDto | list[AlertDto]:
        if isinstance(event, list):
            return [cls._format_alert(item, provider_instance) for item in event]

        variables = cls._normalize_variables(
            event.get("variables") if isinstance(event, dict) else None
        )
        if not variables:
            variables = cls._normalize_variables(event.get("varbinds", {}))

        trap_oid = cls._extract_trap_oid(event)
        trap_name = cls._extract_trap_name(event, trap_oid)
        source_address = cls._extract_source_address(event)
        entity_id = cls._extract_entity_id(event, variables)
        explicit_fingerprint = cls._stringify(event.get("fingerprint"))

        message = cls._extract_message(event, variables, trap_name)
        description = cls._extract_description(event, variables, message, trap_name)
        timestamp = cls._coerce_timestamp(event.get("timestamp"))

        labels = {}
        extra_labels = event.get("labels")
        if isinstance(extra_labels, dict):
            labels.update(
                {
                    str(key): cls._stringify(value)
                    for key, value in extra_labels.items()
                    if cls._stringify(value)
                }
            )

        labels.update(
            {
                "trap_oid": trap_oid,
                "source_address": source_address,
                "entity_id": entity_id,
                "trap_name": trap_name,
                "forwarded_via": "json",
            }
        )

        return AlertDto(
            id=str(uuid.uuid4()),
            name=trap_name,
            status=AlertStatus.FIRING,
            severity=cls.OID_SEVERITY_MAP.get(trap_oid, AlertSeverity.WARNING),
            lastReceived=timestamp,
            environment="snmp",
            service="snmp",
            source=["snmp"],
            message=message,
            description=description,
            labels=labels,
            fingerprint=explicit_fingerprint
            or cls._build_fingerprint(source_address, trap_oid, entity_id),
        )

    @classmethod
    def _extract_trap_oid(cls, event: dict) -> str:
        return cls._stringify(event.get("trap_oid") or event.get("oid"))

    @classmethod
    def _extract_trap_name(cls, event: dict, trap_oid: str) -> str:
        explicit_name = cls._stringify(event.get("trap_name"))
        if explicit_name:
            return explicit_name
        if trap_oid in cls.OID_NAME_MAP:
            return cls.OID_NAME_MAP[trap_oid]
        if trap_oid:
            return trap_oid
        return "SNMP Trap"

    @classmethod
    def _extract_source_address(cls, event: dict) -> str:
        for key in ("source_address", "source", "host", "ip", "address"):
            value = cls._stringify(event.get(key))
            if value:
                return value
        return ""

    @classmethod
    def _extract_message(
        cls, event: dict, variables: dict[str, str], trap_name: str
    ) -> str:
        explicit_message = cls._stringify(event.get("message"))
        if explicit_message:
            return explicit_message
        summary = cls._render_variables_summary(variables)
        if summary:
            return summary
        return trap_name

    @classmethod
    def _extract_description(
        cls, event: dict, variables: dict[str, str], message: str, trap_name: str
    ) -> str:
        explicit_description = cls._stringify(event.get("description"))
        if explicit_description:
            return explicit_description
        variables_block = cls._render_variables_block(variables)
        if variables_block:
            return variables_block
        return message or trap_name

    @classmethod
    def _extract_entity_id(cls, event: dict, variables: dict[str, str]) -> str:
        explicit_entity_id = cls._stringify(event.get("entity_id"))
        if explicit_entity_id:
            return explicit_entity_id

        for candidate in cls.ENTITY_ID_HINTS:
            normalized_candidate = candidate.lower()
            for key, value in variables.items():
                searchable_key = re.sub(r"[^a-z0-9]+", "", key.lower())
                if normalized_candidate.lower() in searchable_key and value:
                    return value
        return ""

    @staticmethod
    def _build_fingerprint(source_address: str, trap_oid: str, entity_id: str) -> str:
        parts = [source_address, trap_oid]
        if entity_id:
            parts.append(entity_id)
        fingerprint_payload = "|".join(parts)
        return hashlib.sha256(
            fingerprint_payload.encode("utf-8", errors="replace")
        ).hexdigest()

    @classmethod
    def _normalize_variables(cls, variables: Any) -> dict[str, str]:
        if isinstance(variables, dict):
            return {
                str(key): cls._stringify(value)
                for key, value in variables.items()
                if cls._stringify(value) != ""
            }

        if isinstance(variables, list):
            normalized = {}
            for index, item in enumerate(variables):
                if isinstance(item, dict):
                    key = (
                        item.get("name")
                        or item.get("oid")
                        or item.get("key")
                        or item.get("label")
                        or f"var_{index}"
                    )
                    value = item.get("value")
                    if value is None and len(item) == 1:
                        value = next(iter(item.values()))
                else:
                    key = f"var_{index}"
                    value = item
                value_str = cls._stringify(value)
                if value_str:
                    normalized[str(key)] = value_str
            return normalized

        return {}

    @staticmethod
    def _render_variables_summary(variables: dict[str, str]) -> str:
        if not variables:
            return ""
        summary_items = list(variables.items())[:3]
        summary = ", ".join(f"{key}={value}" for key, value in summary_items)
        remaining = len(variables) - len(summary_items)
        if remaining > 0:
            summary += f", +{remaining} more"
        return summary

    @staticmethod
    def _render_variables_block(variables: dict[str, str]) -> str:
        if not variables:
            return ""
        return "\n".join(f"{key}: {value}" for key, value in variables.items())

    @staticmethod
    def _coerce_timestamp(value: Any) -> str:
        now = datetime.now(timezone.utc).isoformat()
        if value is None:
            return now

        raw_value = str(value).strip()
        if not raw_value:
            return now

        try:
            float(raw_value.rstrip("Z"))
            return raw_value
        except ValueError:
            pass

        normalized = raw_value[:-1] + "+00:00" if raw_value.endswith("Z") else raw_value
        try:
            datetime.fromisoformat(normalized)
            return raw_value
        except ValueError:
            return now

    @staticmethod
    def _stringify(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, sort_keys=True)
            except TypeError:
                return str(value)
        return str(value).strip()


if __name__ == "__main__":
    pass
