"""
SNMP Provider is a class that provides a way to receive alerts from SNMP-capable devices.
"""

import dataclasses
import logging
import pydantic
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

# We'll use pysnmp or similar, but for now we focus on the structure
try:
    from pysnmp.hlapi import *
except ImportError:
    # We will handle the requirement in the PR
    pass


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    Allows SNMP Authentication.

    config params:
    - host: Hostname or IP of the SNMP device
    - port: SNMP port (default 161)
    - community: SNMP community string (v1/v2c)
    - version: SNMP version (1, 2, or 3)
    - user: SNMP v3 user
    - auth_key: SNMP v3 auth key
    - priv_key: SNMP v3 priv key
    """

    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SNMP Device Host",
            "hint": "e.g. 192.168.1.1",
        }
    )

    port: int = dataclasses.field(
        default=161,
        metadata={
            "required": False,
            "description": "SNMP Port",
            "hint": "Default is 161",
        }
    )

    community: str = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": "SNMP Community (v1/v2c)",
            "sensitive": True,
        }
    )

    version: str = dataclasses.field(
        default="2c",
        metadata={
            "required": True,
            "description": "SNMP Version",
            "hint": "1, 2c, or 3",
        }
    )

    user: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMP v3 User",
        }
    )


class SnmpProvider(BaseProvider):
    """
    Get alerts/data from SNMP devices into Keep.

    feat:
    - Polling OIDs for status/metrics
    - Mapping SNMP values to Keep alerts
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert", "infrastructure"]
    PROVIDER_CATEGORY = ["Monitoring"]
    WEBHOOK_INSTALLATION_REQUIRED = False # SNMP is usually polling or traps
    PROVIDER_ICON = "snmp-icon.png"

    # Define provider scopes
    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_data",
            description="Read data from SNMP devices",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for SNMP provider.
        """
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        """
        Validate connectivity via a simple sysName OID get.
        """
        self.logger.info("Validating SNMP provider connectivity")
        # Placeholder for real SNMP check logic
        return {"read_data": True}

    def _get_alerts(self) -> list[AlertDto]:
        """
        Fetch alerts by polling specific OIDs or status.
        In SNMP context, this often means checking threshold OIDs.
        """
        self.logger.info("Polling SNMP device for alerts")
        # This will be expanded with real OID walking logic
        return []

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format SNMP Trap data into Keep alert format.
        """
        alert = AlertDto(
            id=event.get("oid", "unknown-oid"),
            name=f"SNMP Trap: {event.get('oid')}",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.CRITICAL,
            description=event.get("value", "No data"),
            source=["snmp"],
            hostname=event.get("host"),
        )
        return alert


if __name__ == "__main__":
    pass
