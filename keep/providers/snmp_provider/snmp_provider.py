"""
SNMP provider for Keep.

Receives SNMP trap notifications via webhook. An external SNMP trap manager
(snmptrapd, Net-SNMP, Zabbix, Nagios, etc.) handles the raw SNMP protocol and
forwards trap data as JSON to Keep's webhook endpoint.

No Python SNMP library is required — this provider only parses JSON payloads.
"""

import logging
from typing import Optional

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


class SnmpProvider(BaseProvider):
    """Receive SNMP trap alerts forwarded as JSON by an external trap manager."""

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]
    PROVIDER_SCOPES = []
    FINGERPRINT_FIELDS = ["id"]

    webhook_description = ""
    webhook_markdown = """
1. Configure your external SNMP trap manager (snmptrapd, Net-SNMP, Zabbix, etc.)
   to forward traps as JSON POST requests to Keep's webhook URL.
2. The webhook URL is `{keep_webhook_api_url}`.
3. Include your Keep API key in the `X-API-KEY` header.
4. The JSON body should follow the format described in the [SNMP provider docs](https://docs.keephq.dev/providers/documentation/snmp-provider).
"""

    # Well-known trap OIDs and their severity mapping.
    # Format: prefix of the OID (without trailing instance).
    _OID_SEVERITY_MAP = {
        "1.3.6.1.6.3.1.1.5.1": AlertSeverity.LOW,  # coldStart
        "1.3.6.1.6.3.1.1.5.2": AlertSeverity.LOW,  # warmStart
        "1.3.6.1.6.3.1.1.5.3": AlertSeverity.HIGH,  # linkDown
        "1.3.6.1.6.3.1.1.5.4": AlertSeverity.INFO,  # linkUp
        "1.3.6.1.6.3.1.1.5.5": AlertSeverity.WARNING,  # authenticationFailure
        "1.3.6.1.6.3.1.1.5.6": AlertSeverity.INFO,  # egpNeighborLoss
    }

    _SEVERITY_STR_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "warn": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
    }

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """No authentication required for webhook-only SNMP provider."""
        pass

    def dispose(self):
        """Nothing to clean up."""
        pass

    @staticmethod
    def _resolve_severity(event: dict) -> AlertSeverity:
        """Determine alert severity from OID or explicit severity field."""

        # Explicit severity field takes priority
        raw_severity = event.get("severity", "")
        if raw_severity:
            mapped = SnmpProvider._SEVERITY_STR_MAP.get(raw_severity.lower())
            if mapped:
                return mapped

        # Fall back to OID lookup
        oid = event.get("oid", "")
        if oid:
            # Strip trailing instance suffix if present (e.g. ".0")
            oid_base = oid.rstrip(".0123456789").rstrip(".")
            # Try progressively shorter prefixes to find a match
            for known_oid, severity in SnmpProvider._OID_SEVERITY_MAP.items():
                if oid.startswith(known_oid) or oid_base == known_oid:
                    return severity

        return AlertSeverity.INFO

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: Optional["BaseProvider"] = None
    ) -> AlertDto | list[AlertDto]:
        """
        Parse an incoming SNMP trap JSON payload into an AlertDto.

        Expected JSON keys (all optional except at least one of oid/message):
          - oid (str): Trap OID, e.g. "1.3.6.1.6.3.1.1.5.3"
          - host (str): Source host/IP that sent the trap
          - message (str): Human-readable trap description
          - severity (str): "critical"|"high"|"warning"|"info"|"low"
          - uptime (str|int): sysUpTime value from the trap PDU
          - variables (dict): Varbind dictionary {oid: value, ...}
          - name (str): Optional alert name override
          - id (str): Optional deduplication ID
        """

        oid = event.get("oid", "")
        host = event.get("host", "unknown")
        message = event.get("message") or event.get("msg") or oid or "SNMP Trap"
        name = event.get("name") or oid or "SNMP Trap"
        alert_id = event.get("id") or oid or None
        uptime = event.get("uptime")
        variables = event.get("variables") or {}

        severity = SnmpProvider._resolve_severity(event)

        alert = AlertDto(
            id=alert_id,
            name=name,
            description=message,
            severity=severity,
            status=AlertStatus.FIRING,
            host=host,
            source=["snmp"],
            oid=oid,
            uptime=uptime,
            variables=variables,
        )

        return alert


if __name__ == "__main__":
    pass
