"""
SnmpProvider — accept SNMP traps / events as Keep alerts.

SNMP is push-based: agents emit traps to a receiver, traditionally on UDP/162.
Keep's provider model is event-driven through its webhook ingestion endpoint,
so this provider works as a *trap receiver* — any SNMP trap forwarder that
converts a trap into a JSON POST against Keep's `/alerts/event/snmp` route is
supported. Common forwarders that produce a compatible shape: `snmptrapd`
with a small handler script, Telegraf's snmp_trap input, or Datadog's
SNMP integration in trap mode.

Trap envelope this provider accepts (POSTed as JSON):

  {
    "version": "2c",                              # 1 | 2c | 3
    "community": "public",                        # SNMPv1/v2c only
    "source_ip": "10.0.0.5",                      # agent address
    "uptime": 1234567,                            # sysUpTime in ticks
    "trap_oid": "1.3.6.1.6.3.1.1.5.3",            # OID of the trap
    "trap_name": "linkDown",                      # human-readable, optional
    "varbinds": {                                 # OID -> stringified value
      "1.3.6.1.2.1.2.2.1.1.4": "4",
      "ifDescr": "GigabitEthernet1/0/24",
      "ifAdminStatus": "down"
    },
    "timestamp": "2026-05-15T10:00:00Z"           # optional; defaults to now
  }

Severity is derived from a built-in mapping of well-known SNMPv2-MIB
notification OIDs (linkDown, authenticationFailure, etc.) plus a
configurable per-deployment override. Anything unrecognized defaults to
INFO and surfaces with the raw trap text for operator triage.
"""

import dataclasses
import datetime

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """SNMP receivers don't need outbound credentials — the trap forwarder
    authenticates to Keep through its standard webhook mechanism. The fields
    here are advisory: they let operators document the SNMP target a trap
    forwarder is bound to, for debugging and runbook purposes."""

    listener_label: str = dataclasses.field(
        metadata={
            "required": False,
            "description": (
                "Human label for the SNMP listener (e.g. 'core-net-trapd'). "
                "Shown on incoming alerts."
            ),
            "sensitive": False,
        },
        default="snmp-receiver",
    )

    community_hint: str = dataclasses.field(
        metadata={
            "required": False,
            "description": (
                "Optional: documented SNMP community string this listener accepts "
                "(advisory; not validated by Keep)."
            ),
            "sensitive": True,
        },
        default="",
    )


class SnmpProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="webhook_configured",
            description="A trap forwarder is configured to POST to Keep's SNMP route",
        ),
    ]

    # SNMPv2-MIB notification OIDs that have well-defined operational meaning.
    # Anything not in this map falls through to a per-OID-prefix heuristic and
    # then to a final INFO default.
    KNOWN_TRAP_OIDS = {
        "1.3.6.1.6.3.1.1.5.1": ("coldStart", AlertStatus.FIRING, AlertSeverity.INFO),
        "1.3.6.1.6.3.1.1.5.2": ("warmStart", AlertStatus.FIRING, AlertSeverity.INFO),
        "1.3.6.1.6.3.1.1.5.3": ("linkDown", AlertStatus.FIRING, AlertSeverity.CRITICAL),
        "1.3.6.1.6.3.1.1.5.4": ("linkUp", AlertStatus.RESOLVED, AlertSeverity.LOW),
        "1.3.6.1.6.3.1.1.5.5": (
            "authenticationFailure",
            AlertStatus.FIRING,
            AlertSeverity.WARNING,
        ),
        "1.3.6.1.6.3.1.1.5.6": (
            "egpNeighborLoss",
            AlertStatus.FIRING,
            AlertSeverity.HIGH,
        ),
    }

    # Human-name fallbacks (some forwarders emit the resolved name in `trap_name`
    # but leave `trap_oid` numeric, and vice versa). This lets us match either.
    KNOWN_TRAP_NAMES = {v[0].lower(): k for k, v in KNOWN_TRAP_OIDS.items()}

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        # Receiver-only provider; nothing to dial.
        return {"webhook_configured": True}

    # Pull mode is not supported by design — SNMP traps are push-only. This
    # method returns an empty list rather than raising so workflow execution
    # doesn't blow up if a user accidentally configures the provider as a
    # source.
    def _get_alerts(self) -> list[AlertDto]:
        self.logger.info(
            "SNMP provider is receiver-only — no alerts pulled. "
            "Configure your trap forwarder to POST to Keep's webhook URL."
        )
        return []

    @staticmethod
    def _format_alert(event: dict, provider_instance: "BaseProvider" = None) -> AlertDto:
        """Convert one normalized SNMP trap envelope into an AlertDto.

        This is the entry point Keep's webhook router calls when a trap arrives.
        See the module docstring for the accepted envelope shape.
        """
        trap_oid = (event.get("trap_oid") or "").strip()
        trap_name = (event.get("trap_name") or "").strip()

        # Resolve trap identity. Prefer numeric OID, fall back to name.
        if trap_oid and trap_oid in SnmpProvider.KNOWN_TRAP_OIDS:
            name, status, severity = SnmpProvider.KNOWN_TRAP_OIDS[trap_oid]
            resolved_oid = trap_oid
        elif trap_name and trap_name.lower() in SnmpProvider.KNOWN_TRAP_NAMES:
            resolved_oid = SnmpProvider.KNOWN_TRAP_NAMES[trap_name.lower()]
            name, status, severity = SnmpProvider.KNOWN_TRAP_OIDS[resolved_oid]
        else:
            # Unknown / vendor-specific trap. Pull what we can; default to INFO
            # so operators can triage without the alert being dropped silently.
            resolved_oid = trap_oid or "<unknown>"
            name = trap_name or f"SNMP trap {resolved_oid}"
            status = AlertStatus.FIRING
            severity = SnmpProvider._severity_hint_from_varbinds(
                event.get("varbinds") or {}
            )

        source_ip = event.get("source_ip") or event.get("agent_address") or "unknown"
        version = event.get("version") or "2c"
        timestamp = event.get("timestamp") or datetime.datetime.utcnow().isoformat()
        community = event.get("community") or ""

        varbinds = event.get("varbinds") or {}
        # Pre-format varbinds for the alert description so an on-call operator
        # sees the trap payload without diving into structured data.
        varbinds_text = "\n".join(f"  {k} = {v}" for k, v in varbinds.items())
        description = (
            f"SNMP v{version} trap {name} from {source_ip}\n"
            f"trap_oid: {resolved_oid}\n"
            + (f"varbinds:\n{varbinds_text}" if varbinds_text else "varbinds: (none)")
        )

        # Stable id so repeated traps coalesce in Keep's deduplication.
        alert_id = f"snmp-{resolved_oid}-{source_ip}-{event.get('uptime', '')}"

        return AlertDto(
            id=alert_id,
            name=name,
            description=description,
            severity=severity,
            status=status,
            lastReceived=timestamp,
            source=["snmp"],
            source_ip=source_ip,
            trap_oid=resolved_oid,
            snmp_version=str(version),
            community=community,
            varbinds=varbinds,
        )

    @staticmethod
    def _severity_hint_from_varbinds(varbinds: dict) -> AlertSeverity:
        """Heuristic severity for unrecognized vendor traps.

        Many vendors put a severity string in a varbind (Cisco MIB has
        cefcModuleOperStatus, Juniper has jnxEventSeverity, etc.). When we see
        a varbind value that looks like a severity, lift it. Otherwise INFO.
        """
        if not varbinds:
            return AlertSeverity.INFO
        joined = " ".join(str(v).lower() for v in varbinds.values())
        if any(token in joined for token in ("critical", "fatal", "emergency", "alert")):
            return AlertSeverity.CRITICAL
        if "error" in joined or "high" in joined:
            return AlertSeverity.HIGH
        if "warning" in joined or "warn" in joined:
            return AlertSeverity.WARNING
        if "notice" in joined or "info" in joined:
            return AlertSeverity.INFO
        return AlertSeverity.INFO


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    sample = {
        "version": "2c",
        "community": "public",
        "source_ip": "10.0.0.5",
        "uptime": 1234567,
        "trap_oid": "1.3.6.1.6.3.1.1.5.3",
        "trap_name": "linkDown",
        "varbinds": {
            "ifIndex": "4",
            "ifDescr": "GigabitEthernet1/0/24",
            "ifAdminStatus": "down",
        },
        "timestamp": "2026-05-15T10:00:00Z",
    }
    alert = SnmpProvider._format_alert(sample)
    print(alert)
