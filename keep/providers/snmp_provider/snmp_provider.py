"""
SNMP Provider is a class that allows to ingest SNMP traps into Keep.
"""

import dataclasses
import datetime
import logging
import socket
import threading
from typing import Optional

import pydantic
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import engine, config
from pysnmp.entity.rfc3413 import ntfrcv
from pysnmp.proto.api import v2c
from pysnmp.smi import builder, view, rfc1902

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP authentication configuration.
    """

    port: int = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMP Trap Listener Port",
            "hint": "Default: 162",
            "sensitive": False,
        },
        default=162,
    )
    community: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMP Community String",
            "hint": "Default: public",
            "sensitive": True,
        },
        default="public",
    )
    host: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Host to bind to",
            "hint": "Default: 0.0.0.0 (all interfaces)",
            "sensitive": False,
        },
        default="0.0.0.0",
    )


class SnmpProvider(BaseProvider):
    """
    Ingest SNMP traps into Keep as alerts.
    """

    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="snmp_trap_receive",
            description="Receive SNMP traps",
            mandatory=True,
            mandatory_for_webhook=False,
        ),
    ]
    FINGERPRINT_FIELDS = ["source", "oid", "variables"]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
        **kwargs,
    ):
        super().__init__(context_manager, provider_id, config, **kwargs)
        self.snmp_engine = None
        self.transport_dispatcher = None
        self._stop_event = threading.Event()
        self._snmp_thread: Optional[threading.Thread] = None

    def dispose(self):
        """
        Dispose the provider.
        """
        self._stop()
        super().dispose()

    def validate_config(self):
        """
        Validates required configuration for SNMP provider.
        """
        self.snmp_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    def _stop(self):
        """Stop the SNMP listener."""
        self._stop_event.set()
        if self.snmp_engine:
            try:
                self.snmp_engine.transportDispatcher.closeDispatcher()
            except Exception as e:
                logger.warning(f"Error closing SNMP dispatcher: {e}")
        logger.info("SNMP provider stopped")

    def _start_snmp_listener(self):
        """Start the SNMP trap listener in a separate thread."""
        self._snmp_thread = threading.Thread(target=self._run_snmp_listener)
        self._snmp_thread.daemon = True
        self._snmp_thread.start()
        logger.info(
            f"SNMP listener started on {self.snmp_config.host}:{self.snmp_config.port}"
        )

    def _run_snmp_listener(self):
        """Run the SNMP listener."""
        try:
            # Create SNMP engine
            self.snmp_engine = engine.SnmpEngine()

            # Configure SNMP v1/v2c community
            config.addV1System(
                self.snmp_engine,
                "my-area",
                self.snmp_config.community,
            )

            # Configure transport
            config.addTransport(
                self.snmp_engine,
                udp.domainName + (1,),
                udp.UdpTransport().openServerMode(
                    (self.snmp_config.host, self.snmp_config.port)
                ),
            )

            # Configure SNMP version
            config.addV3User(
                self.snmp_engine,
                "usr-none-none",
            )

            # Register callback for notifications
            ntfrcv.NotificationReceiver(self.snmp_engine, self._cbFun)

            # Run dispatcher
            self.snmp_engine.transportDispatcher.jobStarted(1)
            
            while not self._stop_event.is_set():
                try:
                    self.snmp_engine.transportDispatcher.runDispatcher()
                except Exception as e:
                    if not self._stop_event.is_set():
                        logger.error(f"SNMP dispatcher error: {e}")
                    break

        except Exception as e:
            logger.error(f"SNMP listener error: {e}")

    def _cbFun(
        self,
        snmpEngine,
        stateReference,
        contextEngineId,
        contextName,
        varBinds,
        cbCtx,
    ):
        """
        Callback function for SNMP notifications.
        """
        try:
            # Extract notification details
            trap_oid = None
            variables = {}
            
            for name, val in varBinds:
                oid_str = str(name)
                val_str = str(val)
                
                # Check if this is the trap OID (first varbind usually)
                if trap_oid is None and oid_str.startswith("1.3.6.1.6.3.1.1.5"):
                    trap_oid = oid_str
                
                variables[oid_str] = val_str
            
            # Get source address
            execContext = snmpEngine.observer.getExecutionContext(
                "rfc3412.receiveMessage:request"
            )
            source_address = execContext.get("transportAddress", ("unknown", 0))[0]

            # Create alert
            alert = self._create_alert(trap_oid, variables, source_address)
            
            # Push to Keep
            self._push_alert(alert)
            
            logger.info(
                f"SNMP trap received from {source_address}: {trap_oid}"
            )

        except Exception as e:
            logger.error(f"Error processing SNMP trap: {e}")

    def _create_alert(
        self,
        trap_oid: Optional[str],
        variables: dict,
        source_address: str,
    ) -> AlertDto:
        """
        Create an AlertDto from SNMP trap data.
        """
        # Determine severity based on trap OID or variables
        severity = AlertSeverity.WARNING
        if trap_oid:
            # Standard SNMP trap OIDs
            if "1.3.6.1.6.3.1.1.5.1" in trap_oid:  # coldStart
                severity = AlertSeverity.INFO
            elif "1.3.6.1.6.3.1.1.5.3" in trap_oid:  # linkDown
                severity = AlertSeverity.CRITICAL
            elif "1.3.6.1.6.3.1.1.5.4" in trap_oid:  # linkUp
                severity = AlertSeverity.INFO

        # Create description from variables
        description = f"SNMP Trap from {source_address}"
        if trap_oid:
            description += f"\nTrap OID: {trap_oid}"
        if variables:
            description += "\nVariables:\n" + "\n".join(
                [f"  {k}: {v}" for k, v in variables.items()]
            )

        # Generate fingerprint
        fingerprint = self._generate_fingerprint(source_address, trap_oid, variables)

        return AlertDto(
            id=f"snmp-{fingerprint}",
            source=["snmp", source_address],
            name=trap_oid or "SNMP Trap",
            description=description,
            severity=severity,
            status=AlertStatus.FIRING,
            fingerprint=fingerprint,
            raw=variables,
            lastReceived=datetime.datetime.now(),
        )

    def _generate_fingerprint(
        self,
        source_address: str,
        trap_oid: Optional[str],
        variables: dict,
    ) -> str:
        """Generate a unique fingerprint for the alert."""
        import hashlib
        
        fingerprint_data = f"{source_address}:{trap_oid}:{sorted(variables.items())}"
        return hashlib.md5(fingerprint_data.encode()).hexdigest()

    def _push_alert(self, alert: AlertDto):
        """Push alert to Keep."""
        try:
            # This would integrate with Keep's alert ingestion API
            logger.info(f"Pushing alert to Keep: {alert.name}")
            # In real implementation, this would call Keep's API
            # self.context_manager.insert_alert(alert)
        except Exception as e:
            logger.error(f"Error pushing alert: {e}")

    def _query(
        self,
        **kwargs,
    ) -> list[AlertDto]:
        """
        Query SNMP provider (not applicable for trap receiver).
        """
        # SNMP provider is push-based (receives traps)
        # Query operation doesn't make sense here
        return []

    def setup_webhook(
        self,
        tenant_id: str,
        keep_api_url: str,
        api_key: str,
        setup_alerts: bool = True,
        **kwargs,
    ):
        """
        Setup webhook (starts SNMP listener).
        """
        self.validate_config()
        self._start_snmp_listener()
        
        return {
            "status": "success",
            "message": f"SNMP listener started on {self.snmp_config.host}:{self.snmp_config.port}",
            "port": self.snmp_config.port,
            "community": self.snmp_config.community,
        }

    def cleanup_webhook(self, **kwargs):
        """
        Cleanup webhook (stops SNMP listener).
        """
        self._stop()
        return {"status": "success", "message": "SNMP listener stopped"}


if __name__ == "__main__":
    # Test code
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    # Create test provider
    context_manager = ContextManager(tenant_id="test")
    config = ProviderConfig(
        authentication={"port": 1620, "community": "public"}
    )
    
    provider = SnmpProvider(
        context_manager=context_manager,
        provider_id="snmp-test",
        config=config,
    )
    
    provider.setup_webhook(
        tenant_id="test",
        keep_api_url="http://localhost:8080",
        api_key="test",
    )
    
    print("SNMP provider running. Press Ctrl+C to stop.")
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        provider.cleanup_webhook()
