"""
SNMP Provider allows receiving SNMP traps/events as alerts in Keep.

SNMP (Simple Network Management Protocol) traps are notifications sent from
network devices to a management station when certain events occur. This provider
receives SNMP trap data forwarded as JSON via Keep's webhook endpoint and
converts them into Keep alerts.
"""

import dataclasses
import datetime
import hashlib
import logging
from typing import Optional

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)

GENERIC_TRAP_TYPES = {
    0: "coldStart",
    1: "warmStart",
    2: "linkDown",
    3: "linkUp",
    4: "authenticationFailure",
    5: "egpNeighborLoss",
    6: "enterpriseSpecific",
}

GENERIC_TRAP_SEVERITIES = {
    0: AlertSeverity.WARNING,
    1: AlertSeverity.INFO,
    2: AlertSeverity.HIGH,
    3: AlertSeverity.INFO,
    4: AlertSeverity.WARNING,
    5: AlertSeverity.WARNING,
    6: AlertSeverity.INFO,
}


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP Provider authentication configuration.
    """

    community_string: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMP Community String (for validating incoming traps)",
            "sensitive": True,
            "hint": "public",
        },
        default=None,
    )


class SnmpProvider(BaseProvider):
    """Receive SNMP traps/events as alerts in Keep."""

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="receive_traps",
            description="Receive SNMP traps as alerts",
            mandatory=True,
            alias="Receive Traps",
        )
    ]

    FINGERPRINT_FIELDS = ["trap_oid", "agent_address"]

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send SNMP traps to Keep, you need to configure an SNMP trap receiver (such as snmptrapd) to forward traps as JSON to Keep's webhook endpoint.

**Option 1: Using snmptrapd with a forwarding script**

1. Configure snmptrapd to execute a script on trap receipt.
2. The script should POST the trap data as JSON to: {keep_webhook_api_url}
3. Include the header `x-api-key: {api_key}` for authentication.

Example JSON payload format:
```json
{{
    "trap_oid": "1.3.6.1.6.3.1.1.5.3",
    "agent_address": "192.168.1.1",
    "community": "public",
    "generic_trap": 2,
    "specific_trap": 0,
    "timestamp": "2024-01-15T10:30:00Z",
    "enterprise": "1.3.6.1.4.1.9",
    "varbinds": [
        {{"oid": "1.3.6.1.2.1.2.2.1.1.2", "value": "2", "type": "INTEGER"}},
        {{"oid": "1.3.6.1.2.1.2.2.1.7.2", "value": "down", "type": "STRING"}}
    ],
    "description": "Interface eth0 went down",
    "severity": "high"
}}
```

**Option 2: Using a dedicated SNMP-to-HTTP gateway**

Tools like `snmptraps` or custom scripts can convert SNMP traps to HTTP webhooks.
Configure them to POST to the Keep webhook URL with the JSON format above.

**Required fields:** `trap_oid` or `oid`
**Optional fields:** `agent_address`, `community`, `generic_trap`, `specific_trap`,
`timestamp`, `enterprise`, `varbinds`, `description`, `severity`, `name`, `status`
"""

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
    }

    STATUS_MAP = {
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
        return {"receive_traps": True}

    @staticmethod
    def _get_trap_name(event: dict) -> str:
        trap_oid = event.get("trap_oid") or event.get("oid") or ""
        generic_trap = event.get("generic_trap")

        if event.get("name"):
            return event["name"]

        if generic_trap is not None and int(generic_trap) in GENERIC_TRAP_TYPES:
            return GENERIC_TRAP_TYPES[int(generic_trap)]

        if trap_oid:
            return f"SNMP Trap {trap_oid}"

        return "SNMP Trap"

    @staticmethod
    def _get_severity(event: dict) -> AlertSeverity:
        severity_str = event.get("severity", "").lower()
        if severity_str in SnmpProvider.SEVERITIES_MAP:
            return SnmpProvider.SEVERITIES_MAP[severity_str]

        generic_trap = event.get("generic_trap")
        if generic_trap is not None:
            try:
                return GENERIC_TRAP_SEVERITIES.get(
                    int(generic_trap), AlertSeverity.INFO
                )
            except (ValueError, TypeError):
                pass

        return AlertSeverity.INFO

    @staticmethod
    def _get_status(event: dict) -> AlertStatus:
        status_str = event.get("status", "").lower()
        if status_str in SnmpProvider.STATUS_MAP:
            return SnmpProvider.STATUS_MAP[status_str]

        generic_trap = event.get("generic_trap")
        if generic_trap is not None:
            try:
                trap_type = int(generic_trap)
                if trap_type in (2, 4, 5):
                    return AlertStatus.FIRING
                if trap_type in (1, 3):
                    return AlertStatus.RESOLVED
            except (ValueError, TypeError):
                pass

        return AlertStatus.FIRING

    @staticmethod
    def _build_description(event: dict) -> str:
        if event.get("description"):
            return event["description"]

        if event.get("message"):
            return event["message"]

        parts = []
        trap_oid = event.get("trap_oid") or event.get("oid")
        if trap_oid:
            parts.append(f"Trap OID: {trap_oid}")

        agent = event.get("agent_address") or event.get("source_ip")
        if agent:
            parts.append(f"Agent: {agent}")

        varbinds = event.get("varbinds") or event.get("variables") or []
        if varbinds:
            for vb in varbinds[:5]:
                oid = vb.get("oid", "")
                value = vb.get("value", "")
                parts.append(f"{oid}={value}")

        return "; ".join(parts) if parts else "SNMP Trap received"

    @staticmethod
    def _get_fingerprint(event: dict) -> str:
        trap_oid = event.get("trap_oid") or event.get("oid") or ""
        agent_address = (
            event.get("agent_address") or event.get("source_ip") or ""
        )
        fingerprint_str = f"{trap_oid}|{agent_address}"
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        trap_oid = event.get("trap_oid") or event.get("oid")
        agent_address = event.get("agent_address") or event.get("source_ip")
        enterprise = event.get("enterprise")
        generic_trap = event.get("generic_trap")
        specific_trap = event.get("specific_trap")
        community = event.get("community")
        varbinds = event.get("varbinds") or event.get("variables") or []
        timestamp = event.get("timestamp") or event.get("uptime")

        last_received = timestamp
        if not last_received:
            last_received = datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()

        labels = {}
        if trap_oid:
            labels["trap_oid"] = trap_oid
        if enterprise:
            labels["enterprise"] = enterprise
        if generic_trap is not None:
            labels["generic_trap"] = str(generic_trap)
        if specific_trap is not None:
            labels["specific_trap"] = str(specific_trap)
        if community:
            labels["community"] = community
        if agent_address:
            labels["agent_address"] = agent_address

        alert = AlertDto(
            id=event.get("id") or SnmpProvider._get_fingerprint(event),
            name=SnmpProvider._get_trap_name(event),
            status=SnmpProvider._get_status(event),
            severity=SnmpProvider._get_severity(event),
            lastReceived=last_received,
            description=SnmpProvider._build_description(event),
            source=["snmp"],
            trap_oid=trap_oid,
            agent_address=agent_address,
            enterprise=enterprise,
            generic_trap=generic_trap,
            specific_trap=specific_trap,
            community=community,
            varbinds=varbinds,
            labels=labels,
            fingerprint=SnmpProvider._get_fingerprint(event),
        )

        return alert


if __name__ == "__main__":
    pass
