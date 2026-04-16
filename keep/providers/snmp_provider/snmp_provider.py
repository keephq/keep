"""
SNMP Provider – receives SNMP v1/v2c traps and converts them into Keep alerts.
"""

import dataclasses
import hashlib
from datetime import datetime, timezone

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


# SNMP generic trap type (integer 0-6) → human-readable name (RFC 1157)
GENERIC_TRAP_NAMES: dict[int, str] = {
    0: "coldStart",
    1: "warmStart",
    2: "linkDown",
    3: "linkUp",
    4: "authenticationFailure",
    5: "egpNeighborLoss",
    6: "enterpriseSpecific",
}

# SNMP generic trap type → Keep severity
GENERIC_TRAP_SEVERITY: dict[int, AlertSeverity] = {
    0: AlertSeverity.WARNING,   # coldStart  – unexpected reboot
    1: AlertSeverity.INFO,      # warmStart  – planned restart
    2: AlertSeverity.CRITICAL,  # linkDown   – network outage
    3: AlertSeverity.INFO,      # linkUp     – recovery
    4: AlertSeverity.HIGH,      # authenticationFailure – security event
    5: AlertSeverity.HIGH,      # egpNeighborLoss
    6: AlertSeverity.INFO,      # enterpriseSpecific – unknown until decoded
}


class SnmpProvider(BaseProvider):
    """Get alerts from SNMP traps into Keep."""

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="receive_traps",
            description="Receive SNMP trap messages",
            mandatory=True,
            alias="Receive SNMP Traps",
        )
    ]

    FINGERPRINT_FIELDS = ["name", "agent_address"]

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """To send SNMP traps into Keep, configure your SNMP-capable devices or a trap forwarder (e.g. snmptrapd, net-snmp) to forward traps as HTTP POST requests to Keep's webhook URL:

1. Use the following webhook URL to receive traps: {keep_webhook_api_url}
2. Add a request header with the key "x-api-key" and value {api_key}.
3. The trap payload should be JSON with fields: name, oid, agent_address, severity, description, varbinds (dict), generic_trap (int 0-6), timestamp (ISO-8601).
4. Alternatively, configure snmptrapd with a handler script that POSTs decoded traps to Keep.
"""

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        # SNMP is a push-only provider – no credentials needed to receive traps.
        pass

    def validate_scopes(self) -> dict[str, bool | str]:
        # Nothing to validate for a pure-ingest provider.
        return {"receive_traps": True}

    def _get_alerts(self) -> list[AlertDto]:
        # SNMP is push-based (traps). There is no API to poll.
        return []

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Convert a raw SNMP trap payload dict into a Keep AlertDto.

        Expected keys (all optional – sensible defaults are applied):
          name          : human-readable trap name
          oid           : trap OID string  (e.g. "1.3.6.1.6.3.1.1.5.3")
          agent_address : source IP of the sending device
          community     : SNMP community string
          severity      : Keep AlertSeverity value string
          description   : free-text description
          varbinds      : dict of OID → value variable bindings
          generic_trap  : integer 0-6 (SNMP v1 generic trap type)
          timestamp     : ISO-8601 string
        """
        oid = event.get("oid", "")
        generic_trap = event.get("generic_trap")

        # Derive a human name: prefer explicit name → generic trap name → OID tail → fallback
        name = event.get("name") or (
            GENERIC_TRAP_NAMES.get(generic_trap, f"snmp_trap_{oid.split('.')[-1]}")
            if generic_trap is not None
            else (f"snmp_trap_{oid.split('.')[-1]}" if oid else "snmp_trap")
        )

        # Severity: explicit string > generic_trap mapping > default INFO
        raw_severity = event.get("severity")
        if raw_severity:
            try:
                severity = AlertSeverity(str(raw_severity).lower())
            except ValueError:
                severity = AlertSeverity.INFO
        elif generic_trap is not None:
            severity = GENERIC_TRAP_SEVERITY.get(generic_trap, AlertSeverity.INFO)
        else:
            severity = AlertSeverity.INFO

        agent_address = event.get("agent_address", "unknown")
        description = event.get(
            "description",
            f"SNMP trap '{name}' received from {agent_address}"
            + (f" (OID: {oid})" if oid else ""),
        )

        # Timestamp
        raw_ts = event.get("timestamp")
        if raw_ts:
            try:
                last_received = datetime.fromisoformat(raw_ts).isoformat()
            except ValueError:
                last_received = datetime.now(tz=timezone.utc).isoformat()
        else:
            last_received = datetime.now(tz=timezone.utc).isoformat()

        # Labels
        labels: dict[str, str] = {
            "agent_address": agent_address,
            "community": event.get("community", "public"),
        }
        if oid:
            labels["oid"] = oid
        if generic_trap is not None:
            labels["generic_trap"] = str(generic_trap)
        for vb_oid, vb_val in event.get("varbinds", {}).items():
            labels[f"varbind_{vb_oid}"] = str(vb_val)

        # Fingerprint
        fp_raw = f"snmp-{name}-{agent_address}"
        fingerprint = hashlib.sha256(fp_raw.encode()).hexdigest()

        return AlertDto(
            id=event.get("id", fingerprint),
            name=name,
            description=description,
            severity=severity,
            status=AlertStatus.FIRING,
            source=["snmp"],
            labels=labels,
            fingerprint=fingerprint,
            lastReceived=last_received,
        )


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    config = ProviderConfig(
        description="SNMP Provider smoke-test",
        authentication={},
    )

    provider = SnmpProvider(
        context_manager=context_manager,
        provider_id="snmp_test",
        config=config,
    )
    provider.validate_config()

    print("=== scope validation ===")
    print(provider.validate_scopes())

    print("\n=== simulated alert ===")
    mock = SnmpProvider.simulate_alert()
    print("raw payload:", mock)
    alert = SnmpProvider._format_alert(mock)
    print("AlertDto   :", alert)