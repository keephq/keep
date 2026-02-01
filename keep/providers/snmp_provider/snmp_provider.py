"""
SNMP Provider for Keep.

Receives SNMP traps/events as alerts via webhook endpoint.
SNMP traps can be forwarded from snmptrapd or other SNMP trap receivers.
"""

from datetime import datetime
from typing import Optional

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class SnmpProvider(BaseProvider):
    """Receive SNMP traps/events as Keep alerts."""

    webhook_description = "Receive SNMP traps as alerts"
    webhook_template = ""
    webhook_markdown = """
To send SNMP traps to Keep, you need to configure an SNMP trap receiver (like snmptrapd) to forward traps to Keep's webhook.

## Option 1: Using snmptrapd (net-snmp)

1. Install net-snmp: `apt install snmpd snmptrapd` or `yum install net-snmp net-snmp-utils`

2. Configure `/etc/snmp/snmptrapd.conf`:
```
authCommunity log,execute,net public
traphandle default /usr/local/bin/keep-snmp-forwarder.sh
```

3. Create `/usr/local/bin/keep-snmp-forwarder.sh`:
```bash
#!/bin/bash
KEEP_WEBHOOK_URL="{keep_webhook_api_url}"
API_KEY="{api_key}"

# Read trap data from stdin
read host
read ip
vars=""
while read oid val; do
    vars="$vars\\"$oid\\": \\"$val\\","
done

# Send to Keep
curl -X POST "$KEEP_WEBHOOK_URL" \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: $API_KEY" \\
  -d "{\\"host\\": \\"$host\\", \\"source_ip\\": \\"$ip\\", \\"variables\\": {${{vars%,}}}}"
```

4. Make it executable: `chmod +x /usr/local/bin/keep-snmp-forwarder.sh`

5. Restart snmptrapd: `systemctl restart snmptrapd`

## Option 2: Direct JSON Webhook

Send SNMP trap data directly as JSON to {keep_webhook_api_url}:

```json
{
    "host": "router1.example.com",
    "source_ip": "192.168.1.1",
    "trap_oid": "1.3.6.1.6.3.1.1.5.4",
    "enterprise": "1.3.6.1.4.1.9",
    "generic_trap": 6,
    "specific_trap": 1,
    "severity": "warning",
    "message": "Interface Gi0/1 went down",
    "variables": {
        "1.3.6.1.2.1.2.2.1.1": "1",
        "1.3.6.1.2.1.2.2.1.2": "GigabitEthernet0/1",
        "1.3.6.1.2.1.2.2.1.8": "2"
    }
}
```

Headers required:
- `Content-Type: application/json`
- `x-api-key: {api_key}`
"""

    # Standard SNMP generic trap types to severity mapping
    GENERIC_TRAP_SEVERITIES = {
        0: AlertSeverity.INFO,      # coldStart
        1: AlertSeverity.INFO,      # warmStart
        2: AlertSeverity.CRITICAL,  # linkDown
        3: AlertSeverity.INFO,      # linkUp
        4: AlertSeverity.WARNING,   # authenticationFailure
        5: AlertSeverity.WARNING,   # egpNeighborLoss
        6: AlertSeverity.INFO,      # enterpriseSpecific
    }

    # String severity mapping
    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "major": AlertSeverity.HIGH,
        "minor": AlertSeverity.WARNING,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "informational": AlertSeverity.INFO,
        "clear": AlertSeverity.LOW,
        "normal": AlertSeverity.LOW,
    }

    # Well-known trap OIDs
    TRAP_OID_NAMES = {
        "1.3.6.1.6.3.1.1.5.1": "coldStart",
        "1.3.6.1.6.3.1.1.5.2": "warmStart",
        "1.3.6.1.6.3.1.1.5.3": "linkDown",
        "1.3.6.1.6.3.1.1.5.4": "linkUp",
        "1.3.6.1.6.3.1.1.5.5": "authenticationFailure",
    }

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["host", "trap_oid"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for SNMP provider.
        No specific configuration required - works via webhook.
        """
        pass

    @staticmethod
    def _get_trap_name(trap_oid: str) -> str:
        """Get human-readable trap name from OID."""
        return SnmpProvider.TRAP_OID_NAMES.get(trap_oid, trap_oid)

    @staticmethod
    def _determine_severity(event: dict) -> AlertSeverity:
        """Determine alert severity from SNMP trap data."""
        # First check for explicit severity field
        if "severity" in event:
            severity_str = str(event["severity"]).lower()
            if severity_str in SnmpProvider.SEVERITIES_MAP:
                return SnmpProvider.SEVERITIES_MAP[severity_str]

        # Check generic trap type
        if "generic_trap" in event:
            generic_trap = int(event["generic_trap"])
            if generic_trap in SnmpProvider.GENERIC_TRAP_SEVERITIES:
                return SnmpProvider.GENERIC_TRAP_SEVERITIES[generic_trap]

        # Check for known trap OIDs
        trap_oid = event.get("trap_oid", "")
        if trap_oid == "1.3.6.1.6.3.1.1.5.3":  # linkDown
            return AlertSeverity.CRITICAL
        if trap_oid == "1.3.6.1.6.3.1.1.5.4":  # linkUp
            return AlertSeverity.INFO
        if trap_oid == "1.3.6.1.6.3.1.1.5.5":  # authenticationFailure
            return AlertSeverity.WARNING

        # Default to warning
        return AlertSeverity.WARNING

    @staticmethod
    def _determine_status(event: dict) -> AlertStatus:
        """Determine alert status from SNMP trap data."""
        # Check for explicit status
        if "status" in event:
            status_str = str(event["status"]).lower()
            if status_str in ("resolved", "clear", "ok", "up", "normal"):
                return AlertStatus.RESOLVED
            if status_str in ("firing", "active", "down", "critical"):
                return AlertStatus.FIRING

        # Check trap OID for status hints
        trap_oid = event.get("trap_oid", "")
        if trap_oid in ("1.3.6.1.6.3.1.1.5.4",):  # linkUp
            return AlertStatus.RESOLVED
        if trap_oid in ("1.3.6.1.6.3.1.1.5.3",):  # linkDown
            return AlertStatus.FIRING

        # Default to firing
        return AlertStatus.FIRING

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """Convert SNMP trap event to AlertDto."""
        trap_oid = event.get("trap_oid", event.get("oid", ""))
        trap_name = SnmpProvider._get_trap_name(trap_oid)

        # Build alert name
        name = event.get("name")
        if not name:
            if trap_name != trap_oid:
                name = f"SNMP Trap: {trap_name}"
            else:
                name = f"SNMP Trap from {event.get('host', 'unknown')}"

        # Build message
        message = event.get("message")
        if not message:
            variables = event.get("variables", {})
            if variables:
                var_str = ", ".join(f"{k}={v}" for k, v in list(variables.items())[:5])
                message = f"{trap_name}: {var_str}"
            else:
                message = f"SNMP trap {trap_oid} received from {event.get('host', 'unknown')}"

        # Extract timestamp
        received_at = event.get("timestamp") or event.get("date") or event.get("time")
        if received_at and isinstance(received_at, str):
            try:
                from dateutil.parser import parse
                received_at = parse(received_at).isoformat()
            except Exception:
                received_at = datetime.utcnow().isoformat()
        elif not received_at:
            received_at = datetime.utcnow().isoformat()

        alert = AlertDto(
            id=event.get("id") or f"snmp-{trap_oid}-{event.get('host', 'unknown')}-{hash(str(event))}",
            name=name,
            message=message,
            severity=SnmpProvider._determine_severity(event),
            status=SnmpProvider._determine_status(event),
            source=["snmp"],
            host=event.get("host") or event.get("hostname") or event.get("agent_addr"),
            source_ip=event.get("source_ip") or event.get("ip"),
            trap_oid=trap_oid,
            trap_name=trap_name,
            enterprise=event.get("enterprise"),
            generic_trap=event.get("generic_trap"),
            specific_trap=event.get("specific_trap"),
            community=event.get("community"),
            snmp_version=event.get("version") or event.get("snmp_version"),
            variables=event.get("variables", {}),
            lastReceived=received_at,
            # Keep original data for debugging
            raw_event=event if event.get("include_raw", False) else None,
        )

        return alert


if __name__ == "__main__":
    # Test the provider
    test_event = {
        "host": "router1.example.com",
        "source_ip": "192.168.1.1",
        "trap_oid": "1.3.6.1.6.3.1.1.5.3",  # linkDown
        "enterprise": "1.3.6.1.4.1.9",
        "generic_trap": 2,
        "specific_trap": 0,
        "message": "Interface GigabitEthernet0/1 went down",
        "variables": {
            "1.3.6.1.2.1.2.2.1.1": "1",
            "1.3.6.1.2.1.2.2.1.2": "GigabitEthernet0/1",
            "1.3.6.1.2.1.2.2.1.8": "2",
        }
    }
    
    alert = SnmpProvider._format_alert(test_event)
    print(f"Alert: {alert.name}")
    print(f"Severity: {alert.severity}")
    print(f"Status: {alert.status}")
    print(f"Message: {alert.message}")
