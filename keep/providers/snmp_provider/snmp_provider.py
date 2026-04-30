"""
SNMP Provider is a class that allows receiving SNMP trap data as alerts in Keep.

SNMP traps can be forwarded to Keep's webhook endpoint using an SNMP trap receiver
(like snmptrapd) configured to send trap data as JSON via HTTP POST.
"""

import dataclasses
import datetime
import typing

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP Provider authentication configuration.

    Since SNMP traps are received via webhook, authentication is optional.
    When configured, the provider can also actively query SNMP agents.
    """

    community_string: typing.Optional[str] = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": "SNMP Community String",
            "sensitive": True,
            "hint": "Community string for SNMP v1/v2c (default: public)",
        },
    )


class SnmpProvider(BaseProvider):
    """Receive SNMP traps/events as alerts in Keep."""

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send SNMP traps to Keep, configure your SNMP trap receiver (e.g., snmptrapd) to forward traps as JSON to Keep's webhook endpoint.

### Using snmptrapd with a script handler

1. Install `snmptrapd` (part of Net-SNMP).
2. Create a trap handler script that forwards traps to Keep:

```bash
#!/bin/bash
# /usr/local/bin/keep-snmp-handler.sh
# Reads snmptrapd input and posts to Keep webhook

KEEP_WEBHOOK_URL="{keep_webhook_api_url}"
API_KEY="{api_key}"

read -r HOSTNAME
read -r IP_ADDRESS
VARBINDS=""
while IFS= read -r line; do
    VARBINDS="$VARBINDS$line\\n"
done

# Parse the trap data
TRAP_OID=$(echo -e "$VARBINDS" | grep "snmpTrapOID" | cut -d' ' -f2-)
ENTERPRISE=$(echo -e "$VARBINDS" | grep "snmpTrapEnterprise" | cut -d' ' -f2-)

curl -s -X POST "$KEEP_WEBHOOK_URL" \\
  -H "Content-Type: application/json" \\
  -H "X-API-KEY: $API_KEY" \\
  -d "$(cat <<EOF
{{
  "hostname": "$HOSTNAME",
  "ip_address": "$IP_ADDRESS",
  "trap_oid": "$TRAP_OID",
  "enterprise": "$ENTERPRISE",
  "varbinds_raw": "$(echo -e "$VARBINDS" | sed 's/"/\\\\"/g')",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}}
EOF
)"
```

3. Configure snmptrapd to use the handler in `/etc/snmp/snmptrapd.conf`:

```
authCommunity log,execute,net public
traphandle default /usr/local/bin/keep-snmp-handler.sh
```

### Using a Python trap receiver

You can also use a Python-based trap receiver with `pysnmp`:

```python
import json
import requests
from pysnmp.hlapi import *
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import engine, config
from pysnmp.entity.rfc3413 import ntfrcv

KEEP_WEBHOOK_URL = "{keep_webhook_api_url}"
API_KEY = "{api_key}"

def trap_callback(snmpEngine, stateReference, contextEngineId,
                  contextName, varBinds, cbCtx):
    trap_data = {{
        "varbinds": {{str(name): str(val) for name, val in varBinds}},
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }}
    # Extract common fields
    for name, val in varBinds:
        oid = str(name)
        if "snmpTrapOID" in oid:
            trap_data["trap_oid"] = str(val)
        elif "sysName" in oid:
            trap_data["hostname"] = str(val)
    requests.post(
        KEEP_WEBHOOK_URL,
        json=trap_data,
        headers={{"X-API-KEY": API_KEY, "Content-Type": "application/json"}},
    )
```

### JSON payload format

Send a JSON POST to `{keep_webhook_api_url}` with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `hostname` | string | Source host name or address |
| `ip_address` | string | Source IP address |
| `trap_oid` | string | The trap OID |
| `enterprise` | string | Enterprise OID (SNMPv1) |
| `severity` | string | One of: critical, warning, info, low |
| `status` | string | One of: firing, resolved |
| `description` | string | Human-readable trap description |
| `varbinds` | object | Key-value pairs of variable bindings |
| `varbinds_raw` | string | Raw varbind text |
| `timestamp` | string | ISO 8601 timestamp |
| `generic_trap` | int | Generic trap type (SNMPv1: 0-6) |
| `specific_trap` | int | Specific trap type (SNMPv1) |
| `version` | string | SNMP version (v1, v2c, v3) |
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    WEBHOOK_INSTALLATION_REQUIRED = True
    FINGERPRINT_FIELDS = ["trap_oid", "hostname"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="Community string is configured",
        ),
    ]

    # Map SNMP generic trap types to severity
    # 0=coldStart, 1=warmStart, 2=linkDown, 3=linkUp, 4=authFailure,
    # 5=egpNeighborLoss, 6=enterpriseSpecific
    GENERIC_TRAP_SEVERITY = {
        0: AlertSeverity.WARNING,     # coldStart
        1: AlertSeverity.INFO,        # warmStart
        2: AlertSeverity.CRITICAL,    # linkDown
        3: AlertSeverity.INFO,        # linkUp
        4: AlertSeverity.WARNING,     # authenticationFailure
        5: AlertSeverity.WARNING,     # egpNeighborLoss
        6: AlertSeverity.INFO,        # enterpriseSpecific (default)
    }

    GENERIC_TRAP_STATUS = {
        0: AlertStatus.FIRING,       # coldStart
        1: AlertStatus.RESOLVED,     # warmStart
        2: AlertStatus.FIRING,       # linkDown
        3: AlertStatus.RESOLVED,     # linkUp
        4: AlertStatus.FIRING,       # authenticationFailure
        5: AlertStatus.FIRING,       # egpNeighborLoss
        6: AlertStatus.FIRING,       # enterpriseSpecific (default)
    }

    GENERIC_TRAP_NAMES = {
        0: "coldStart",
        1: "warmStart",
        2: "linkDown",
        3: "linkUp",
        4: "authenticationFailure",
        5: "egpNeighborLoss",
        6: "enterpriseSpecific",
    }

    SEVERITY_STR_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
    }

    STATUS_STR_MAP = {
        "firing": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
    }

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
        return {"authenticated": True}

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format an SNMP trap event into a Keep AlertDto.

        Supports multiple input formats:
        - Raw snmptrapd output forwarded as JSON
        - pysnmp callback data
        - Custom JSON with standard fields
        """
        # Handle list of events
        if isinstance(event, list):
            return [
                SnmpProvider._format_alert(e, provider_instance)
                for e in event
            ]

        hostname = (
            event.get("hostname")
            or event.get("agent_address")
            or event.get("ip_address")
            or "unknown"
        )

        trap_oid = (
            event.get("trap_oid")
            or event.get("snmpTrapOID")
            or event.get("oid")
            or ""
        )

        enterprise = event.get("enterprise") or event.get("snmpTrapEnterprise") or ""

        description = event.get("description") or event.get("message") or ""
        if not description:
            varbinds_raw = event.get("varbinds_raw", "")
            if varbinds_raw:
                description = f"SNMP Trap from {hostname}: {varbinds_raw[:500]}"
            else:
                description = f"SNMP Trap from {hostname}"
            if trap_oid:
                description += f" (OID: {trap_oid})"

        # Determine severity
        severity = AlertSeverity.INFO
        if event.get("severity"):
            severity = SnmpProvider.SEVERITY_STR_MAP.get(
                str(event["severity"]).lower(), AlertSeverity.INFO
            )
        elif event.get("generic_trap") is not None:
            try:
                generic_trap = int(event["generic_trap"])
                severity = SnmpProvider.GENERIC_TRAP_SEVERITY.get(
                    generic_trap, AlertSeverity.INFO
                )
            except (ValueError, TypeError):
                pass

        # Determine status
        status = AlertStatus.FIRING
        if event.get("status"):
            status = SnmpProvider.STATUS_STR_MAP.get(
                str(event["status"]).lower(), AlertStatus.FIRING
            )
        elif event.get("generic_trap") is not None:
            try:
                generic_trap = int(event["generic_trap"])
                status = SnmpProvider.GENERIC_TRAP_STATUS.get(
                    generic_trap, AlertStatus.FIRING
                )
            except (ValueError, TypeError):
                pass

        # Build trap name
        name = event.get("name") or ""
        if not name:
            generic_trap = event.get("generic_trap")
            if generic_trap is not None:
                try:
                    name = SnmpProvider.GENERIC_TRAP_NAMES.get(
                        int(generic_trap), f"trap-{generic_trap}"
                    )
                except (ValueError, TypeError):
                    name = "snmp-trap"
            elif trap_oid:
                name = f"snmp-trap-{trap_oid}"
            else:
                name = "snmp-trap"

        # Parse timestamp
        timestamp = event.get("timestamp") or event.get("time")
        if timestamp:
            last_received = str(timestamp)
        else:
            last_received = datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()

        # Extract varbinds
        varbinds = event.get("varbinds") or {}

        # Build the alert ID
        alert_id = event.get("id")
        if not alert_id:
            alert_id = f"snmp-{hostname}-{trap_oid}-{name}"

        alert = AlertDto(
            id=alert_id,
            name=name,
            status=status,
            severity=severity,
            description=description,
            lastReceived=last_received,
            source=["snmp"],
            hostname=hostname,
            ip_address=event.get("ip_address") or event.get("agent_address"),
            trap_oid=trap_oid,
            enterprise=enterprise,
            generic_trap=event.get("generic_trap"),
            specific_trap=event.get("specific_trap"),
            snmp_version=event.get("version") or event.get("snmp_version"),
            community=event.get("community"),
            varbinds=varbinds,
            varbinds_raw=event.get("varbinds_raw"),
        )

        return alert


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    config = ProviderConfig(
        description="SNMP Provider",
        authentication={
            "community_string": "public",
        },
    )

    provider = SnmpProvider(
        context_manager,
        provider_id="snmp",
        config=config,
    )

    # Test formatting a sample trap
    sample_trap = {
        "hostname": "switch01.example.com",
        "ip_address": "192.168.1.1",
        "trap_oid": "1.3.6.1.6.3.1.1.5.3",
        "generic_trap": 2,
        "specific_trap": 0,
        "enterprise": "1.3.6.1.4.1.9.1",
        "version": "v2c",
        "community": "public",
        "description": "Interface GigabitEthernet0/1 is down",
        "varbinds": {
            "1.3.6.1.2.1.1.3.0": "12345",
            "1.3.6.1.2.1.2.2.1.1": "1",
            "1.3.6.1.2.1.2.2.1.7": "2",
        },
        "timestamp": "2026-04-24T10:00:00Z",
    }

    alert = SnmpProvider._format_alert(sample_trap)
    print(f"Alert: {alert}")
