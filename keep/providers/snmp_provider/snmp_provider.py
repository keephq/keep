"""
SnmpProvider receives SNMP trap events forwarded as JSON and converts them into Keep alerts.

Typical setup: snmptrapd (net-snmp) with a handler script that POSTs trap data to Keep's
webhook endpoint. See webhook_markdown for setup instructions.
"""

import datetime
import logging

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)

# SNMPv2-MIB trap OID prefix
_TRAP_OID_PREFIX = "1.3.6.1.6.3.1.1.5."

# Standard SNMP generic trap type names (RFC 1157 + SNMPv2c OID suffixes)
_GENERIC_TRAP_NAMES: dict[str, str] = {
    "0": "coldStart",
    "1": "warmStart",
    "2": "linkDown",
    "3": "linkUp",
    "4": "authenticationFailure",
    "5": "egpNeighborLoss",
    # SNMPv2c / SNMPv3 OID-based names
    _TRAP_OID_PREFIX + "1": "coldStart",
    _TRAP_OID_PREFIX + "2": "warmStart",
    _TRAP_OID_PREFIX + "3": "linkDown",
    _TRAP_OID_PREFIX + "4": "linkUp",
    _TRAP_OID_PREFIX + "5": "authenticationFailure",
    _TRAP_OID_PREFIX + "6": "egpNeighborLoss",
}

# MIB symbolic name fragments → Keep severity
_SEVERITY_MAP: dict[str, AlertSeverity] = {
    "cold": AlertSeverity.CRITICAL,
    "down": AlertSeverity.CRITICAL,
    "failure": AlertSeverity.HIGH,
    "error": AlertSeverity.HIGH,
    "warn": AlertSeverity.WARNING,
    "degraded": AlertSeverity.WARNING,
    "up": AlertSeverity.INFO,
    "warm": AlertSeverity.INFO,
    "start": AlertSeverity.INFO,
    "neighbor": AlertSeverity.WARNING,
}

# Standard SNMP generic trap type → Keep status
_STATUS_MAP: dict[str, AlertStatus] = {
    "coldStart": AlertStatus.FIRING,
    "warmStart": AlertStatus.FIRING,
    "linkDown": AlertStatus.FIRING,
    "linkUp": AlertStatus.RESOLVED,
    "authenticationFailure": AlertStatus.FIRING,
    "egpNeighborLoss": AlertStatus.FIRING,
}


def _resolve_trap_name(trap_oid: str | None, generic_trap: str | None) -> str:
    """Return a human-readable trap name, preferring OID lookup then generic type."""
    if trap_oid:
        # Direct OID match
        if trap_oid in _GENERIC_TRAP_NAMES:
            return _GENERIC_TRAP_NAMES[trap_oid]
        # Symbolic name forwarded by MIB-aware tools (e.g. "IF-MIB::linkDown")
        if "::" in trap_oid:
            return trap_oid.split("::")[-1]
        return trap_oid
    if generic_trap is not None:
        return _GENERIC_TRAP_NAMES.get(str(generic_trap), f"trap-{generic_trap}")
    return "unknownTrap"


def _severity_from_name(trap_name: str) -> AlertSeverity:
    lower = trap_name.lower()
    for keyword, severity in _SEVERITY_MAP.items():
        if keyword in lower:
            return severity
    return AlertSeverity.INFO


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    No credentials are required for the SNMP webhook provider.
    Keep validates the source using its own API key on the webhook URL.
    """

    pass


class SnmpProvider(BaseProvider):
    """Ingest SNMP trap events into Keep as alerts via a JSON webhook."""

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["source_host", "trap_oid"]

    webhook_description = "Receive SNMP trap events forwarded by snmptrapd"
    webhook_markdown = """
## SNMP Provider Setup

Keep receives SNMP traps through a lightweight handler script that converts
Net-SNMP's output into JSON and POSTs it to Keep's webhook endpoint.

### 1. Install the handler script

Save the script below as `/etc/snmp/keep_handler.py` on your trap-receiver host:

```python
#!/usr/bin/env python3
import sys, json, os, datetime, requests

KEEP_URL = os.environ.get("KEEP_WEBHOOK_URL", "{keep_webhook_api_url}")
KEEP_KEY  = os.environ.get("KEEP_API_KEY",     "{api_key}")

lines = sys.stdin.read().splitlines()
host = lines[0] if lines else "unknown"
trap_oid = None
varbinds = []
for line in lines[1:]:
    parts = line.split(None, 1)
    if len(parts) == 2:
        oid, val = parts
        if "snmpTrapOID" in oid or "enterprises" in oid:
            trap_oid = val.strip()
        else:
            varbinds.append({{"oid": oid, "value": val.strip()}})

payload = {{
    "host": host,
    "trap_oid": trap_oid,
    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    "varbinds": varbinds,
}}
requests.post(KEEP_URL, json=payload, headers={{"x-api-key": KEEP_KEY}}, timeout=5)
```

Make it executable: `chmod +x /etc/snmp/keep_handler.py`

### 2. Configure snmptrapd

Add to `/etc/snmp/snmptrapd.conf`:

```
authCommunity log,execute,net public
traphandle default /etc/snmp/keep_handler.py
```

### 3. Restart snmptrapd

```bash
systemctl restart snmptrapd
```

### Expected JSON payload

```json
{{
  "host": "192.168.1.100",
  "trap_oid": "1.3.6.1.6.3.1.1.5.3",
  "timestamp": "2024-01-15T10:30:00Z",
  "community": "public",
  "generic_trap": "2",
  "enterprise_oid": "1.3.6.1.4.1.9.1.1",
  "uptime": "12345",
  "varbinds": [
    {{"oid": "1.3.6.1.2.1.2.2.1.1.1", "value": "1", "type": "INTEGER"}},
    {{"oid": "1.3.6.1.2.1.2.2.1.7.1", "value": "down(2)", "type": "INTEGER"}}
  ]
}}
```
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
        self.authentication_config = SnmpProviderAuthConfig()

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Convert an SNMP trap JSON payload into a Keep AlertDto.

        Supports payloads produced by Net-SNMP handlers, SNMP proxy tools,
        or any source that follows the documented JSON schema.
        """
        source_host = (
            event.get("host")
            or event.get("source_host")
            or event.get("agent_addr")
            or "unknown"
        )

        trap_oid = (
            event.get("trap_oid")
            or event.get("enterprise_oid")
            or event.get("oid")
        )
        generic_trap = event.get("generic_trap")

        trap_name = _resolve_trap_name(trap_oid, generic_trap)
        severity = _severity_from_name(trap_name)
        status = _STATUS_MAP.get(trap_name, AlertStatus.FIRING)

        # Build a concise description from varbinds
        varbinds = event.get("varbinds") or event.get("variable_bindings") or []
        if isinstance(varbinds, dict):
            varbinds = [{"oid": k, "value": v} for k, v in varbinds.items()]

        varbind_lines = [
            f"{vb.get('oid', '?')}: {vb.get('value', '')}"
            for vb in varbinds
            if isinstance(vb, dict)
        ]
        description = (
            "; ".join(varbind_lines)
            if varbind_lines
            else f"SNMP trap {trap_name} from {source_host}"
        )

        # Timestamp
        ts_raw = event.get("timestamp") or event.get("time_stamp")
        try:
            last_received = (
                datetime.datetime.fromisoformat(ts_raw.rstrip("Z")).isoformat()
                if ts_raw
                else datetime.datetime.now(datetime.timezone.utc).isoformat()
            )
        except (ValueError, AttributeError):
            last_received = datetime.datetime.now(datetime.timezone.utc).isoformat()

        return AlertDto(
            id=f"{source_host}-{trap_oid or generic_trap or 'unknown'}",
            name=f"SNMP Trap: {trap_name}",
            description=description,
            severity=severity,
            status=status,
            source=["snmp"],
            source_host=source_host,
            trap_oid=trap_oid,
            trap_name=trap_name,
            community=event.get("community"),
            uptime=event.get("uptime"),
            enterprise_oid=event.get("enterprise_oid"),
            version=event.get("version"),
            varbinds=varbinds,
            lastReceived=last_received,
        )


if __name__ == "__main__":
    pass
