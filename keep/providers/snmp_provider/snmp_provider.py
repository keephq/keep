"""
SnmpProvider ingests SNMP traps into Keep as alerts.

SNMP traps arrive via a small `snmptrapd` exec hook that POSTs the parsed
trap as JSON to Keep's generic webhook endpoint. See
`docs/providers/documentation/snmp-provider.mdx` for the bridge setup.
"""

import dataclasses
import datetime
import hashlib

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """SNMP provider configuration.

    The provider itself is passive (receives JSON-over-HTTPS posted by the
    trap bridge), so no credentials are required. These fields tune how
    incoming traps are interpreted.
    """

    default_severity: str = dataclasses.field(
        default="info",
        metadata={
            "required": False,
            "description": (
                "Severity assigned to a trap when the payload does not specify one "
                "and the trap OID is not in the built-in mapping."
            ),
            "type": "select",
            "options": ["critical", "high", "warning", "info", "low"],
            "sensitive": False,
        },
    )
    community_string: str = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": (
                "Expected SNMP community string. Documented for the trap "
                "bridge; the provider itself does not enforce it."
            ),
            "sensitive": False,
        },
    )


# Well-known SNMP trap OIDs from RFC 1907 / RFC 3418 with reasonable
# default severities. Users can override any of these in the bridge.
_STANDARD_TRAP_OIDS = {
    "1.3.6.1.6.3.1.1.5.1": ("coldStart", AlertSeverity.INFO),
    "1.3.6.1.6.3.1.1.5.2": ("warmStart", AlertSeverity.INFO),
    "1.3.6.1.6.3.1.1.5.3": ("linkDown", AlertSeverity.HIGH),
    "1.3.6.1.6.3.1.1.5.4": ("linkUp", AlertSeverity.INFO),
    "1.3.6.1.6.3.1.1.5.5": ("authenticationFailure", AlertSeverity.WARNING),
    "1.3.6.1.6.3.1.1.5.6": ("egpNeighborLoss", AlertSeverity.WARNING),
}


class SnmpProvider(BaseProvider):
    """Ingest SNMP traps into Keep as alerts."""

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]

    FINGERPRINT_FIELDS = ["trap_oid", "source_address"]

    webhook_description = (
        "This provider ingests SNMP traps via a small `snmptrapd` exec hook "
        "that POSTs each trap as JSON to the Keep webhook URL below. "
        "See the SNMP provider docs for the bridge script and "
        "`snmptrapd.conf` snippet."
    )
    webhook_template = (
        "POST {keep_webhook_api_url}\n"
        "Headers:\n"
        "  X-API-KEY: {api_key}\n"
        "  Content-Type: application/json\n"
        "Body (example):\n"
        "{{\n"
        '  "trap_oid": "1.3.6.1.6.3.1.1.5.3",\n'
        '  "trap_name": "linkDown",\n'
        '  "source_address": "192.0.2.10",\n'
        '  "variables": {{"1.3.6.1.2.1.2.2.1.1": "2"}},\n'
        '  "community": "public",\n'
        '  "version": "2c"\n'
        "}}"
    )

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "error": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "medium": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
    }

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """Validate the provider configuration."""
        self.authentication_config = SnmpProviderAuthConfig(
            **(self.config.authentication or {})
        )

    def dispose(self):
        """Nothing to clean up; the provider holds no connections."""
        return

    @staticmethod
    def _resolve_name(event: dict) -> str:
        """Pick a human-friendly alert name for a trap event."""
        if event.get("trap_name"):
            return str(event["trap_name"])
        trap_oid = event.get("trap_oid") or ""
        if trap_oid in _STANDARD_TRAP_OIDS:
            return _STANDARD_TRAP_OIDS[trap_oid][0]
        if trap_oid:
            # Use the last numeric segment as a last resort name.
            return f"snmp_trap_{trap_oid.rsplit('.', 1)[-1]}"
        return "snmp_trap"

    @staticmethod
    def _resolve_severity(event: dict, default_severity: str) -> AlertSeverity:
        """Resolve severity: explicit field > well-known OID map > default."""
        raw = event.get("severity")
        if isinstance(raw, str) and raw.strip():
            mapped = SnmpProvider.SEVERITIES_MAP.get(raw.strip().lower())
            if mapped is not None:
                return mapped
        trap_oid = event.get("trap_oid") or ""
        if trap_oid in _STANDARD_TRAP_OIDS:
            return _STANDARD_TRAP_OIDS[trap_oid][1]
        return SnmpProvider.SEVERITIES_MAP.get(
            (default_severity or "info").lower(), AlertSeverity.INFO
        )

    @staticmethod
    def _build_fingerprint(event: dict) -> str:
        """Deterministic fingerprint from (trap_oid, source_address).

        Falls back to a hash of the full event if neither is present.
        """
        trap_oid = event.get("trap_oid") or ""
        source = event.get("source_address") or ""
        if trap_oid or source:
            return hashlib.sha256(f"{trap_oid}|{source}".encode()).hexdigest()
        raw = repr(sorted(event.items()))
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _format_alert(
        event: dict,
        provider_instance: "BaseProvider" = None,
    ) -> AlertDto:
        default_severity = "info"
        if provider_instance is not None and getattr(
            provider_instance, "authentication_config", None
        ):
            default_severity = (
                provider_instance.authentication_config.default_severity or "info"
            )

        name = SnmpProvider._resolve_name(event)
        severity = SnmpProvider._resolve_severity(event, default_severity)
        description = event.get("description") or (
            f"SNMP trap {event.get('trap_oid', '')} "
            f"from {event.get('source_address', 'unknown host')}".strip()
        )
        last_received = (
            event.get("last_received")
            or datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        )

        labels = {
            "trap_oid": event.get("trap_oid", ""),
            "trap_name": event.get("trap_name", ""),
            "source_address": event.get("source_address", ""),
            "community": event.get("community", ""),
            "version": event.get("version", ""),
        }
        # Expose varbinds as labels too, prefixed so they can't clobber
        # existing keys.
        variables = event.get("variables") or {}
        if isinstance(variables, dict):
            for oid, value in variables.items():
                labels[f"var:{oid}"] = str(value)

        return AlertDto(
            id=event.get("id"),
            name=name,
            description=description,
            severity=severity,
            status=AlertStatus.FIRING,
            lastReceived=last_received,
            source=["snmp"],
            host=event.get("source_address"),
            fingerprint=event.get("fingerprint")
            or SnmpProvider._build_fingerprint(event),
            labels={k: v for k, v in labels.items() if v not in (None, "")},
            pushed=True,
        )

    @classmethod
    def simulate_alert(cls, **kwargs) -> dict:
        """Return a representative SNMP trap payload for UI testing."""
        import random

        from keep.providers.snmp_provider.alerts_mock import TRAPS

        trap_key = kwargs.get("alert_type") or random.choice(list(TRAPS.keys()))
        payload = dict(TRAPS[trap_key])
        payload.setdefault(
            "last_received", datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        )
        return payload


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")
    provider = SnmpProvider(
        context_manager=context_manager,
        provider_id="snmp-test",
        config=ProviderConfig(authentication={"default_severity": "info"}),
    )
    sample = SnmpProvider.simulate_alert()
    alert = SnmpProvider._format_alert(sample, provider_instance=provider)
    print(alert.json(indent=2))
