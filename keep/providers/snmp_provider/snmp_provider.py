"""
SNMP Provider for Keep.
"""

import dataclasses
from typing import Optional

import pydantic
from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
)

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """Authentication configuration for SNMP."""

    community: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SNMP Community String (e.g., public)",
        }
    )
    host: str = dataclasses.field(
        metadata={"required": True, "description": "Target Device IP or Hostname"}
    )
    port: int = dataclasses.field(
        default=161,
        metadata={"required": False, "description": "SNMP Port (default: 161)"},
    )


class SnmpProvider(BaseProvider):
    """
    Enables fetching metrics from SNMP-enabled devices.
    """

    provider_id = "snmp"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """Validates that community and host are provided."""
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    def query(self, **kwargs):
        """
        Performs an SNMP GET operation.
        kwargs must include 'oid'.
        """
        oid = kwargs.get("oid")
        if not oid:
            raise Exception("OID is required for SNMP query")

        # Extract config
        community = self.authentication_config.community
        host = self.authentication_config.host
        port = self.authentication_config.port

        # Perform SNMP GET (mpModel=1 is SNMP v2c)
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(community, mpModel=1),
            UdpTransportTarget((host, port), timeout=1, retries=0),
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
        )

        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

        if errorIndication:
            raise Exception(f"SNMP Error: {errorIndication}")
        elif errorStatus:
            raise Exception(f"SNMP Error: {errorStatus.prettyPrint()} at {errorIndex}")
        else:
            results = {}
            for varBind in varBinds:
                results[str(varBind[0])] = str(varBind[1])
            return results

    def dispose(self):
        """No resources to dispose for SNMP."""
        pass
