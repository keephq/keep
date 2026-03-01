"""
SNMP Provider — receive SNMP traps/events as Keep alerts via webhook.

Users configure their SNMP trap daemon (e.g. snmptrapd) to forward
trap notifications as JSON to Keep's webhook endpoint.
No additional Python dependencies are required.
"""

import datetime
import hashlib
import logging

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)

# Standard SNMP generic trap types (RFC 1157 / RFC 3418)
WELL_KNOWN_TRAPS = {
    # SNMPv2 notification OIDs
    "1.3.6.1.6.3.1.1.5.1": {
        "name": "coldStart",
        "severity": AlertSeverity.INFO,
        "status": AlertStatus.FIRING,
    },
    "1.3.6.1.6.3.1.1.5.2": {
        "name": "warmStart",
        "severity": AlertSeverity.INFO,
        "status": AlertStatus.FIRING,
    },
    "1.3.6.1.6.3.1.1.5.3": {
        "name": "linkDown",
        "severity": AlertSeverity.CRITICAL,
        "status": AlertStatus.FIRING,
    },
    "1.3.6.1.6.3.1.1.5.4": {
        "name": "linkUp",
        "severity": AlertSeverity.INFO,
        "status": AlertStatus.RESOLVED,
    },
    "1.3.6.1.6.3.1.1.5.5": {
        "name": "authenticationFailure",
        "severity": AlertSeverity.WARNING,
        "status": AlertStatus.FIRING,
    },
    "1.3.6.1.6.3.1.1.5.6": {
        "name": "egpNeighborLoss",
        "severity": AlertSeverity.WARNING,
        "status": AlertStatus.FIRING,
    },
}

# SNMPv1 generic-trap integer → severity/status mapping
GENERIC_TRAP_MAP = {
    0: {"name": "coldStart", "severity": AlertSeverity.INFO, "status": AlertStatus.FIRING},
    1: {"name": "warmStart", "severity": AlertSeverity.INFO, "status": AlertStatus.FIRING},
    2: {"name": "linkDown", "severity": AlertSeverity.CRITICAL, "status": AlertStatus.FIRING},
    3: {"name": "linkUp", "severity": AlertSeverity.INFO, "status": AlertStatus.RESOLVED},
    4: {"name": "authenticationFailure", "severity": AlertSeverity.WARNING, "status": AlertStatus.FIRING},
    5: {"name": "egpNeighborLoss", "severity": AlertSeverity.WARNING, "status": AlertStatus.FIRING},
    6: {"name": "enterpriseSpecific", "severity": AlertSeverity.INFO, "status": AlertStatus.FIRING},
}

SEVERITY_MAP = {
    "critical": AlertSeverity.CRITICAL,
    "high": AlertSeverity.HIGH,
    "warning": AlertSeverity.WARNING,
    "info": AlertSeverity.INFO,
    "low": AlertSeverity.LOW,
}


class SnmpProvider(BaseProvider):
    """Receive SNMP traps/events as alerts in Keep."""

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send SNMP traps to Keep, configure your SNMP trap daemon to forward trap
notifications as JSON HTTP POST requests to Keep's webhook endpoint.

### Using snmptrapd (Net-SNMP)

1. Install Net-SNMP if not already present:
   ```
   # Debian/Ubuntu
   apt-get install snmptrapd
   # RHEL/CentOS
   yum install net-snmp
   ```

2. Create a trap handler script (`/usr/local/bin/keep-snmp-handler.sh`):
   ```bash
   #!/bin/bash
   # Reads snmptrapd input and forwards to Keep as JSON
   read HOST
   read IP
   VARS=""
   while read OID TYPE VALUE; do
       VARS="$VARS\\"$OID\\": \\"$VALUE\\","
   done
   VARS="${VARS%,}"

   curl -s -X POST {keep_webhook_api_url} \\
     -H "Content-Type: application/json" \\
     -H "x-api-key: {api_key}" \\
     -d "{{
       \\"host\\": \\"$HOST\\",
       \\"source_ip\\": \\"$IP\\",
       \\"variables\\": {{$VARS}}
     }}"
   ```

3. Configure snmptrapd (`/etc/snmp/snmptrapd.conf`):
   ```
   authCommunity execute public
   traphandle default /usr/local/bin/keep-snmp-handler.sh
   ```

4. Restart snmptrapd:
   ```
   systemctl restart snmptrapd
   ```

### Manual testing with curl

```bash
curl -X POST {keep_webhook_api_url} \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: {api_key}" \\
  -d '{{
    "host": "router1.example.com",
    "source_ip": "192.168.1.1",
    "trap_oid": "1.3.6.1.6.3.1.1.5.3",
    "generic_trap": 2,
    "version": "v2c",
    "message": "Interface GigabitEthernet0/1 went down",
    "variables": {{
      "1.3.6.1.2.1.2.2.1.2": "GigabitEthernet0/1",
      "1.3.6.1.2.1.2.2.1.8": "2"
    }}
  }}'
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
        """No configuration required — webhook-only provider."""
        pass

    def dispose(self):
        pass

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        trap_oid = event.get("trap_oid", "")
        generic_trap = event.get("generic_trap")
        enterprise = event.get("enterprise", "")
        source_ip = event.get("source_ip", "")
        host = event.get("host", source_ip)
        version = event.get("version", "unknown")
        variables = event.get("variables", {})

        # Resolve trap metadata from OID table or generic-trap integer
        trap_info = WELL_KNOWN_TRAPS.get(trap_oid)
        if trap_info is None and generic_trap is not None:
            try:
                trap_info = GENERIC_TRAP_MAP.get(int(generic_trap))
            except (ValueError, TypeError):
                trap_info = None

        # Determine name
        if trap_info:
            trap_name = trap_info["name"]
        elif trap_oid:
            trap_name = f"snmpTrap:{trap_oid}"
        else:
            trap_name = event.get("name", "SNMP Trap")

        # Determine severity — explicit field takes priority
        explicit_severity = event.get("severity", "").lower()
        if explicit_severity in SEVERITY_MAP:
            severity = SEVERITY_MAP[explicit_severity]
        elif trap_info:
            severity = trap_info["severity"]
        else:
            severity = AlertSeverity.INFO

        # Determine status — explicit field takes priority
        explicit_status = event.get("status", "").lower() if isinstance(event.get("status"), str) else ""
        if explicit_status == "resolved":
            status = AlertStatus.RESOLVED
        elif explicit_status == "firing":
            status = AlertStatus.FIRING
        elif trap_info:
            status = trap_info["status"]
        else:
            status = AlertStatus.FIRING

        # Build description
        message = event.get("message") or event.get("description", "")
        if not message:
            parts = [f"SNMP trap {trap_name} from {host}"]
            if enterprise:
                parts.append(f"enterprise={enterprise}")
            if variables:
                var_str = ", ".join(f"{k}={v}" for k, v in list(variables.items())[:5])
                parts.append(f"vars: {var_str}")
            message = " | ".join(parts)

        # Fingerprint for deduplication
        fingerprint_src = f"{trap_oid or generic_trap}:{source_ip}:{enterprise}"
        fingerprint = hashlib.sha256(fingerprint_src.encode()).hexdigest()

        # Timestamp
        last_received = (
            event.get("timestamp")
            or event.get("date")
            or datetime.datetime.now(datetime.timezone.utc).isoformat()
        )

        return AlertDto(
            id=event.get("id"),
            name=trap_name,
            status=status,
            severity=severity,
            lastReceived=last_received,
            host=host,
            source=["snmp"],
            message=message,
            description=message,
            pushed=True,
            fingerprint=fingerprint,
            service=event.get("service", host),
            url=event.get("url"),
            # Extra SNMP-specific fields stored via Extra.allow
            trap_oid=trap_oid,
            source_ip=source_ip,
            enterprise=enterprise,
            generic_trap=generic_trap,
            specific_trap=event.get("specific_trap"),
            snmp_version=version,
            community=event.get("community"),
            variables=variables,
        )


if __name__ == "__main__":
    pass
