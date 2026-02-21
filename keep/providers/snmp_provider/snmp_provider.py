"""
SNMP Provider is a class that allows ingesting SNMP traps/events into Keep as alerts.

Supports SNMPv1, SNMPv2c, and SNMPv3 trap formats via webhook-based ingestion.
SNMP managers or trap forwarders (e.g., snmptrapd) can send trap data as JSON
to Keep's webhook endpoint.
"""

import logging

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


class SnmpProvider(BaseProvider):
    """Receive SNMP traps/events as alerts in Keep."""

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]
    FINGERPRINT_FIELDS = ["oid", "agent_address"]

    # Well-known SNMP trap OIDs and their descriptions
    WELL_KNOWN_TRAPS = {
        # SNMPv1 generic trap types
        "0": {"name": "coldStart", "severity": AlertSeverity.WARNING, "description": "Device cold start"},
        "1": {"name": "warmStart", "severity": AlertSeverity.INFO, "description": "Device warm start"},
        "2": {"name": "linkDown", "severity": AlertSeverity.CRITICAL, "description": "Network interface down"},
        "3": {"name": "linkUp", "severity": AlertSeverity.INFO, "description": "Network interface up"},
        "4": {"name": "authenticationFailure", "severity": AlertSeverity.WARNING, "description": "SNMP authentication failure"},
        "5": {"name": "egpNeighborLoss", "severity": AlertSeverity.WARNING, "description": "EGP neighbor loss"},
        "6": {"name": "enterpriseSpecific", "severity": AlertSeverity.WARNING, "description": "Enterprise-specific trap"},
        # Well-known SNMPv2c/v3 notification OIDs
        "1.3.6.1.6.3.1.1.5.1": {"name": "coldStart", "severity": AlertSeverity.WARNING, "description": "Device cold start"},
        "1.3.6.1.6.3.1.1.5.2": {"name": "warmStart", "severity": AlertSeverity.INFO, "description": "Device warm start"},
        "1.3.6.1.6.3.1.1.5.3": {"name": "linkDown", "severity": AlertSeverity.CRITICAL, "description": "Network interface down"},
        "1.3.6.1.6.3.1.1.5.4": {"name": "linkUp", "severity": AlertSeverity.INFO, "description": "Network interface up"},
        "1.3.6.1.6.3.1.1.5.5": {"name": "authenticationFailure", "severity": AlertSeverity.WARNING, "description": "SNMP authentication failure"},
    }

    # OIDs that indicate a resolved/recovery state
    RESOLUTION_OIDS = {
        "3",  # linkUp (v1 generic trap type)
        "1.3.6.1.6.3.1.1.5.4",  # linkUp (v2c/v3)
    }

    # Severity mapping for user-provided severity strings
    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "major": AlertSeverity.HIGH,
        "minor": AlertSeverity.WARNING,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "informational": AlertSeverity.INFO,
        "clear": AlertSeverity.INFO,
        "ok": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "active": AlertStatus.FIRING,
        "firing": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "clear": AlertStatus.RESOLVED,
    }

    webhook_description = "Receive SNMP traps as alerts"
    webhook_template = ""
    webhook_markdown = """
## SNMP Provider Setup

Keep receives SNMP traps via its webhook endpoint. You need to configure your
SNMP trap receiver (e.g., `snmptrapd`) to forward traps as JSON to Keep.

### Using snmptrapd (Net-SNMP)

1. Install Net-SNMP: `apt-get install snmptrapd` or `yum install net-snmp-utils`

2. Create a trap handler script (`/usr/local/bin/keep-snmp-handler.sh`):

```bash
#!/bin/bash
# Read trap data from stdin (snmptrapd format)
read -r HOSTNAME
read -r IP_ADDRESS
VARBINDS=""
while IFS= read -r line; do
    VARBINDS="$VARBINDS$line\\n"
done

# Parse and forward to Keep
curl -X POST {keep_webhook_api_url} \\
  -H "Content-Type: application/json" \\
  -H "X-API-KEY: {api_key}" \\
  -d '{
    "version": "v2c",
    "agent_address": "'$IP_ADDRESS'",
    "hostname": "'$HOSTNAME'",
    "varbinds_raw": "'$VARBINDS'"
  }'
```

3. Configure snmptrapd (`/etc/snmp/snmptrapd.conf`):
```
authCommunity log,execute public
traphandle default /usr/local/bin/keep-snmp-handler.sh
```

4. Start snmptrapd: `snmptrapd -Lf /var/log/snmptrapd.log`

### Using snmptrapd with JSON output

For a cleaner integration, use snmptrapd's `-Oj` flag for OID output and
format traps as JSON before sending to Keep.

### Direct JSON Webhook

You can also send SNMP trap data directly as JSON to the webhook endpoint:

```json
{
    "version": "v2c",
    "oid": "1.3.6.1.6.3.1.1.5.3",
    "agent_address": "192.168.1.100",
    "community": "public",
    "hostname": "switch01",
    "description": "Interface GigabitEthernet0/1 is down",
    "severity": "critical",
    "varbinds": {
        "1.3.6.1.2.1.2.2.1.1": "1",
        "1.3.6.1.2.1.2.2.1.2": "GigabitEthernet0/1",
        "1.3.6.1.2.1.2.2.1.7": "2",
        "1.3.6.1.2.1.2.2.1.8": "2"
    }
}
```

### Webhook URL

```
{keep_webhook_api_url}
```

### API Key

```
{api_key}
```
"""

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        No validation required for webhook-only SNMP provider.
        """
        pass

    def dispose(self):
        """
        No cleanup required.
        """
        pass

    @staticmethod
    def _get_trap_info(event: dict) -> dict:
        """
        Extract trap information from the event, handling v1, v2c, and v3 formats.

        Returns a dict with normalized trap fields:
            - oid: The trap OID or generic trap type
            - trap_name: Human-readable trap name
            - severity: AlertSeverity based on trap type
            - is_resolved: Whether this trap indicates resolution
        """
        # Try to get OID from various field names
        oid = (
            event.get("oid")
            or event.get("trap_oid")
            or event.get("snmpTrapOID")
            or event.get("snmpTrapOID.0")
            or event.get("1.3.6.1.6.3.1.1.4.1.0")  # snmpTrapOID.0 numeric
        )

        # For SNMPv1, check generic trap type
        generic_trap = event.get("generic_trap", event.get("genericTrap", event.get("generic-trap")))
        specific_trap = event.get("specific_trap", event.get("specificTrap", event.get("specific-trap")))
        enterprise = event.get("enterprise", event.get("enterprise_oid"))

        # If no OID but we have generic trap type (v1 format)
        if not oid and generic_trap is not None:
            oid = str(generic_trap)

        # Look up well-known trap info
        trap_info = SnmpProvider.WELL_KNOWN_TRAPS.get(str(oid), {}) if oid else {}
        trap_name = trap_info.get("name", "unknown")
        default_severity = trap_info.get("severity", AlertSeverity.WARNING)
        description = trap_info.get("description", "")

        # Check if this is a resolution event
        is_resolved = str(oid) in SnmpProvider.RESOLUTION_OIDS if oid else False

        # Check for user-provided severity override
        raw_severity = event.get("severity", "")
        user_severity = str(raw_severity).lower() if raw_severity else ""
        if user_severity in SnmpProvider.SEVERITIES_MAP:
            severity = SnmpProvider.SEVERITIES_MAP[user_severity]
        else:
            severity = default_severity

        return {
            "oid": oid,
            "trap_name": trap_name,
            "severity": severity,
            "is_resolved": is_resolved,
            "description": description,
            "generic_trap": generic_trap,
            "specific_trap": specific_trap,
            "enterprise": enterprise,
        }

    @staticmethod
    def _parse_varbinds(event: dict) -> dict:
        """
        Extract and normalize SNMP varbinds from the event.

        Varbinds can come in several formats:
        - As a dict: {"oid": "value", ...}
        - As a list of dicts: [{"oid": "...", "value": "..."}, ...]
        - As raw text (from snmptrapd pipe)
        """
        varbinds = event.get("varbinds", event.get("variables", event.get("var_binds", {})))

        if isinstance(varbinds, dict):
            return varbinds
        elif isinstance(varbinds, list):
            result = {}
            for vb in varbinds:
                if isinstance(vb, dict):
                    oid = vb.get("oid", vb.get("name", ""))
                    value = vb.get("value", vb.get("val", ""))
                    if oid:
                        result[str(oid)] = str(value)
            return result
        elif isinstance(varbinds, str):
            # Raw text — store as-is
            return {"raw": varbinds}

        return {}

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format an SNMP trap event into a Keep AlertDto.

        Handles SNMPv1, SNMPv2c, and SNMPv3 trap formats.
        """
        trap_info = SnmpProvider._get_trap_info(event)
        varbinds = SnmpProvider._parse_varbinds(event)

        # Extract common fields
        agent_address = (
            event.get("agent_address")
            or event.get("agentAddress")
            or event.get("source_ip")
            or event.get("hostname")
            or event.get("host")
            or "unknown"
        )

        hostname = (
            event.get("hostname")
            or event.get("host")
            or event.get("sysName")
            or agent_address
        )

        version = event.get("version", event.get("snmp_version", "unknown"))
        community = event.get("community", event.get("community_string", ""))

        # Build description
        description = event.get("description", event.get("message", ""))
        if not description:
            if trap_info["description"]:
                description = trap_info["description"]
            elif trap_info["trap_name"] != "unknown":
                description = f"SNMP Trap: {trap_info['trap_name']}"
            else:
                description = f"SNMP Trap from {hostname} (OID: {trap_info['oid']})"

        # Build alert name
        name = event.get("name", "")
        if not name:
            if trap_info["trap_name"] != "unknown":
                name = f"SNMP {trap_info['trap_name']}"
            else:
                name = f"SNMP Trap ({trap_info['oid'] or 'unknown'})"

        # Determine status
        raw_status = event.get("status", "")
        user_status = str(raw_status).lower() if raw_status else ""
        if user_status in SnmpProvider.STATUS_MAP:
            status = SnmpProvider.STATUS_MAP[user_status]
        elif trap_info["is_resolved"]:
            status = AlertStatus.RESOLVED
        else:
            status = AlertStatus.FIRING

        # Build the alert
        alert = AlertDto(
            id=event.get("id", event.get("trap_id", "")),
            name=name,
            description=description,
            severity=trap_info["severity"],
            status=status,
            host=hostname,
            source=["snmp"],
            agent_address=agent_address,
            snmp_version=str(version),
            community=community,
            oid=str(trap_info["oid"]) if trap_info["oid"] else "",
            trap_name=trap_info["trap_name"],
            generic_trap=str(trap_info["generic_trap"]) if trap_info["generic_trap"] is not None else None,
            specific_trap=str(trap_info["specific_trap"]) if trap_info["specific_trap"] is not None else None,
            enterprise=str(trap_info["enterprise"]) if trap_info["enterprise"] else None,
            varbinds=varbinds,
        )

        return alert


if __name__ == "__main__":
    pass
