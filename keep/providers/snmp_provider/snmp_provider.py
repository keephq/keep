import dataclasses
import logging
import uuid
import datetime
import time
from typing import Any, Dict, List, Optional

import pydantic
from pysnmp.hlapi import *
from pysnmp.entity import engine, config
from pysnmp.entity.rfc3413 import ntfrcv
from pysnmp.carrier.asyncio.dgram import udp

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP authentication configuration.
    """

    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SNMP Host (for polling)",
            "hint": "e.g. 192.168.1.1",
        }
    )
    port: int = dataclasses.field(
        default=161,
        metadata={
            "required": False,
            "description": "SNMP Port (for polling)",
            "hint": "Default is 161",
        }
    )
    community: str = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": "SNMP Community (v1/v2c)",
            "hint": "Default is public",
            "sensitive": True,
        }
    )
    version: str = dataclasses.field(
        default="2c",
        metadata={
            "required": False,
            "description": "SNMP Version",
            "hint": "1, 2c, or 3",
        }
    )
    trap_port: int = dataclasses.field(
        default=162,
        metadata={
            "required": False,
            "description": "SNMP Trap Port (to listen on)",
            "hint": "Default is 162. Note: Ports < 1024 might require root.",
        }
    )
    # v3 settings
    user: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMP v3 User",
        }
    )
    auth_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMP v3 Auth Key",
            "sensitive": True,
        }
    )
    priv_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMP v3 Priv Key",
            "sensitive": True,
        }
    )


class SnmpProvider(BaseProvider):
    """
    SNMP Provider class for OID polling and Trap receiving.
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["network", "alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="poll",
            description="Poll OIDs from a device",
            mandatory=True,
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.stop_requested = False

    def validate_config(self):
        """
        Validates required configuration for SNMP provider.
        """
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        """
        Validate scopes for the provider.
        """
        # For SNMP, we just try to poll sysDescr (1.3.6.1.2.1.1.1.0)
        try:
            self._query(oids=["1.3.6.1.2.1.1.1.0"])
            return {"poll": True}
        except Exception as e:
            self.logger.exception("Failed to validate SNMP scopes")
            return {"poll": str(e)}

    def dispose(self):
        """
        Dispose the provider.
        """
        self.stop_consume()

    def _query(self, **kwargs: Any) -> Any:
        """
        Poll SNMP OIDs.
        """
        host = kwargs.get("host") or self.authentication_config.host
        port = kwargs.get("port") or self.authentication_config.port
        oids = kwargs.get("oids") or []
        
        if not oids:
            return []

        if self.authentication_config.version == "3":
            auth_data = UsmUserData(
                self.authentication_config.user,
                self.authentication_config.auth_key,
                self.authentication_config.priv_key,
            )
        else:
            auth_data = CommunityData(self.authentication_config.community, mpModel=(0 if self.authentication_config.version == "1" else 1))

        iterator = getCmd(
            SnmpEngine(),
            auth_data,
            UdpTransportTarget((host, port)),
            ContextData(),
            *[ObjectType(ObjectIdentity(oid)) for oid in oids]
        )

        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

        if errorIndication:
            raise Exception(f"SNMP Error: {errorIndication}")
        elif errorStatus:
            raise Exception(f"SNMP Error Status: {errorStatus.prettyPrint()} at {errorIndex and varBinds[int(errorIndex) - 1][0] or '?'}")
        else:
            result = {}
            for name, val in varBinds:
                result[name.prettyPrint()] = val.prettyPrint()
            return result

    def start_consume(self):
        """
        Start SNMP Trap listener.
        """
        self.logger.info(
            f"Starting SNMP trap listener on port {self.authentication_config.trap_port}"
        )
        snmpEngine = engine.SnmpEngine()

        # SNMP v1/v2c setup
        config.addV1System(
            snmpEngine, "keep-trap-area", self.authentication_config.community
        )

        # SNMP v3 setup if user provided
        if self.authentication_config.user:
            config.addV3User(
                snmpEngine,
                self.authentication_config.user,
                config.usmHMACMD5AuthProtocol,  # Defaulting to MD5 for now, should be configurable
                self.authentication_config.auth_key,
                config.usmDESPrivProtocol,  # Defaulting to DES for now, should be configurable
                self.authentication_config.priv_key,
            )

        # UDP over IPv4
        try:
            config.addTransport(
                snmpEngine,
                udp.domainName,
                udp.UdpTransport().openServerMode(
                    ("0.0.0.0", self.authentication_config.trap_port)
                ),
            )
        except Exception as e:
            self.logger.error(f"Failed to bind to SNMP trap port: {e}")
            return

        def cbFun(
            snmpEngine, stateReference, contextEngineId, contextName, varBinds, cbCtx
        ):
            self.logger.info("SNMP Trap received")
            
            # Try to get the sender address
            try:
                transportDomain, transportAddress = snmpEngine.msgAndPduDispatcher.getTransportInfo(stateReference)
                sender_address = f"{transportAddress[0]}:{transportAddress[1]}"
            except Exception:
                sender_address = "unknown"

            trap_data = {}
            for name, val in varBinds:
                trap_data[name.prettyPrint()] = val.prettyPrint()

            # Map trap to alert
            alert = {
                "id": str(uuid.uuid4()),
                "name": "SNMP Trap",
                "status": AlertStatus.FIRING,
                "severity": AlertSeverity.INFO,
                "lastReceived": datetime.datetime.now(
                    tz=datetime.timezone.utc
                ).isoformat(),
                "environment": "network",
                "service": "snmp-trap",
                "source": ["snmp"],
                "message": f"SNMP Trap received from {sender_address}",
                "description": "SNMP Trap received",
                **trap_data,
            }
            try:
                self._push_alert(alert)
                self.logger.info("SNMP Trap pushed as alert")
            except Exception as e:
                self.logger.error(f"Failed to push SNMP trap alert: {e}")

        ntfrcv.NotificationReceiver(snmpEngine, cbFun)

        snmpEngine.transportDispatcher.jobStarted(1)

        while not self.stop_requested:
            try:
                # Run the dispatcher for 1 second
                snmpEngine.transportDispatcher.runDispatcher(timeout=1.0)
            except Exception as e:
                self.logger.error(f"Error in SNMP trap dispatcher: {e}")
                # Don't break on small errors, but maybe log
                time.sleep(1)

        snmpEngine.transportDispatcher.closeDispatcher()
        self.logger.info("SNMP trap listener stopped")

    def stop_consume(self):
        """
        Stop SNMP Trap listener.
        """
        self.stop_requested = True
