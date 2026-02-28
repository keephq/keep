"""
SNMP Provider is a class that allows Keep to ingest SNMP traps.
"""

import dataclasses
import datetime
import logging
import random
from typing import Any

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP authentication configuration.
    (Often SNMP Trap receivers are push-based, meaning they receive webhooks. 
     This config can hold community strings or basic auth for related APIs if needed.)
    """

    community_string: str = dataclasses.field(
        default="public",
        metadata={
            "description": "SNMP Community String",
            "hint": "public",
            "sensitive": True,
        }
    )


class SnmpProvider(BaseProvider):
    """
    Ingest SNMP traps into Keep as alerts.
    Typically, a separate SNMP Trap receiver service (like snmptrapd) forwards 
    parsed traps to Keep's webhook/event endpoint, which then maps them via this provider.
    """

    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for SNMP provider.
        """
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        # Standard format for SNMP traps forwarded as JSON
        # Example schema: {"trap_oid": "1.3.6.1.4.1...", "agent_address": "192.168.1.1", "vars": {...}}
        
        trap_oid = event.get("trap_oid", "Unknown OID")
        agent_address = event.get("agent_address", "Unknown Host")
        
        # Try to extract a meaningful message from the trap variables
        vars_dict = event.get("vars", {})
        message_parts = [f"{k}: {v}" for k, v in vars_dict.items()]
        message = "\\n".join(message_parts) if message_parts else f"SNMP Trap received from {agent_address}"

        # Determine severity based on common SNMP paradigms, default to WARNING for traps
        severity = AlertSeverity.WARNING
        if "critical" in message.lower() or "down" in message.lower():
            severity = AlertSeverity.CRITICAL

        return AlertDto(
            id=event.get("id", str(random.randint(10000, 99999))),
            name=f"SNMP Trap: {trap_oid}",
            status=AlertStatus.FIRING,
            lastReceived=datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            source=["snmp"],
            message=message,
            severity=severity,
            environment=event.get("environment", "unknown"),
            hostname=agent_address,
            service=agent_address,
            raw_event=event,
        )

if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    
    provider_config = {
        "authentication": {
            "community_string": "public",
        },
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="snmp",
        provider_type="snmp",
        provider_config=provider_config,
    )
    print("Provider initialized successfully")
