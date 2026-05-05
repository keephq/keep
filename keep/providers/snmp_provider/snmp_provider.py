"""
SNMP Provider – receive SNMP trap events as Keep alerts via webhook.

This provider acts as a webhook receiver for SNMP trap notifications.
External SNMP trap receivers (snmptrapd, SNMPTT, Zabbix, Nagios, etc.)
forward trap data to Keep's webhook URL as JSON.

Supported payload schemas
─────────────────────────
1. Structured JSON (preferred by Keep's SNMP handler script):
     {"source_ip": "192.168.1.10", "community": "public",
      "trap_oid": "1.3.6.1.6.3.1.1.5.3", "uptime": "12345",
      "varbinds": {"ifIndex": "2", "ifOperStatus": "2"}}

2. Flat JSON (simple forwarders):
     {"oid": "1.3.6.1.6.3.1.1.5.3", "message": "linkDown on eth0",
      "source": "router1.example.com", "severity": "high"}

3. snmptrapd extended-log JSON (via traphandle script):
     {"src": "192.168.1.10", "enterprise": "1.3.6.1.6.3.1.1.5.3",
      "trap": "2", "description": "Interface eth0 changed state to down"}
"""

import dataclasses
import datetime
import uuid
from typing import Optional

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

# ---------------------------------------------------------------------------
# SNMPv2-MIB / SNMPv2-TRAP-MIB well-known trap OID → human-readable name
# ---------------------------------------------------------------------------
WELL_KNOWN_TRAPS: dict[str, str] = {
    "1.3.6.1.6.3.1.1.5.1": "coldStart",
    "1.3.6.1.6.3.1.1.5.2": "warmStart",
    "1.3.6.1.6.3.1.1.5.3": "linkDown",
    "1.3.6.1.6.3.1.1.5.4": "linkUp",
    "1.3.6.1.6.3.1.1.5.5": "authenticationFailure",
    "1.3.6.1.6.3.1.1.5.6": "egpNeighborLoss",
}

# SNMPv1 generic trap type number → name (RFC 1157)
SNMPv1_GENERIC_TRAPS: dict[int, str] = {
    0: "coldStart",
    1: "warmStart",
    2: "linkDown",
    3: "linkUp",
    4: "authenticationFailure",
    5: "egpNeighborLoss",
    6: "enterpriseSpecific",
}

# Trap name → Keep severity
TRAP_SEVERITY_MAP: dict[str, AlertSeverity] = {
    "coldStart": AlertSeverity.CRITICAL,
    "warmStart": AlertSeverity.WARNING,
    "linkDown": AlertSeverity.HIGH,
    "linkUp": AlertSeverity.INFO,
    "authenticationFailure": AlertSeverity.WARNING,
    "egpNeighborLoss": AlertSeverity.HIGH,
    "enterpriseSpecific": AlertSeverity.WARNING,
}

# Traps that indicate recovery / resolved state
RESOLVED_TRAP_NAMES = {"linkUp", "warmStart"}

# Keyword → severity for free-text scanning
_KEYWORD_SEVERITY = [
    ({"critical", "down", "fail", "error", "unreachable"}, AlertSeverity.CRITICAL),
    ({"warning", "warn", "degraded", "degrade"}, AlertSeverity.WARNING),
    ({"up", "ok", "resolved", "recover"}, AlertSeverity.INFO),
]

_EXPLICIT_SEVERITY_MAP: dict[str, AlertSeverity] = {
    "critical": AlertSeverity.CRITICAL,
    "error": AlertSeverity.HIGH,
    "high": AlertSeverity.HIGH,
    "warning": AlertSeverity.WARNING,
    "warn": AlertSeverity.WARNING,
    "info": AlertSeverity.INFO,
    "informational": AlertSeverity.INFO,
    "low": AlertSeverity.LOW,
    "ok": AlertSeverity.INFO,
    "clear": AlertSeverity.INFO,
}


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    Configuration for the SNMP webhook provider.

    The SNMP provider is webhook-only — it receives traps forwarded by an
    external trap receiver and requires no outbound credentials.
    """

    community_filter: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": (
                "Only accept traps with this SNMP community string. "
                "Leave empty to accept traps from any community."
            ),
            "hint": "public",
            "sensitive": True,
        },
    )


class SnmpProvider(BaseProvider):
    """
    Keep provider for SNMP trap events.

    Receives SNMP traps forwarded as HTTP JSON from an external trap receiver
    (snmptrapd, SNMPTT, Zabbix, Nagios, OcNOS, etc.) and converts them to
    Keep alerts with automatic severity and status resolution.
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["source_ip", "trap_oid"]

    webhook_description = (
        "Forward SNMP traps to Keep from any trap receiver that can issue "
        "HTTP POST requests (snmptrapd, SNMPTT, Zabbix, etc.)."
    )
    webhook_markdown = """
1. Keep provides a webhook URL that accepts SNMP trap notifications as JSON.
2. Use `{keep_webhook_api_url}` as the destination for your forwarder.

### snmptrapd (recommended)

Install `net-snmp` and add a traphandle script:

```
# /etc/snmp/snmptrapd.conf
authCommunity log,execute,net public
traphandle default /usr/local/bin/keep-snmp-forward
```

Create `/usr/local/bin/keep-snmp-forward`:

```bash
#!/bin/bash
# snmptrapd passes trap info via stdin and $1=hostname $2=ip
read src; read vars
curl -s -X POST {keep_webhook_api_url} \\
  -H "Content-Type: application/json" \\
  -d "{
    \\"source_ip\\": \\"$2\\",
    \\"community\\": \\"public\\",
    \\"trap_oid\\": \\"$(echo $vars | grep -o '1\\.3\\.6.*' | head -1)\\",
    \\"description\\": \\"$vars\\"
  }"
```

### Direct JSON payload

Any system can POST a JSON body to the webhook URL:

```json
{
  "source_ip": "192.168.1.10",
  "community": "public",
  "trap_oid": "1.3.6.1.6.3.1.1.5.3",
  "trap_name": "linkDown",
  "uptime": "567890",
  "varbinds": {
    "ifIndex": "2",
    "ifAdminStatus": "1",
    "ifOperStatus": "2"
  }
}
```
"""

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ) -> None:
        super().__init__(context_manager, provider_id, config)

    def validate_config(self) -> None:
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_trap_name(event: dict) -> str:
        """Return the human-readable trap name from the raw event dict."""
        if event.get("trap_name"):
            return str(event["trap_name"])

        oid = (
            event.get("trap_oid")
            or event.get("oid")
            or event.get("enterprise")
            or ""
        )
        if oid in WELL_KNOWN_TRAPS:
            return WELL_KNOWN_TRAPS[oid]

        # SNMPv1 generic trap type number
        generic = event.get("generic_trap") or event.get("trap")
        if generic is not None:
            try:
                return SNMPv1_GENERIC_TRAPS.get(int(generic), "enterpriseSpecific")
            except (ValueError, TypeError):
                pass

        return oid if oid else "snmpTrap"

    @staticmethod
    def _resolve_severity(trap_name: str, event: dict) -> AlertSeverity:
        """
        Resolve alert severity.

        Priority: explicit severity field → trap-name map → keyword heuristic.
        """
        explicit = (event.get("severity") or event.get("priority") or "").lower()
        if explicit in _EXPLICIT_SEVERITY_MAP:
            return _EXPLICIT_SEVERITY_MAP[explicit]

        if trap_name in TRAP_SEVERITY_MAP:
            return TRAP_SEVERITY_MAP[trap_name]

        # Keyword scan across all string values in the payload
        haystack = " ".join(
            str(v) for v in event.values() if isinstance(v, (str, int, float))
        ).lower()
        for keywords, sev in _KEYWORD_SEVERITY:
            if any(kw in haystack for kw in keywords):
                return sev

        return AlertSeverity.INFO

    @staticmethod
    def _resolve_status(trap_name: str, event: dict) -> AlertStatus:
        """Resolve alert status from trap name and explicit status field."""
        explicit = (event.get("status") or "").lower()
        if explicit in ("ok", "resolved", "up", "clear"):
            return AlertStatus.RESOLVED
        if explicit in ("firing", "down", "active", "open"):
            return AlertStatus.FIRING

        if trap_name in RESOLVED_TRAP_NAMES:
            return AlertStatus.RESOLVED

        return AlertStatus.FIRING

    @staticmethod
    def _format_alert(
        event: dict,
        provider_instance: "SnmpProvider" = None,
    ) -> AlertDto | list[AlertDto]:
        """
        Convert an incoming SNMP trap webhook payload into a Keep AlertDto.

        Handles structured JSON, flat JSON, and snmptrapd-style payloads.
        """
        # Normalise source IP across common field names
        source_ip = (
            event.get("source_ip")
            or event.get("src")
            or event.get("agent")
            or event.get("host")
            or event.get("source")
            or "unknown"
        )

        # Normalise OID across common field names
        trap_oid = (
            event.get("trap_oid")
            or event.get("oid")
            or event.get("enterprise")
            or ""
        )

        trap_name = SnmpProvider._resolve_trap_name(event)
        severity = SnmpProvider._resolve_severity(trap_name, event)
        status = SnmpProvider._resolve_status(trap_name, event)

        description = (
            event.get("description")
            or event.get("message")
            or event.get("output")
            or trap_name
        )

        # Preserve varbinds as additional context
        varbinds = event.get("varbinds") or {}
        if not isinstance(varbinds, dict):
            varbinds = {"raw": str(varbinds)}

        return AlertDto(
            id=event.get("id") or str(uuid.uuid4()),
            name=trap_name,
            description=str(description),
            severity=severity,
            status=status,
            source=["snmp"],
            source_ip=source_ip,
            trap_oid=trap_oid,
            community=event.get("community") or event.get("community_string") or "",
            uptime=event.get("uptime") or event.get("sysUpTime") or "",
            varbinds=varbinds,
            lastReceived=(
                event.get("timestamp")
                or datetime.datetime.now(datetime.timezone.utc).isoformat()
            ),
        )


if __name__ == "__main__":
    pass
