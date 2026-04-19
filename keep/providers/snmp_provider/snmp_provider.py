"""
SNMP Provider — ingest SNMP trap / notification events into Keep via HTTP webhook.

SNMP traps are classically UDP/BER; Keep's ingestion path is HTTP. The supported
workflow is to forward traps to Keep as JSON (snmptrapd + shell, SNMPTT,
Telegraf `inputs.snmp_trap`, etc.) against POST /event/snmp with a webhook API key.
"""

from __future__ import annotations

import datetime
import json
import logging
import uuid
from typing import Any

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)

# Standard SNMPv2-MIB / SNMPv2-TC notification OIDs (suffix after 1.3.6.1.6.3.1.1.5.)
_STD_TRAP_SUFFIX_SEVERITY: dict[str, AlertSeverity] = {
    "1": AlertSeverity.INFO,  # coldStart
    "2": AlertSeverity.INFO,  # warmStart
    "3": AlertSeverity.HIGH,  # linkDown
    "4": AlertSeverity.INFO,  # linkUp
    "5": AlertSeverity.WARNING,  # authenticationFailure
    "6": AlertSeverity.WARNING,  # egpNeighborLoss
}


class SnmpProvider(BaseProvider):
    """Receive SNMP trap / inform payloads (as JSON) into Keep."""

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    WEBHOOK_INSTALLATION_REQUIRED = True
    FINGERPRINT_FIELDS = ["name", "host", "labels.trap_oid"]

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
### SNMP traps → Keep (HTTP)

Keep accepts **JSON** describing one or more traps on `POST {keep_webhook_api_url}` with header `X-API-KEY` / `Authorization: Bearer ...` (same as other webhook providers).

Use any forwarder that can `curl` JSON, for example **`snmptrapd`** with a `traphandle` script, **SNMPTT**, or **Telegraf** `inputs.snmp_trap` + `outputs.http`.

#### Single trap (minimal)

```json
{
  "trap_oid": "1.3.6.1.6.3.1.1.5.3",
  "agent_address": "192.0.2.10",
  "name": "linkDown on eth0",
  "message": "Interface eth0 down",
  "hostname": "router-01"
}
```

#### Batch

```json
{
  "snmp_traps": [
    { "trap_oid": "1.3.6.1.6.3.1.1.5.1", "agent_address": "192.0.2.1", "hostname": "sw1" }
  ]
}
```

Optional fields: `varbinds` (list of `{oid,type,value}`), `community`, `uptime`, `severity`, `status`, `lastReceived`.

`trap_oid` may also be sent as `trapOid` / `snmpTrapOID` (forwarder-specific).
"""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        pass

    def dispose(self):
        pass

    @staticmethod
    def parse_event_raw_body(raw_body: bytes | dict) -> dict:
        if isinstance(raw_body, dict):
            return raw_body
        if isinstance(raw_body, (bytes, bytearray)):
            text = raw_body.decode("utf-8", errors="replace").strip()
            if not text:
                return {}
            try:
                parsed: Any = json.loads(text)
            except json.JSONDecodeError:
                logger.exception("SNMP provider: body is not valid JSON")
                raise
            if isinstance(parsed, list):
                return {"snmp_traps": parsed}
            if isinstance(parsed, dict):
                return parsed
            raise ValueError("SNMP webhook JSON must be an object or array")
        raise TypeError(f"Unsupported SNMP event body type: {type(raw_body)}")

    @staticmethod
    def _normalize_trap_dict(raw: dict[str, Any]) -> dict[str, Any]:
        out = dict(raw)
        oid = (
            out.get("trap_oid")
            or out.get("trapOid")
            or out.get("snmpTrapOID")
        )
        if oid:
            out["trap_oid"] = oid
        agent = (
            out.get("agent_address")
            or out.get("agentAddress")
            or out.get("source_ip")
            or out.get("agent-addr")
        )
        if agent:
            out["agent_address"] = agent
        host = out.get("hostname") or out.get("sysName") or out.get("host")
        if host:
            out["hostname"] = host
        return out

    @staticmethod
    def _severity_for_oid(trap_oid: str | None) -> AlertSeverity:
        if not trap_oid:
            return AlertSeverity.INFO
        trap_oid = trap_oid.strip()
        prefix = "1.3.6.1.6.3.1.1.5."
        if trap_oid.startswith(prefix):
            rest = trap_oid[len(prefix):]
            suffix = rest.split(".", 1)[0] if rest else ""
            return _STD_TRAP_SUFFIX_SEVERITY.get(suffix, AlertSeverity.INFO)
        return AlertSeverity.INFO

    @staticmethod
    def _format_one(event: dict[str, Any]) -> AlertDto:
        event = SnmpProvider._normalize_trap_dict(dict(event))
        trap_oid = event.get("trap_oid") or "unknown"
        agent = event.get("agent_address") or "unknown"
        hostname = event.get("hostname") or agent
        name = event.get("name") or f"SNMP trap {trap_oid}"
        message = event.get("message") or event.get("description")
        if not message:
            vbs = event.get("varbinds")
            if isinstance(vbs, list) and vbs:
                message = json.dumps(vbs[:20], default=str)
            else:
                message = f"Trap {trap_oid} from {agent}"

        sev = event.get("severity")
        if isinstance(sev, str):
            try:
                severity = AlertSeverity(sev.lower())
            except ValueError:
                severity = SnmpProvider._severity_for_oid(trap_oid)
        elif isinstance(sev, int):
            try:
                severity = AlertSeverity.from_number(sev)
            except ValueError:
                severity = SnmpProvider._severity_for_oid(trap_oid)
        else:
            severity = SnmpProvider._severity_for_oid(trap_oid)

        st = event.get("status")
        if isinstance(st, str):
            try:
                status = AlertStatus(st.lower())
            except ValueError:
                status = AlertStatus.FIRING
        else:
            status = AlertStatus.FIRING

        last = event.get("lastReceived") or event.get("timestamp")
        if not last:
            last = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

        labels = dict(event.get("labels") or {})
        labels.setdefault("trap_oid", trap_oid)
        labels.setdefault("agent_address", agent)

        alert_id = event.get("id") or str(uuid.uuid4())
        fingerprint = event.get("fingerprint")

        return AlertDto(
            id=alert_id,
            name=name,
            message=str(message),
            description=str(event.get("description") or message),
            status=status,
            severity=severity,
            lastReceived=str(last),
            host=hostname,
            source=["snmp"],
            labels=labels,
            pushed=True,
            fingerprint=fingerprint,
        )

    @staticmethod
    def _format_alert(
        event: dict | list[dict], provider_instance: BaseProvider | None = None
    ) -> AlertDto | list[AlertDto]:
        if isinstance(event, list):
            return [SnmpProvider._format_one(dict(x)) for x in event]

        if isinstance(event, dict) and "snmp_traps" in event:
            traps = event["snmp_traps"]
            if not isinstance(traps, list):
                raise ValueError("snmp_traps must be a list")
            return [SnmpProvider._format_one(dict(x)) for x in traps]

        if isinstance(event, dict) and "traps" in event:
            traps = event["traps"]
            if not isinstance(traps, list):
                raise ValueError("traps must be a list")
            return [SnmpProvider._format_one(dict(x)) for x in traps]

        if not isinstance(event, dict):
            raise TypeError("SNMP format_alert expects dict or list[dict]")

        return SnmpProvider._format_one(event)


if __name__ == "__main__":
    pass
