"""
SNMP Provider for Keep.
Supports receiving SNMP Traps (v1, v2c) and converting them into Keep Alerts.
"""

import dataclasses
import datetime
import logging
import threading
import uuid
import pydantic
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
    bind_address: str = dataclasses.field(
        default="0.0.0.0",
        metadata={
            "required": True,
            "description": "The address to bind the SNMP Trap listener to",
            "hint": "0.0.0.0 to listen on all interfaces",
        },
    )
    port: int = dataclasses.field(
        default=162,
        metadata={
            "required": True,
            "description": "The UDP port to listen for Traps",
            "hint": "Default is 162. Note: ports < 1024 require root privileges.",
        },
    )
    community: str = dataclasses.field(
        default="public",
        metadata={
            "required": True,
            "description": "SNMP Community string",
            "hint": "e.g. public",
        },
    )


class SnmpProvider(BaseProvider):
    """
    SNMP provider class.
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert", "network"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.snmp_engine = None
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
        self.stop_consume()

    def _trap_callback(self, snmp_engine, state_reference, context_engine_id, context_name, var_binds, cb_ctx):
        """
        Callback function executed when a Trap is received.
        """
        self.logger.info("SNMP Trap received from %s", cb_ctx)
        
        # Extract OIDs and values
        trap_data = {}
        for name, val in var_binds:
            oid = str(name)
            value = str(val.prettyPrint())
            trap_data[oid] = value
            self.logger.debug("OID: %s, Value: %s", oid, value)

        # Create a Keep Alert
        try:
            alert = self._format_trap_to_alert(trap_data, cb_ctx)
            self._push_alert(alert)
        except Exception:
            self.logger.exception("Failed to push SNMP trap alert to Keep")

    def _format_trap_to_alert(self, trap_data: dict, source_info: any) -> dict:
        """
        Converts raw trap data into a Keep-compatible Alert dictionary.
        """
        # Attempt to find a meaningful name from the Trap (e.g., sysName or specific OID)
        # 1.3.6.1.6.3.1.1.4.1.0 is snmpTrapOID.0
        trap_oid = trap_data.get("1.3.6.1.6.3.1.1.4.1.0", "unknown-trap")
        
        return {
            "id": str(uuid.uuid4()),
            "name": f"SNMP Trap: {trap_oid}",
            "status": AlertStatus.FIRING,
            "lastReceived": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "environment": self.config.details.get("environment", "production"),
            "service": "network-device",
            "source": ["snmp"],
            "message": f"Received SNMP Trap {trap_oid} from {source_info}",
            "description": "SNMP Trap captured by Keep SNMP Provider",
            "severity": AlertSeverity.CRITICAL, # Traps are usually critical by default
            "fingerprint": hashlib.sha256(f"{trap_oid}-{source_info}".encode()).hexdigest(),
            "payload": trap_data, # Include all OIDs in the payload
        }

    def start_consume(self):
        """
        Starts the SNMP Trap listener.
        """
        self.logger.info(
            "Starting SNMP Trap listener on %s:%s",
            self.authentication_config.bind_address,
            self.authentication_config.port,
        )
        self.consume = True
        self.snmp_engine = engine.SnmpEngine()

        # Configure Community-based security (SNMP v1/v2c)
        config.addV1System(self.snmp_engine, "keep-area", self.authentication_config.community)

        # Configure Transport Endpoint
        try:
            config.addTransport(
                self.snmp_engine,
                udp.domainName,
                udp.UdpTransport().openServerMode(
                    (self.authentication_config.bind_address, self.authentication_config.port)
                ),
            )
        except Exception as e:
            self.logger.error("Failed to bind SNMP port %s: %s", self.authentication_config.port, e)
            self.consume = False
            return

        # Register Callback
        ntfrcv.NotificationReceiver(self.snmp_engine, self._trap_callback)

        self.snmp_engine.transportDispatcher.jobStarted(1)

        try:
            while self.consume:
                # Run the dispatcher loop
                self.snmp_engine.transportDispatcher.runDispatcher()
        except Exception:
            self.logger.exception("Error in SNMP Trap dispatcher loop")
        finally:
            self.snmp_engine.transportDispatcher.closeDispatcher()
            self.logger.info("SNMP Trap listener stopped")

    def stop_consume(self):
        """
        Stops the SNMP Trap listener.
        """
        self.consume = False
        if self.snmp_engine:
            self.snmp_engine.transportDispatcher.jobFinished(1)

    def status(self):
        if self.consume:
            return {"status": "running", "error": ""}
        return {"status": "stopped", "error": ""}

import hashlib
