"""
SNMP Provider - receive SNMP trap notifications forwarded as webhooks.

Typical setup: snmptrapd or snmptt receives SNMP traps, converts them to
JSON, and POSTs them to Keep's webhook endpoint.
"""

import dataclasses
from datetime import datetime, timezone

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP provider auth config.

    No credentials required because the provider works in push/webhook mode.
    An optional community string can be used to validate incoming traps.
    """

    community: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "SNMP community string to validate incoming traps (optional)",
            "hint": "e.g. public",
            "sensitive": True,
        },
    )


# Standard SNMP generic trap types (RFC 1157 / SNMPv1)
GENERIC_TRAP_NAMES = {
    0: "coldStart",
    1: "warmStart",
    2: "linkDown",
    3: "linkUp",
    4: "authenticationFailure",
    5: "egpNeighborLoss",
    6: "enterpriseSpecific",
}

# Map generic trap types to Keep severity levels
GENERIC_TRAP_SEVERITY = {
    0: AlertSeverity.WARNING,       # coldStart
    1: AlertSeverity.INFO,          # warmStart
    2: AlertSeverity.HIGH,          # linkDown
    3: AlertSeverity.INFO,          # linkUp
    4: AlertSeverity.WARNING,       # authenticationFailure
    5: AlertSeverity.WARNING,       # egpNeighborLoss
    6: AlertSeverity.INFO,          # enterpriseSpecific (varies)
}

# Map generic trap types to status
GENERIC_TRAP_STATUS = {
    0: AlertStatus.FIRING,          # coldStart
    1: AlertStatus.RESOLVED,        # warmStart
    2: AlertStatus.FIRING,          # linkDown
    3: AlertStatus.RESOLVED,        # linkUp
    4: AlertStatus.FIRING,          # authenticationFailure
    5: AlertStatus.FIRING,          # egpNeighborLoss
    6: AlertStatus.FIRING,          # enterpriseSpecific
}

# Keyword-based severity heuristic for free-text fields
SEVERITY_KEYWORDS = {
    "critical": AlertSeverity.CRITICAL,
    "fatal": AlertSeverity.CRITICAL,
    "emergency": AlertSeverity.CRITICAL,
    "error": AlertSeverity.HIGH,
    "down": AlertSeverity.HIGH,
    "fail": AlertSeverity.HIGH,
    "failure": AlertSeverity.HIGH,
    "warning": AlertSeverity.WARNING,
    "warn": AlertSeverity.WARNING,
    "degraded": AlertSeverity.WARNING,
    "info": AlertSeverity.INFO,
    "up": AlertSeverity.INFO,
    "clear": AlertSeverity.INFO,
    "ok": AlertSeverity.INFO,
}


def _extract_severity(event: dict) -> AlertSeverity:
    """Figure out severity from whatever fields the payload provides."""
    # 1) explicit severity field
    raw = event.get("severity") or event.get("Severity") or ""
    if isinstance(raw, str):
        low = raw.strip().lower()
        for kw, sev in SEVERITY_KEYWORDS.items():
            if kw == low:
                return sev

    # 2) generic trap type
    gtrap = event.get("generic_trap") if "generic_trap" in event else event.get("genericTrap")
    if gtrap is not None:
        try:
            return GENERIC_TRAP_SEVERITY.get(int(gtrap), AlertSeverity.INFO)
        except (ValueError, TypeError):
            pass

    # 3) keyword scan in description / message
    for field in ("description", "message", "msg", "trap_description", "trapDescription"):
        text = event.get(field) or ""
        if isinstance(text, str):
            low = text.lower()
            for kw, sev in SEVERITY_KEYWORDS.items():
                if kw in low:
                    return sev

    return AlertSeverity.INFO


def _extract_status(event: dict) -> AlertStatus:
    """Derive firing/resolved from the trap payload."""
    raw = event.get("status") or event.get("Status") or ""
    if isinstance(raw, str):
        low = raw.strip().lower()
        if low in ("resolved", "ok", "clear", "up"):
            return AlertStatus.RESOLVED
        if low in ("firing", "down", "critical", "error", "fail"):
            return AlertStatus.FIRING

    gtrap = event.get("generic_trap") if "generic_trap" in event else event.get("genericTrap")
    if gtrap is not None:
        try:
            return GENERIC_TRAP_STATUS.get(int(gtrap), AlertStatus.FIRING)
        except (ValueError, TypeError):
            pass

    return AlertStatus.FIRING


def _build_trap_name(event: dict) -> str:
    """Build a human-readable alert name from trap OID or generic type."""
    # prefer explicit name / trap OID
    for field in ("name", "trap_oid", "trapOID", "oid", "snmpTrapOID"):
        val = event.get(field)
        if val:
            return str(val)

    gtrap = event.get("generic_trap") if "generic_trap" in event else event.get("genericTrap")
    if gtrap is not None:
        try:
            return GENERIC_TRAP_NAMES.get(int(gtrap), f"genericTrap({gtrap})")
        except (ValueError, TypeError):
            pass

    return "SNMP Trap"


class SnmpProvider(BaseProvider):
    """Receive SNMP traps forwarded as JSON webhooks."""

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send SNMP traps to Keep you need a trap receiver (snmptrapd, snmptt, or
similar) that converts traps to JSON and POSTs them to the Keep webhook URL.

**Using snmptrapd with a webhook script:**

1. Configure snmptrapd to invoke a script when it receives a trap.
2. The script converts the trap data to JSON and sends an HTTP POST to
   `{keep_webhook_api_url}`.
3. Include the header `X-API-KEY` with your Keep API key.
4. Example JSON payload:

```json
{
  "trap_oid": "1.3.6.1.6.3.1.1.5.3",
  "generic_trap": 2,
  "agent_address": "192.168.1.1",
  "community": "public",
  "description": "Interface eth0 is down",
  "varbinds": {
    "1.3.6.1.2.1.2.2.1.1": "2",
    "1.3.6.1.2.1.2.2.1.7": "2"
  },
  "timestamp": "2025-01-15T10:30:00Z"
}
```

**Using snmptt (SNMP Trap Translator):**

1. Configure snmptt to handle incoming traps.
2. Set the EXEC action to POST a JSON payload to `{keep_webhook_api_url}`.
3. Include the header `X-API-KEY` with value `{api_key}`.

See the [Keep docs](https://docs.keephq.dev/providers/documentation/snmp-provider) for more details.
    """

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

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        # handle batch payloads (list of traps in a single POST)
        if isinstance(event, list):
            if len(event) > 0:
                event = event[0]
            else:
                event = {}

        name = _build_trap_name(event)
        severity = _extract_severity(event)
        status = _extract_status(event)

        description = (
            event.get("description")
            or event.get("message")
            or event.get("msg")
            or event.get("trap_description")
            or event.get("trapDescription")
            or ""
        )

        agent = (
            event.get("agent_address")
            or event.get("agentAddress")
            or event.get("source_ip")
            or event.get("sourceIP")
            or event.get("host")
            or ""
        )

        trap_oid = (
            event.get("trap_oid")
            or event.get("trapOID")
            or event.get("snmpTrapOID")
            or event.get("oid")
            or ""
        )

        community = event.get("community") or event.get("Community") or ""

        # timestamp
        ts_raw = (
            event.get("timestamp")
            or event.get("Timestamp")
            or event.get("time")
            or event.get("sysUpTime")
            or ""
        )
        timestamp = None
        if ts_raw:
            if isinstance(ts_raw, (int, float)):
                try:
                    timestamp = datetime.fromtimestamp(ts_raw, tz=timezone.utc).isoformat()
                except (OSError, ValueError):
                    timestamp = str(ts_raw)
            else:
                timestamp = str(ts_raw)

        # varbinds (variable bindings carried by the trap)
        varbinds = event.get("varbinds") or event.get("varBinds") or {}

        # build a stable fingerprint from OID + agent
        alert_id = event.get("id") or f"{trap_oid}:{agent}" if trap_oid and agent else None

        generic_trap = event.get("generic_trap") or event.get("genericTrap")
        specific_trap = event.get("specific_trap") or event.get("specificTrap")
        enterprise = event.get("enterprise") or event.get("Enterprise") or ""

        alert = AlertDto(
            id=alert_id,
            name=name,
            severity=severity,
            status=status,
            description=description,
            source=["snmp"],
            agent_address=agent,
            trap_oid=trap_oid,
            community=community,
            enterprise=enterprise,
            generic_trap=generic_trap,
            specific_trap=specific_trap,
            varbinds=varbinds,
            lastReceived=timestamp,
        )

        return alert


if __name__ == "__main__":
    pass
