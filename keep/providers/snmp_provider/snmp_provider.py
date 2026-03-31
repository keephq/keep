"""
SNMP provider for Keep.
"""

import dataclasses

from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    NotificationType,
    ObjectIdentity,
    ObjectType,
    OctetString,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
    sendNotification,
)

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@dataclasses.dataclass
class SnmpProviderAuthConfig:
    """SNMP authentication configuration."""

    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SNMP Agent Host",
            "hint": "127.0.0.1",
        },
    )
    port: int = dataclasses.field(
        default=162,
        metadata={
            "required": False,
            "description": "SNMP Agent Port",
            "hint": "162",
        },
    )
    community: str = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": "SNMP Community String",
            "hint": "public",
        },
    )
    version: str = dataclasses.field(
        default="2c",
        metadata={
            "required": False,
            "description": "SNMP Version (1, 2c, 3). Default is 2c.",
            "hint": "2c",
        },
    )


class SnmpProvider(BaseProvider):
    """Enrich alerts with data using SNMP."""

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """Validates required configuration for SNMP provider."""
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    def _query(self, oid: str, **kwargs: dict):
        """
        Query SNMP OID.
        """
        if self.authentication_config.version in ["1", "v1"]:
            mp_model = 0
        else:  # default 2c
            mp_model = 1

        errorIndication, errorStatus, errorIndex, varBinds = next(
            getCmd(
                SnmpEngine(),
                CommunityData(self.authentication_config.community, mpModel=mp_model),
                UdpTransportTarget(
                    (self.authentication_config.host, int(self.authentication_config.port))
                ),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
            )
        )

        if errorIndication:
            self.logger.error(f"SNMP Query Error: {errorIndication}")
            raise Exception(f"SNMP Query Error: {errorIndication}")
        elif errorStatus:
            err_msg = f"{errorStatus.prettyPrint()} at {errorIndex and varBinds[int(errorIndex) - 1][0] or '?'}"
            self.logger.error(f"SNMP Query Status Error: {err_msg}")
            raise Exception(err_msg)
        else:
            result = {}
            for varBind in varBinds:
                result[str(varBind[0])] = str(varBind[1])
            return result

    def _notify(self, trap_oid: str, message: str = "", **kwargs: dict):
        """
        Send SNMP Trap.
        """
        if self.authentication_config.version in ["1", "v1"]:
            mp_model = 0
        else:
            mp_model = 1

        var_binds = []
        if message:
            # Add message as a custom varbind or system description
            var_binds.append(
                ObjectType(ObjectIdentity("1.3.6.1.2.1.1.1.0"), OctetString(message))
            )

        errorIndication, errorStatus, errorIndex, varBinds = next(
            sendNotification(
                SnmpEngine(),
                CommunityData(self.authentication_config.community, mpModel=mp_model),
                UdpTransportTarget(
                    (self.authentication_config.host, int(self.authentication_config.port))
                ),
                ContextData(),
                "trap",
                NotificationType(ObjectIdentity(trap_oid)).addVarBinds(*var_binds),
            )
        )

        if errorIndication:
            self.logger.error(f"SNMP Notify Error: {errorIndication}")
            raise Exception(f"SNMP Notify Error: {errorIndication}")

        return {"status": "success", "message": "Trap sent successfully"}

    def dispose(self):
        pass


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    config = {
        "authentication": {
            "host": "127.0.0.1",
            "port": 162,
            "community": "public",
            "version": "2c",
        },
    }
    provider = SnmpProvider(
        context_manager=context_manager,
        provider_id="snmp-provider",
        config=ProviderConfig(**config),
    )
    print("SNMPProvider loaded successfully.")
