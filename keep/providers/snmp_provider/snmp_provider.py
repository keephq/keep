"""
SNMP provider — receives trap data pushed as JSON by an SNMP manager
(e.g. snmptrapd with a custom handler, Net-SNMP, or any trap forwarder).
No external SNMP library required.
"""

import logging
from datetime import datetime, timezone

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


class SnmpProvider(BaseProvider):
    """Ingest SNMP trap data into Keep via webhook."""

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To forward SNMP traps to Keep:

1. Configure your SNMP trap receiver (e.g. snmptrapd, Net-SNMP, Zabbix, or a custom handler)
   to POST trap data as JSON to the Keep webhook endpoint.
2. Use the webhook URL: `{keep_webhook_api_url}`
3. Add the request header `x-api-key: {api_key}`.
4. The JSON body must include at minimum `trap_type` (or `trapType`) and either
   `trap_name` (or `trapName`) or `enterprise` to identify the trap.

Example payload:
```json
{
  "agent_addr": "192.168.1.10",
  "trap_type": 2,
  "trap_name": "linkDown",
  "enterprise": "1.3.6.1.2.1.11",
  "uptime": "12345",
  "timestamp": "2024-01-01T00:00:00Z",
  "community": "public",
  "varbinds": [
    {"oid": "1.3.6.1.2.1.2.2.1.1.1", "type": "integer", "value": "1"},
    {"oid": "ifDescr", "type": "octet-string", "value": "eth0"}
  ]
}
```

Both camelCase (`agentAddr`, `trapType`, `trapName`) and snake_case variants are accepted.
"""

    # Generic trap type numbers as defined in RFC 1157
    GENERIC_TRAP_NAMES = {
        0: "coldStart",
        1: "warmStart",
        2: "linkDown",
        3: "linkUp",
        4: "authenticationFailure",
        5: "egpNeighborLoss",
        6: "enterpriseSpecific",
    }

    # Severity by generic trap type
    TRAP_SEVERITY_MAP = {
        "coldStart": AlertSeverity.WARNING,
        "warmStart": AlertSeverity.INFO,
        "linkDown": AlertSeverity.CRITICAL,
        "linkUp": AlertSeverity.INFO,
        "authenticationFailure": AlertSeverity.HIGH,
        "egpNeighborLoss": AlertSeverity.WARNING,
        "enterpriseSpecific": AlertSeverity.INFO,
    }

    # linkUp is a recovery event; everything else fires
    TRAP_STATUS_MAP = {
        "coldStart": AlertStatus.FIRING,
        "warmStart": AlertStatus.FIRING,
        "linkDown": AlertStatus.FIRING,
        "linkUp": AlertStatus.RESOLVED,
        "authenticationFailure": AlertStatus.FIRING,
        "egpNeighborLoss": AlertStatus.FIRING,
        "enterpriseSpecific": AlertStatus.FIRING,
    }

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["id"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        pass

    @staticmethod
    def _get(event: dict, *keys: str):
        """Return the first matching value from event, trying each key in order."""
        for key in keys:
            val = event.get(key)
            if val is not None:
                return val
        return None

    @staticmethod
    def _resolve_trap_name(event: dict) -> str:
        trap_name = SnmpProvider._get(event, "trap_name", "trapName")
        if trap_name:
            return str(trap_name)

        trap_type = SnmpProvider._get(event, "trap_type", "trapType")
        if trap_type is not None:
            try:
                return SnmpProvider.GENERIC_TRAP_NAMES.get(int(trap_type), "enterpriseSpecific")
            except (ValueError, TypeError):
                pass

        return "enterpriseSpecific"

    @staticmethod
    def _format_varbinds(varbinds) -> str | None:
        if not varbinds or not isinstance(varbinds, list):
            return None
        parts = []
        for vb in varbinds:
            if isinstance(vb, dict):
                oid = vb.get("oid", "")
                value = vb.get("value", "")
                vb_type = vb.get("type", "")
                parts.append(f"{oid} ({vb_type}): {value}" if vb_type else f"{oid}: {value}")
            else:
                parts.append(str(vb))
        return "\n".join(parts) if parts else None

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        get = SnmpProvider._get

        trap_name = SnmpProvider._resolve_trap_name(event)
        severity = SnmpProvider.TRAP_SEVERITY_MAP.get(trap_name, AlertSeverity.INFO)
        status = SnmpProvider.TRAP_STATUS_MAP.get(trap_name, AlertStatus.FIRING)

        agent_addr = get(event, "agent_addr", "agentAddr", "source_address", "sourceAddress")
        enterprise = get(event, "enterprise", "enterprise_oid", "enterpriseOid")
        community = get(event, "community")
        uptime = get(event, "uptime", "sys_uptime", "sysUptime")
        varbinds = get(event, "varbinds", "variable_bindings", "variableBindings")

        alert_id = get(event, "id", "trap_id", "trapId")

        timestamp = get(event, "timestamp", "time", "datetime")
        if not timestamp:
            timestamp = datetime.now(timezone.utc).isoformat()

        name = f"SNMP Trap: {trap_name}"
        if agent_addr:
            name = f"SNMP Trap: {trap_name} from {agent_addr}"

        description_parts = []
        if enterprise:
            description_parts.append(f"Enterprise OID: {enterprise}")
        if community:
            description_parts.append(f"Community: {community}")
        if uptime:
            description_parts.append(f"Agent uptime: {uptime}")
        varbind_str = SnmpProvider._format_varbinds(varbinds)
        if varbind_str:
            description_parts.append(f"Varbinds:\n{varbind_str}")

        alert = AlertDto(
            id=str(alert_id) if alert_id is not None else None,
            name=name,
            description="\n".join(description_parts) if description_parts else None,
            severity=severity,
            status=status,
            source=["snmp"],
            lastReceived=timestamp,
            trap_name=trap_name,
            trap_type=get(event, "trap_type", "trapType"),
            agent_addr=agent_addr,
            enterprise=enterprise,
            community=community,
            uptime=uptime,
            varbinds=varbinds,
        )

        return alert


if __name__ == "__main__":
    pass
