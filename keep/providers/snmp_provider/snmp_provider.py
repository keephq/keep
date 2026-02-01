"""
SNMPProvider is a class that handles SNMP trap events as alerts.
"""

import dataclasses
import datetime
from typing import Optional

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SNMPProviderAuthConfig:
    """
    SNMPProviderAuthConfig holds the configuration for SNMP trap reception.
    """

    community_string: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMP Community String for validation (optional)",
            "sensitive": True,
        },
        default="public",
    )


class SNMPProvider(BaseProvider):
    """
    SNMPProvider allows Keep to receive SNMP traps as alerts.
    
    SNMP (Simple Network Management Protocol) is widely used for network 
    device monitoring. This provider receives SNMP trap events via webhook
    and converts them to Keep alerts.
    
    Note: This provider receives traps forwarded via an SNMP trap receiver
    (like snmptrapd) configured to send webhooks to Keep.
    """
    
    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring", "Network"]
    PROVIDER_SCOPES = [
        ProviderScope(name="webhook_receiver", description="Can receive SNMP trap webhooks"),
    ]

    # SNMP Generic Trap Types mapping
    # 0=coldStart, 1=warmStart, 2=linkDown, 3=linkUp, 4=authFailure, 5=egpNeighborLoss, 6=enterpriseSpecific
    TRAP_SEVERITY_MAP = {
        0: AlertSeverity.WARNING,   # coldStart
        1: AlertSeverity.INFO,      # warmStart
        2: AlertSeverity.CRITICAL,  # linkDown
        3: AlertSeverity.LOW,       # linkUp (recovery)
        4: AlertSeverity.WARNING,   # authenticationFailure
        5: AlertSeverity.WARNING,   # egpNeighborLoss
        6: AlertSeverity.WARNING,   # enterpriseSpecific (default)
    }

    TRAP_STATUS_MAP = {
        0: AlertStatus.FIRING,   # coldStart
        1: AlertStatus.FIRING,   # warmStart
        2: AlertStatus.FIRING,   # linkDown
        3: AlertStatus.RESOLVED, # linkUp
        4: AlertStatus.FIRING,   # authenticationFailure
        5: AlertStatus.FIRING,   # egpNeighborLoss
        6: AlertStatus.FIRING,   # enterpriseSpecific
    }

    TRAP_TYPE_NAMES = {
        0: "Cold Start",
        1: "Warm Start",
        2: "Link Down",
        3: "Link Up",
        4: "Authentication Failure",
        5: "EGP Neighbor Loss",
        6: "Enterprise Specific",
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """
        Validates the configuration of the SNMP provider.
        """
        self.authentication_config = SNMPProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate the scopes of the provider.
        SNMP provider primarily receives webhooks, so validation is minimal.
        """
        return {"webhook_receiver": True}

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: Optional["SNMPProvider"] = None
    ) -> AlertDto:
        """
        Formats an incoming SNMP trap event to AlertDto.
        
        Expected event format (from snmptrapd webhook forwarder):
        {
            "agent_address": "192.168.1.1",
            "generic_trap": 2,
            "specific_trap": 0,
            "enterprise": "1.3.6.1.4.1.9.9.43",
            "timestamp": "2024-01-15T10:30:00Z",
            "varbinds": [
                {"oid": "1.3.6.1.2.1.1.3.0", "value": "12345"},
                {"oid": "1.3.6.1.2.1.2.2.1.1", "value": "eth0"}
            ],
            "community": "public",
            "version": "2c"
        }
        
        Also supports simpler format:
        {
            "host": "192.168.1.1",
            "trap_type": "linkDown",
            "message": "Interface eth0 is down",
            "oid": "1.3.6.1.4.1.9.9.43.1.1"
        }
        """
        # Extract agent/host address
        agent_address = event.get("agent_address", 
                        event.get("host", 
                        event.get("source_ip", "unknown")))
        
        # Get trap type - could be numeric or string
        generic_trap = event.get("generic_trap")
        trap_type_str = event.get("trap_type", "")
        
        if generic_trap is not None:
            try:
                generic_trap = int(generic_trap)
            except (ValueError, TypeError):
                generic_trap = 6  # Default to enterprise-specific
        else:
            # Map string trap types
            trap_type_map = {
                "coldstart": 0,
                "warmstart": 1,
                "linkdown": 2,
                "linkup": 3,
                "authfailure": 4,
                "authenticationfailure": 4,
                "egpneighborloss": 5,
            }
            generic_trap = trap_type_map.get(trap_type_str.lower().replace(" ", ""), 6)
        
        # Get severity and status based on trap type
        severity = SNMPProvider.TRAP_SEVERITY_MAP.get(generic_trap, AlertSeverity.WARNING)
        status = SNMPProvider.TRAP_STATUS_MAP.get(generic_trap, AlertStatus.FIRING)
        trap_name = SNMPProvider.TRAP_TYPE_NAMES.get(generic_trap, "Enterprise Specific")
        
        # Build description from varbinds or message
        description = event.get("message", "")
        if not description and "varbinds" in event:
            varbind_strs = []
            for vb in event.get("varbinds", []):
                oid = vb.get("oid", "")
                value = vb.get("value", "")
                varbind_strs.append(f"{oid}={value}")
            description = "; ".join(varbind_strs)
        
        if not description:
            description = f"SNMP {trap_name} trap from {agent_address}"
        
        # Get enterprise OID
        enterprise = event.get("enterprise", event.get("oid", ""))
        specific_trap = event.get("specific_trap", 0)
        
        # Create unique fingerprint
        fingerprint = f"snmp-{agent_address}-{enterprise}-{generic_trap}-{specific_trap}"
        
        # Build labels
        labels = {
            "agent_address": agent_address,
            "generic_trap": str(generic_trap),
            "trap_type": trap_name,
            "snmp_version": event.get("version", event.get("snmp_version", "2c")),
        }
        
        if enterprise:
            labels["enterprise_oid"] = enterprise
        if specific_trap:
            labels["specific_trap"] = str(specific_trap)
        if event.get("community"):
            labels["community"] = event.get("community")
        
        # Add any extra fields as labels
        for key in ["interface", "port", "ifIndex", "ifName", "ifDescr"]:
            if key in event:
                labels[key] = str(event[key])
        
        # Parse timestamp
        timestamp_str = event.get("timestamp", event.get("time"))
        if timestamp_str:
            try:
                last_received = datetime.datetime.fromisoformat(
                    timestamp_str.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                last_received = datetime.datetime.now(datetime.timezone.utc)
        else:
            last_received = datetime.datetime.now(datetime.timezone.utc)
        
        return AlertDto(
            id=event.get("id", fingerprint),
            name=f"SNMP {trap_name}: {agent_address}",
            description=description,
            status=status,
            severity=severity,
            source=["snmp"],
            lastReceived=last_received,
            fingerprint=fingerprint,
            labels=labels,
        )

    def _get_alerts(self) -> list[AlertDto]:
        """
        SNMP provider is webhook-based and doesn't poll for alerts.
        Returns empty list as alerts come via webhooks.
        """
        return []


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    # Test the provider with sample trap data
    sample_trap = {
        "agent_address": "192.168.1.100",
        "generic_trap": 2,
        "specific_trap": 0,
        "enterprise": "1.3.6.1.4.1.9.9.43",
        "varbinds": [
            {"oid": "1.3.6.1.2.1.2.2.1.1", "value": "2"},
            {"oid": "1.3.6.1.2.1.2.2.1.2", "value": "GigabitEthernet0/1"},
        ],
        "version": "2c"
    }
    
    alert = SNMPProvider._format_alert(sample_trap)
    print(f"Alert: {alert.name}")
    print(f"Status: {alert.status}")
    print(f"Severity: {alert.severity}")
    print(f"Description: {alert.description}")
