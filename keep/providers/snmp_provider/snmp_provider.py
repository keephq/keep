"""
Snmp Provider is a class that allows to receive SNMP v1/v2c traps as Keep alerts.
"""

import dataclasses
import datetime
import logging
import os

import pydantic

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

from pysnmp.carrier.asynsock.dgram import udp
from pysnmp.entity import config as snmp_config
from pysnmp.entity.rfc3413 import ntfrcv

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """SNMP provider authentication configuration."""

    listen_address: str = dataclasses.field(
        default="0.0.0.0",
        metadata={
            "required": False,
            "description": "IP address to listen for SNMP traps",
            "sensitive": False,
            "hint": "Use 0.0.0.0 to listen on all interfaces",
        },
    )
    listen_port: int = dataclasses.field(
        default=1162,
        metadata={
            "required": False,
            "description": "UDP port to listen for SNMP traps (default: 1162; use 162 in production with correct privileges)",
            "sensitive": False,
            "hint": "Port 162 requires root or CAP_NET_BIND_SERVICE. Use 1162 for development.",
        },
    )
    community_string: str = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": "SNMP v1/v2c community string",
            "sensitive": True,
            "hint": "Must match the community string configured on your network devices",
        },
    )


class SnmpProvider(BaseProvider):
    """Receive SNMP v1/v2c traps as Keep alerts."""

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring", "Cloud Infrastructure"]
    PROVIDER_TAGS = ["alert"]
    PROVIDER_DESCRIPTION = (
        "Receive SNMP v1/v2c traps from network devices "
        "(routers, switches, servers, firewalls) as Keep alerts."
    )
    FINGERPRINT_FIELDS = ["trap_oid", "source_address"]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        # Consumer state flags.
        # Keep manages threading internally via start_consume().
        # Do NOT create threads manually.
        self.consume = False
        self._snmp_engine = None
        self.err = ""

    def validate_config(self):
        """Validate SNMP provider configuration."""
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """Dispose the SNMP provider and stop listener if running."""
        self.consume = False
        self._cleanup_engine()

    def status(self) -> dict:
        """Return current consumer status."""
        return {
            "status": "running" if self.consume else "stopped",
            "error": self.err,
        }

    def start_consume(self):
        """
        Start consuming SNMP traps.

        Consumer pattern (Kafka-style).
        Keep manages threading internally via start_consume().
        Do NOT create threads manually here.

        Binds a UDP socket on the configured address and port,
        processes incoming SNMPv1/v2c traps, and pushes each
        as a Keep alert via self._push_alert().
        """
        self.consume = True

        self.logger.info(
            "Starting SNMP trap listener",
            extra={
                "provider_id": self.provider_id,
                "address": self.authentication_config.listen_address,
                "port": self.authentication_config.listen_port,
            },
        )

        try:
            from pysnmp.entity.engine import SnmpEngine

            snmp_engine = SnmpEngine()
            self._snmp_engine = snmp_engine

            listen_address = self.authentication_config.listen_address
            listen_port = self.authentication_config.listen_port

            # Configure UDP transport
            snmp_config.addTransport(
                snmp_engine,
                udp.domainName,
                udp.UdpTransport().openServerMode(
                    (listen_address, listen_port)
                ),
            )

            # Register SNMPv1/v2c community string
            snmp_config.addV1System(
                snmp_engine,
                "keep-snmp-area",
                self.authentication_config.community_string,
            )

            # Register trap receiver callback
            ntfrcv.NotificationReceiver(snmp_engine, self._trap_callback)

            # Signal dispatcher that work is pending
            snmp_engine.transportDispatcher.jobStarted(1)

            self.logger.info(
                "SNMP trap listener active",
                extra={
                    "provider_id": self.provider_id,
                    "port": listen_port,
                },
            )

            # Blocking dispatcher — runs until closeDispatcher() is called
            # or an unhandled exception occurs.
            snmp_engine.transportDispatcher.runDispatcher()

        except Exception:
            self.logger.exception(
                "SNMP trap listener encountered an error",
                extra={"provider_id": self.provider_id},
            )
            self.err = "SNMP listener stopped unexpectedly"
        finally:
            self._cleanup_engine()

        self.logger.info(
            "SNMP trap listener stopped",
            extra={"provider_id": self.provider_id},
        )

    def stop_consume(self):
        """Stop the SNMP trap listener cleanly."""
        self.consume = False
        self._cleanup_engine()

    def _cleanup_engine(self):
        """Clean up SNMP engine and transport safely."""
        if self._snmp_engine is not None:
            try:
                self._snmp_engine.transportDispatcher.closeDispatcher()
            except Exception:
                self.logger.warning(
                    "Error closing SNMP dispatcher during cleanup",
                    extra={"provider_id": self.provider_id},
                )
            self._snmp_engine = None

    def _trap_callback(
        self,
        snmp_engine,
        state_reference,
        context_engine_id,
        context_name,
        var_binds,
        cb_ctx,
    ):
        """
        Invoked by pysnmp for each received SNMP trap.
        Parses var_binds and pushes alert to Keep via _push_alert().
        """
        try:
            self.logger.info(
                "SNMP trap received",
                extra={"provider_id": self.provider_id},
            )

            # Use original parsing contract (DO NOT CHANGE SIGNATURE)
            alert = self._parse_trap(var_binds, snmp_engine, state_reference)

            # Safe push (avoid failing when KEEP_API_URL is not set)
            if os.getenv("KEEP_API_URL"):
                self._push_alert(alert)
            else:
                self.logger.info(
                    "Skipping push_alert (KEEP_API_URL not set)",
                    extra={
                        "provider_id": self.provider_id,
                        "trap_oid": alert.get("trap_oid"),
                        "source_address": alert.get("source_address"),
                    },
                )

        except Exception:
            self.logger.exception(
                "Error processing SNMP trap",
                extra={"provider_id": self.provider_id},
            )

    def _parse_trap(
        self,
        var_binds: list,
        snmp_engine,
        state_reference,
    ) -> dict:
        """
        Parse pysnmp var_binds into a dict compatible with _push_alert().

        OIDs are stored as numeric strings.
        MIB resolution is out of scope for this version.

        Args:
            var_binds: List of (OID, value) tuples from pysnmp callback.
            snmp_engine: The active pysnmp SnmpEngine instance.
            state_reference: Transport state reference for source IP extraction.

        Returns:
            dict: Alert-compatible dict for _push_alert().
        """
        # Extract source IP address from transport info
        try:
            transport_domain, transport_address = (
                snmp_engine.msgAndPduDsp.getTransportInfo(state_reference)
            )
            source_address = (
                str(transport_address[0]) if transport_address else "unknown"
            )
        except Exception:
            source_address = "unknown"

        # Build OID-to-value map. OIDs kept as numeric strings.
        # MIB-based name resolution is future work.
        oid_values = {}
        trap_oid = "unknown"

        for oid, val in var_binds:
            oid_str = str(oid)
            val_str = str(val)
            oid_values[oid_str] = val_str
            # snmpTrapOID.0 per RFC 3416 — identifies the trap type
            if oid_str == "1.3.6.1.6.3.1.1.4.1.0":
                trap_oid = val_str

        # Severity is INFO for all traps in this version.
        # Per-trap-type severity mapping is future work.
        severity = AlertSeverity.INFO

        name = f"SNMP Trap: {trap_oid}"
        description = (
            f"SNMP trap received from {source_address} — OID: {trap_oid}"
        )

        # Build stable unique ID for deduplication
        timestamp = datetime.datetime.now(tz=datetime.timezone.utc)
        alert_id = (
            f"snmp-{trap_oid}-{source_address}-{timestamp.timestamp()}"
        )

        return {
            "id": alert_id,
            "name": name,
            "source": ["snmp"],
            "description": description,
            # str() ensures string type matches _push_alert schema
            "severity": str(severity.value),
            "status": str(AlertStatus.FIRING.value),
            "lastReceived": timestamp.isoformat(),
            "environment": "production",
            "pushed": True,
            # Fingerprint fields — must match FINGERPRINT_FIELDS
            "trap_oid": trap_oid,
            "source_address": source_address,
            # Raw OID map for enrichment and debugging
            "oid_values": oid_values,
        }