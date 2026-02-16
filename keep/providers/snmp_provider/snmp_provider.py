import asyncio
import logging
import time
from dataclasses import dataclass

from pysnmp.entity import engine, config
from pysnmp.entity.rfc3413 import ntfrcv
from pysnmp.carrier.asyncio.dgram import udp

# Correct imports based on Keep's base structure
from keep.providers.base.base_provider import BaseProvider
from keep.api.models.alert import AlertDto, AlertSeverity
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@dataclass
class SnmpProviderAuthConfig:
    """
    Configuration for the SNMP provider.
    These fields will show up as a form in the Keep UI.
    """
    port: int = 162
    community: str = "public"
    denoise_window: int = 10


class SnmpProvider(BaseProvider):
    """Native SNMP Trap Listener with Signal Denoising."""

    # --- UI & Discovery Metadata ---
    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert", "infrastructure", "network"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_DESCRIPTION = "Native SNMP Trap Listener with Signal Denoising logic to prevent alert fatigue."
    PROVIDER_SCOPES = []
    PROVIDER_COMING_SOON = False
    WEBHOOK_INSTALLATION_REQUIRED = False

    def __init__(self, context_manager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

        # Pull directly from the config dictionary to avoid property attribute errors
        auth = self.config.authentication if self.config.authentication else {}
        self.port = int(auth.get("port", 162))
        self.community = auth.get("community", "public")
        self.denoise_window = int(auth.get("denoise_window", 10))

        self.snmp_engine = engine.SnmpEngine()
        self._trap_cache = {}

    def validate_config(self):
        """Validates the provider configuration."""
        return True

    def setup_provider(self):
        """Starts the native UDP listener as a background task."""
        self.logger.info(f"Setting up Native SNMP Listener on port {self.port}")
        loop = asyncio.get_event_loop()
        loop.create_task(self._start_snmp_listener())

    async def _start_snmp_listener(self):
        """Standalone Native Async UDP Server."""
        try:
            config.addTransport(
                self.snmp_engine,
                udp.domainName,
                udp.UdpTransport().openServerMode(("0.0.0.0", self.port))
            )
            config.addV1System(self.snmp_engine, "keep-area", self.community)
            ntfrcv.NotificationReceiver(self.snmp_engine, self._process_trap)

            self.logger.info(f"✅ Native SNMP Listener active on UDP Port {self.port}")
            while True:
                await asyncio.sleep(1)
        except Exception as e:
            self.logger.error(f"Failed to start SNMP listener: {e}")

    def _process_trap(self, snmpEngine, stateReference, contextEngineId, contextName, varBinds, cbCtx):
        """Processes trap with sliding-window denoising."""
        try:
            transport_info = snmpEngine.msgAndPduDsp.getTransportInfo(stateReference)
            source_ip = transport_info[1][0]

            trap_oid = str(varBinds[1][1]) if len(varBinds) > 1 else "unknown"

            # --- SIGNAL DENOISING ---
            cache_key = (source_ip, trap_oid)
            current_time = time.time()
            if cache_key in self._trap_cache:
                if (current_time - self._trap_cache[cache_key]) < self.denoise_window:
                    self.logger.info(f"🔇 Denoising: Dropped rapid-fire trap {trap_oid} from {source_ip}")
                    return
            self._trap_cache[cache_key] = current_time

            # --- SEVERITY MAPPING ---
            severity = AlertSeverity.INFO
            if "1.3.6.1.6.3.1.1.5.3" in trap_oid:  # linkDown
                severity = AlertSeverity.CRITICAL
            elif "1.3.6.1.6.3.1.1.5.4" in trap_oid:  # linkUp
                severity = AlertSeverity.LOW

            # --- DISPATCH ALERT ---
            alert = AlertDto(
                id=f"snmp-{trap_oid}-{int(current_time)}",
                name=f"SNMP Trap: {trap_oid}",
                status="firing",
                severity=severity,
                lastReceived=str(int(current_time)),
                environment="production",
                service=source_ip,
                source=["snmp"],
                description=f"Native SNMP Trap received from {source_ip}",
                payload={str(k): str(v) for k, v in varBinds}
            )

            # Use Keep's internal event manager to push
            self.context_manager.event_manager.push_event(alert)
            self.logger.info(f"🚀 SNMP Alert Dispatched: {trap_oid} from {source_ip}")
            return alert

        except Exception as e:
            self.logger.error(f"Error in SNMP handler: {e}")

    # --- ADDED THESE TO COMPLY WITH BASEPROVIDER ABSTRACT METHODS ---

    def dispose(self):
        """
        Required by BaseProvider.
        Cleans up the SNMP engine resources.
        """
        try:
            self.snmp_engine.transportDispatcher.closeDispatcher()
            self.logger.info("SNMP Listener resources disposed.")
        except Exception:
            pass

    def _query(self, **kwargs):
        """
        Required by BaseProvider.
        SNMP is a push-based listener, so query is not supported for this provider.
        """
        raise NotImplementedError("SNMP provider does not support manual querying.")