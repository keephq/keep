"""
SNMP Trap Provider receives SNMP traps (v1/v2c/v3) and converts them to Keep alerts.

This is a push-based (consumer) provider -- it opens a UDP socket on a
configurable port and listens for incoming SNMP trap/inform PDUs.
"""

import asyncio
import dataclasses
import datetime

import pydantic
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import config as snmp_config
from pysnmp.entity import engine
from pysnmp.entity.rfc3413 import ntfrcv
from pysnmp.smi import view

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """SNMP Trap receiver configuration."""

    listen_port: int = dataclasses.field(
        default=162,
        metadata={
            "required": True,
            "description": "UDP port to listen for SNMP traps",
            "hint": "e.g. 162 (default) or 1162 (unprivileged)",
        },
    )
    listen_address: str = dataclasses.field(
        default="0.0.0.0",
        metadata={
            "required": False,
            "description": "IP address to bind to",
            "hint": "e.g. 0.0.0.0 (all interfaces)",
        },
    )
    community_string: str = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": "SNMPv1/v2c community string",
            "hint": "e.g. public",
            "sensitive": True,
        },
    )


# Well-known SNMP generic trap types (SNMPv1)
_GENERIC_TRAP_NAMES = {
    0: "coldStart",
    1: "warmStart",
    2: "linkDown",
    3: "linkUp",
    4: "authenticationFailure",
    5: "egpNeighborLoss",
    6: "enterpriseSpecific",
}

# Severity heuristics based on generic trap types and common OID patterns
_SEVERITY_MAP = {
    "coldStart": AlertSeverity.WARNING,
    "warmStart": AlertSeverity.INFO,
    "linkDown": AlertSeverity.HIGH,
    "linkUp": AlertSeverity.INFO,
    "authenticationFailure": AlertSeverity.WARNING,
    "egpNeighborLoss": AlertSeverity.HIGH,
}


class SnmpProvider(BaseProvider):
    """Receives SNMP traps and converts them to Keep alerts."""

    PROVIDER_DISPLAY_NAME = "SNMP Trap Receiver"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="receive_traps",
            description="Receive SNMP traps on the configured UDP port.",
            mandatory=True,
            alias="Receive Traps",
        )
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self.consume = False
        self._snmp_engine = None
        self._loop = None
        self._loop_thread = None
        self.err = ""

    def validate_config(self):
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict:
        scopes = {"receive_traps": False}
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(
                (
                    self.authentication_config.listen_address,
                    self.authentication_config.listen_port,
                )
            )
            sock.close()
            scopes["receive_traps"] = True
        except OSError as exc:
            self.err = f"Cannot bind to UDP port {self.authentication_config.listen_port}: {exc}"
            self.logger.warning(self.err)
            scopes["receive_traps"] = self.err
        return scopes

    def dispose(self):
        pass

    def status(self):
        if self._snmp_engine is None:
            status = "not-initialized"
        elif self.consume:
            status = "listening"
        else:
            status = "stopped"
        return {"status": status, "error": self.err}

    def start_consume(self):
        self.consume = True
        self._loop = asyncio.new_event_loop()
        try:
            self._snmp_engine = self._create_engine()
            self.logger.info(
                "SNMP trap receiver listening on %s:%d",
                self.authentication_config.listen_address,
                self.authentication_config.listen_port,
            )
            self._loop.run_forever()
        except Exception:
            self.logger.exception("SNMP trap receiver failed to start")
        finally:
            self._cleanup()
            self.logger.info("SNMP trap receiver stopped")

    def stop_consume(self):
        self.consume = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _create_engine(self):
        snmp_eng = engine.SnmpEngine()

        # Load MIB modules for OID resolution
        mib_builder = snmp_eng.getMibBuilder()
        mib_builder.loadModules("SNMPv2-MIB", "IF-MIB")
        self._mib_view = view.MibViewController(mib_builder)

        # Transport -- UDP/IPv4
        snmp_config.addTransport(
            snmp_eng,
            udp.domainName,
            udp.UdpTransport().openServerMode(
                (
                    self.authentication_config.listen_address,
                    self.authentication_config.listen_port,
                )
            ),
        )

        # SNMPv1/v2c community
        snmp_config.addV1System(
            snmp_eng,
            "keep-area",
            self.authentication_config.community_string,
        )

        # Register callback for incoming notifications
        ntfrcv.NotificationReceiver(snmp_eng, self._trap_callback)

        return snmp_eng

    def _trap_callback(
        self,
        snmp_engine,
        state_reference,
        context_engine_id,
        context_name,
        var_binds,
        cb_ctx,
    ):
        """Called by pysnmp for every incoming trap/inform."""
        try:
            alert = self._varbinds_to_alert(var_binds)
            self._push_alert(alert)
        except Exception:
            self.logger.exception("Error processing SNMP trap")

    def _resolve_oid(self, oid):
        """Resolve a numeric OID to a human-readable MIB name."""
        try:
            mod_name, sym_name, suffix = self._mib_view.getNodeName(oid)
            suffix_str = ".".join(str(s) for s in suffix) if suffix else ""
            resolved = f"{sym_name}.{suffix_str}" if suffix_str else str(sym_name)
            return resolved
        except Exception:
            return str(oid)

    def _varbinds_to_alert(self, var_binds):
        """Convert SNMP varbind list to a Keep alert dictionary."""
        trap_oid = None
        description_parts = []
        labels = {}
        source_address = None

        for oid, val in var_binds:
            oid_str = self._resolve_oid(oid)
            val_str = val.prettyPrint() if val else ""

            # Capture the trap OID (snmpTrapOID.0)
            if "snmpTrapOID" in oid_str or str(oid) == "1.3.6.1.6.3.1.1.4.1.0":
                trap_oid = self._resolve_oid(val)
                continue

            # Capture source address if present
            if "snmpTrapAddress" in oid_str:
                source_address = val_str
                continue

            labels[oid_str] = val_str
            description_parts.append(f"{oid_str} = {val_str}")

        trap_name = trap_oid or "snmpTrap"
        severity = _SEVERITY_MAP.get(trap_name, AlertSeverity.WARNING)

        alert = {
            "name": trap_name,
            "description": (
                "; ".join(description_parts) if description_parts else trap_name
            ),
            "status": AlertStatus.FIRING,
            "severity": severity,
            "lastReceived": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            "source": ["snmp"],
            "labels": labels,
            "service": source_address or "snmp-device",
        }
        return alert

    def _cleanup(self):
        if self._snmp_engine:
            try:
                self._snmp_engine.transportDispatcher.closeDispatcher()
            except Exception:
                self.logger.debug("Error closing SNMP transport", exc_info=True)
            self._snmp_engine = None
        if self._loop:
            try:
                self._loop.close()
            except Exception:
                pass
            self._loop = None
