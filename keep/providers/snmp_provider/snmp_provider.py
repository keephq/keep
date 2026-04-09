"""
SNMP Provider is a class that allows to ingest/digest data from SNMP devices.
"""

import dataclasses
import logging

import pydantic
from pysnmp.hlapi import *

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP authentication configuration.
    """

    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SNMP Device Host",
            "hint": "192.168.1.1",
            "sensitive": False,
        }
    )
    port: int = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMP Device Port",
            "hint": "161",
            "sensitive": False,
        },
        default=161,
    )
    community: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SNMP Community String",
            "hint": "public",
            "sensitive": True,
        },
        default="public",
    )
    version: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMP Version (1, 2c, 3 - v3 not yet supported)",
            "hint": "2c",
            "sensitive": False,
        },
        default="2c",
    )


class SnmpProvider(BaseProvider):
    """
    Query SNMP devices from Keep.
    """

    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["networking", "monitoring"]

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

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def _query(self, oid: str, method: str = "get", **kwargs) -> dict:
        """
        Query an SNMP device.

        Args:
            oid (str): The OID to query.
            method (str): The method to use (get, walk).

        Returns:
            dict: The result of the query.
        """
        self.logger.info(f"Querying SNMP device {self.authentication_config.host} for OID {oid} using {method}")
        
        community_data = CommunityData(self.authentication_config.community, mpModel=1 if self.authentication_config.version == "2c" else 0)
        transport_target = UdpTransportTarget((self.authentication_config.host, self.authentication_config.port))
        
        results = {}
        if method.lower() == "get":
            error_indication, error_status, error_index, var_binds = next(
                getCmd(SnmpEngine(), community_data, transport_target, ContextData(), ObjectType(ObjectIdentity(oid)))
            )
            if error_indication:
                raise Exception(f"SNMP Error: {error_indication}")
            elif error_status:
                raise Exception(f"SNMP Status Error: {error_status.prettyPrint()} at {error_index and var_binds[int(error_index) - 1][0] or '?'}")
            else:
                for var_bind in var_binds:
                    results[str(var_bind[0])] = str(var_bind[1])
        
        elif method.lower() == "walk":
            for (error_indication, error_status, error_index, var_binds) in nextCmd(
                SnmpEngine(), community_data, transport_target, ContextData(), ObjectType(ObjectIdentity(oid)), lexicographicMode=False
            ):
                if error_indication:
                    raise Exception(f"SNMP Error: {error_indication}")
                elif error_status:
                    raise Exception(f"SNMP Status Error: {error_status.prettyPrint()} at {error_index and var_binds[int(error_index) - 1][0] or '?'}")
                else:
                    for var_bind in var_binds:
                        results[str(var_bind[0])] = str(var_bind[1])
        
        return results

    def _get_alerts(self) -> list[AlertDto]:
        # SNMP provider doesn't pull alerts by default, it's used for querying or receiving traps
        return []

    @staticmethod
    def _format_alert(event: dict, provider_instance: "BaseProvider" = None) -> AlertDto:
        # Placeholder for SNMP Trap formatting if implemented in the future
        return AlertDto(
            id=event.get("id", "snmp-trap"),
            name=event.get("name", "SNMP Trap"),
            status=AlertStatus.FIRING,
            severity=AlertSeverity.INFO,
            source=["snmp"],
            **event
        )

if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Mock config
    config = ProviderConfig(
        description="SNMP Provider",
        authentication={
            "host": "localhost",
            "community": "public",
        },
    )
    provider = SnmpProvider(context_manager, "snmp", config)
    print("SNMP Provider Initialized")
