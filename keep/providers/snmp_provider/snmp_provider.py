import dataclasses
import logging

import pydantic
from pysnmp.hlapi import *
from pysnmp.carrier.asyncore.dispatch import AsyncoreDispatcher
from pysnmp.carrier.asyncore.dgram import udp
from pyasn1.codec.ber import decoder
from pysnmp.proto import api

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP authentication configuration.
    """

    port: int = dataclasses.field(
        default=1162,
        metadata={
            "required": True,
            "description": "SNMP Trap listening port",
            "hint": "Default is 1162 (standard 162 usually requires root)",
        },
    )
    community: str = dataclasses.field(
        default="public",
        metadata={
            "required": True,
            "description": "SNMP Community string (v1/v2c)",
            "hint": "e.g. public",
            "sensitive": True,
        },
    )


class SnmpProvider(BaseProvider):
    """
    SNMP provider class for receiving traps.
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.consume = False

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
        self.consume = False

    def _cbFun(self, snmpEngine, stateReference, contextEngineId, contextName, varBinds, cbCtx):
        """
        Callback function for receiving traps.
        """
        self.logger.info("SNMP Trap received")
        trap_data = {}
        for name, val in varBinds:
            trap_data[name.prettyPrint()] = val.prettyPrint()
        
        try:
            self._push_alert(trap_data)
        except Exception:
            self.logger.exception("Error pushing SNMP trap as alert")

    def start_consume(self):
        """
        Start listening for SNMP traps.
        """
        self.consume = True
        port = self.authentication_config.port
        community = self.authentication_config.community

        snmpEngine = SnmpEngine()

        # Transport setup
        config.addTransport(
            snmpEngine,
            udp.domainName,
            udp.UdpTransport().openServerMode(('0.0.0.0', port))
        )

        # SNMPv1/2c setup
        config.addV1System(snmpEngine, 'my-area', community)

        # Callback registration
        ntfrcv.NotificationReceiver(snmpEngine, self._cbFun)

        self.logger.info(f"SNMP Trap listener started on port {port} with community '{community}'")
        
        snmpEngine.transportDispatcher.jobStarted(1)

        try:
            while self.consume:
                snmpEngine.transportDispatcher.runDispatcher()
        except Exception:
            self.logger.exception("SNMP Dispatcher error")
        finally:
            snmpEngine.transportDispatcher.closeDispatcher()
            self.logger.info("SNMP Trap listener stopped")

    def stop_consume(self):
        self.consume = False

    @staticmethod
    def _format_alert(event: dict, provider_instance: "SnmpProvider" = None) -> AlertDto:
        # Map SNMP varbinds to Keep Alert fields
        # Common OIDs:
        # sysUpTimeInstance = '1.3.6.1.2.1.1.3.0'
        # snmpTrapOID = '1.3.6.1.6.3.1.1.4.1.0'
        
        trap_oid = event.get('1.3.6.1.6.3.1.1.4.1.0', 'Unknown OID')
        
        return AlertDto(
            id=event.get('id', trap_oid),
            name=f"SNMP Trap: {trap_oid}",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.CRITICAL, # SNMP traps are usually critical events
            message=str(event),
            description="Received SNMP Trap",
            source=["snmp"],
            payload=event
        )
