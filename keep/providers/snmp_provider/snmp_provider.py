"""
SNMP Provider is a class that allows integration with SNMP (Simple Network Management Protocol)
to receive SNMP traps and convert them into Keep alerts.
"""

import dataclasses
import datetime
from typing import Optional

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP Provider authentication configuration.
    SNMP traps typically don't require authentication for receiving,
    but we allow optional community string validation.
    """

    community_string: str = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": "SNMP Community String for trap validation",
            "sensitive": True,
        },
    )

    allowed_hosts: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Comma-separated list of allowed source hosts (optional)",
            "sensitive": False,
        },
    )


class SnmpProvider(BaseProvider):
    """
    Receive SNMP traps and convert them into Keep alerts.
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["id", "source"]

    # SNMP severity mapping based on standard SNMP trap OID values
    # https://datatracker.ietf.org/doc/html/rfc2578
    SEVERITY_MAP = {
        "CRITICAL": AlertSeverity.CRITICAL,
        "MAJOR": AlertSeverity.HIGH,
        "MINOR": AlertSeverity.WARNING,
        "WARNING": AlertSeverity.WARNING,
        "INDETERMINATE": AlertSeverity.INFO,
        "CLEARED": AlertSeverity.INFO,
        "INFO": AlertSeverity.INFO,
        "DEBUG": AlertSeverity.LOW,
    }

    # SNMP trap type to status mapping
    STATUS_MAP = {
        "COLDSTART": AlertStatus.FIRING,
        "WARMSTART": AlertStatus.FIRING,
        "LINKDOWN": AlertStatus.FIRING,
        "LINKUP": AlertStatus.RESOLVED,
        "AUTHENTICATIONFAILURE": AlertStatus.FIRING,
        "EGPNEIGHBORLOSS": AlertStatus.FIRING,
        "ENTERPRISE": AlertStatus.FIRING,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Cleanup any resources when provider is disposed.
        """
        pass

    def validate_config(self):
        """
        Validates the configuration of the SNMP provider.
        """
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: BaseProvider = None
    ) -> AlertDto:
        """
        Format SNMP trap event into Keep AlertDto.

        Args:
            event: Dictionary containing SNMP trap data
            provider_instance: Optional provider instance for context

        Returns:
            AlertDto formatted alert
        """
        # Extract SNMP trap data with fallbacks
        trap_oid = event.get("trap_oid", "")
        source = event.get("source", "unknown")
        community = event.get("community", "public")
        uptime = event.get("sys_uptime", "")

        # Extract varbinds (SNMP variables)
        varbinds = event.get("varbinds", {})

        # Try to extract severity from varbinds or use default
        severity_str = varbinds.get("severity", "WARNING").upper()
        severity = SnmpProvider.SEVERITY_MAP.get(
            severity_str, AlertSeverity.WARNING
        )

        # Determine status based on trap type or OID
        trap_type = event.get("trap_type", "ENTERPRISE")
        status = SnmpProvider.STATUS_MAP.get(trap_type, AlertStatus.FIRING)

        # Check for specific resolution indicators in varbinds
        if varbinds.get("state", "").lower() in ["up", "ok", "cleared", "resolved"]:
            status = AlertStatus.RESOLVED

        # Build description from varbinds
        description_parts = []
        if varbinds.get("message"):
            description_parts.append(varbinds.get("message"))
        if varbinds.get("description"):
            description_parts.append(varbinds.get("description"))

        description = " - ".join(description_parts) if description_parts else f"SNMP trap received from {source}"

        # Create alert name from trap OID or type
        alert_name = varbinds.get("alertname", "")
        if not alert_name:
            # Extract meaningful name from OID
            oid_parts = trap_oid.split(".")
            alert_name = oid_parts[-1] if oid_parts else trap_type

        # Build fingerprint fields
        fingerprint = f"{source}:{alert_name}:{trap_oid}"

        # Parse timestamp
        last_received = event.get("timestamp")
        if not last_received:
            last_received = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Extract additional metadata from varbinds
        host = varbinds.get("host", source)
        service = varbinds.get("service", "")
        metric = varbinds.get("metric", "")
        value = varbinds.get("value", "")

        return AlertDto(
            id=event.get("id", fingerprint),
            name=alert_name,
            description=description,
            status=status,
            severity=severity,
            source=["snmp"],
            host=host,
            service=service,
            fingerprint=fingerprint,
            lastReceived=last_received,
            # Additional SNMP-specific fields
            community=community,
            trap_oid=trap_oid,
            trap_type=trap_type,
            sys_uptime=uptime,
            varbinds=varbinds,
            metric=metric,
            metric_value=value,
            raw_event=event,
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate the scopes of the provider.
        For SNMP, we just check if configuration is valid.
        """
        try:
            # SNMP receiver doesn't require external validation
            # The webhook endpoint will handle incoming traps
            scopes = {"configured": True}
        except Exception as e:
            scopes = {
                "configured": f"Error validating SNMP configuration: {e}",
            }

        return scopes


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    # Test configuration
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

    # Test formatting an SNMP trap event
    test_event = {
        "id": "test-123",
        "source": "192.168.1.100",
        "trap_oid": "1.3.6.1.4.1.8072.2.3.0.1",
        "trap_type": "LINKDOWN",
        "community": "public",
        "sys_uptime": "12345678",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "varbinds": {
            "severity": "CRITICAL",
            "message": "Link down on interface eth0",
            "host": "router-01",
            "service": "network",
            "metric": "ifOperStatus",
            "value": "2",
        },
    }

    alert = SnmpProvider._format_alert(test_event, provider)
    print(f"Alert created: {alert}")
