"""
SNMP Trap Provider receives SNMP traps (v1/v2c) and converts them to Keep alerts.

Push-based consumer: opens a UDP socket on a configurable port, decodes
incoming trap PDUs at the protocol level, and forwards them as Keep alerts.
No asyncio -- uses a blocking socket with a timeout-based polling loop so
the consumer thread can be stopped cleanly via the ``consume`` flag.
"""

import dataclasses
import datetime
import socket

import pydantic
from pyasn1.codec.ber import decoder as ber_decoder
from pysnmp.proto import api as snmp_api
from pysnmp.smi import builder as mib_builder_mod
from pysnmp.smi import view as mib_view_mod

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
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

# Standard SNMPv2 notification OIDs (from SNMPv2-MIB)
_V2_TRAP_OIDS = {
    "1.3.6.1.6.3.1.1.5.1": "coldStart",
    "1.3.6.1.6.3.1.1.5.2": "warmStart",
    "1.3.6.1.6.3.1.1.5.3": "linkDown",
    "1.3.6.1.6.3.1.1.5.4": "linkUp",
    "1.3.6.1.6.3.1.1.5.5": "authenticationFailure",
}

# Severity heuristics keyed by generic trap name
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
        self._socket = None
        self._mib_view = None
        self.err = ""

    def validate_config(self):
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict:
        scopes = {"receive_traps": False}
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(
                (
                    self.authentication_config.listen_address,
                    self.authentication_config.listen_port,
                )
            )
            scopes["receive_traps"] = True
        except OSError as exc:
            self.err = (
                f"Cannot bind to UDP port "
                f"{self.authentication_config.listen_port}: {exc}"
            )
            self.logger.warning(self.err)
            scopes["receive_traps"] = self.err
        finally:
            sock.close()
        return scopes

    def dispose(self):
        pass

    # ------------------------------------------------------------------
    # Alert formatting (webhook / simulate path)
    # ------------------------------------------------------------------

    SEVERITY_MAP_STR = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
    }

    STATUS_MAP_STR = {
        "firing": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
    }

    @staticmethod
    def _format_alert(
        event: dict | list[dict], provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        events = event if isinstance(event, list) else [event]
        alerts: list[AlertDto] = []
        for e in events:
            severity_raw = e.get("severity", "info")
            if isinstance(severity_raw, str):
                severity = SnmpProvider.SEVERITY_MAP_STR.get(
                    severity_raw.lower(), AlertSeverity.INFO
                )
            else:
                severity = severity_raw

            status_raw = e.get("status", "firing")
            if isinstance(status_raw, str):
                status = SnmpProvider.STATUS_MAP_STR.get(
                    status_raw.lower(), AlertStatus.FIRING
                )
            else:
                status = status_raw

            alerts.append(
                AlertDto(
                    id=e.get("id", e.get("name", "")),
                    name=e.get("name", "SNMP Trap"),
                    description=e.get("description"),
                    message=e.get("message"),
                    status=status,
                    severity=severity,
                    lastReceived=e.get(
                        "lastReceived",
                        datetime.datetime.now(
                            tz=datetime.timezone.utc
                        ).isoformat(),
                    ),
                    source=e.get("source", ["snmp"]),
                    service=e.get("service"),
                    labels=e.get("labels", {}),
                )
            )
        return alerts[0] if len(alerts) == 1 else alerts

    def status(self) -> dict:
        if self._socket is None:
            status = "not-initialized"
        elif self.consume:
            status = "listening"
        else:
            status = "stopped"
        return {"status": status, "error": self.err}

    # ------------------------------------------------------------------
    # Consumer lifecycle
    # ------------------------------------------------------------------

    def start_consume(self):
        self.consume = True
        self._init_mib_view()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1.0)
        try:
            sock.bind(
                (
                    self.authentication_config.listen_address,
                    self.authentication_config.listen_port,
                )
            )
        except OSError as exc:
            self.err = (
                f"Failed to bind SNMP trap socket on "
                f"{self.authentication_config.listen_address}:"
                f"{self.authentication_config.listen_port}: {exc}"
            )
            self.consume = False
            self.logger.exception(self.err)
            sock.close()
            return
        self._socket = sock

        self.logger.info(
            "SNMP trap receiver listening on %s:%d",
            self.authentication_config.listen_address,
            self.authentication_config.listen_port,
        )

        while self.consume:
            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                if not self.consume:
                    break
                self.logger.exception("Socket error in SNMP trap receiver")
                break

            if len(data) < 2:
                # Ignore wake-up / stray packets too small to be SNMP.
                continue

            try:
                alert = self._decode_trap(data, addr)
                if alert:
                    self._push_alert(alert)
            except Exception:
                self.logger.exception("Error processing SNMP trap from %s", addr[0])

        try:
            sock.close()
        except Exception:
            self.logger.debug("Error closing SNMP trap socket", exc_info=True)
        self._socket = None
        self.logger.info("SNMP trap receiver stopped")

    def stop_consume(self):
        self.consume = False
        if self._socket:
            # Send a dummy packet to unblock the recvfrom() call.
            # On Linux, closing a socket from another thread does not
            # reliably wake a blocking recvfrom.  A tiny UDP packet makes
            # the consumer loop iterate, see ``self.consume is False``,
            # and exit.
            try:
                addr = self.authentication_config.listen_address or "127.0.0.1"
                port = self.authentication_config.listen_port
                wake = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                wake.sendto(b"\x00", (addr, port))
                wake.close()
            except Exception:
                pass
            try:
                self._socket.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # MIB helpers
    # ------------------------------------------------------------------

    def _init_mib_view(self) -> None:
        """Load MIB modules for OID resolution. Falls back to raw OIDs."""
        try:
            mb = mib_builder_mod.MibBuilder()
            mb.loadModules("SNMPv2-MIB", "IF-MIB")
            self._mib_view = mib_view_mod.MibViewController(mb)
            self.logger.debug("MIB modules loaded for OID resolution")
        except Exception:
            self._mib_view = None
            self.logger.debug(
                "MIB modules not available, using raw OIDs", exc_info=True
            )

    def _resolve_oid(self, oid) -> str:
        """Resolve a numeric OID to a human-readable MIB name."""
        if self._mib_view is None:
            return str(oid)
        try:
            _mod_name, sym_name, suffix = self._mib_view.getNodeName(oid)
            suffix_str = ".".join(str(s) for s in suffix) if suffix else ""
            return f"{sym_name}.{suffix_str}" if suffix_str else str(sym_name)
        except Exception:
            return str(oid)

    # ------------------------------------------------------------------
    # Trap decoding
    # ------------------------------------------------------------------

    def _decode_trap(self, data: bytes, addr: tuple) -> dict | None:
        """Decode a raw SNMP trap datagram into a Keep alert dict.

        Supports SNMPv1 Trap-PDU and SNMPv2c SNMPv2-Trap-PDU formats.
        Returns ``None`` when the datagram is not a valid trap or the
        community string does not match the configured value.
        """
        try:
            msg_ver = int(snmp_api.decodeMessageVersion(data))
        except Exception:
            self.logger.debug("Cannot determine SNMP version from datagram")
            return None

        if msg_ver not in snmp_api.protoModules:
            self.logger.debug("Unsupported SNMP version: %d", msg_ver)
            return None

        p_mod = snmp_api.protoModules[msg_ver]
        try:
            msg, _ = ber_decoder.decode(data, asn1Spec=p_mod.Message())
        except Exception:
            self.logger.debug("BER decode failed for SNMP datagram")
            return None

        # Verify community string
        community = str(p_mod.apiMessage.getCommunity(msg))
        if community != self.authentication_config.community_string:
            self.logger.debug(
                "Ignoring trap with community '%s' from %s",
                community,
                addr[0],
            )
            return None

        req_pdu = p_mod.apiMessage.getPDU(msg)
        if req_pdu is None:
            return None

        # Route by SNMP version first -- p_mod.TrapPDU() maps to the
        # version-specific PDU class, so checking isSameTypeWith alone
        # would send v2c traps into the v1 handler.
        if msg_ver == snmp_api.protoVersion1:
            if not req_pdu.isSameTypeWith(p_mod.TrapPDU()):
                self.logger.debug(
                    "Ignoring non-trap SNMPv1 PDU from %s", addr[0]
                )
                return None
            return self._decode_v1_trap(p_mod, req_pdu, addr)

        # SNMPv2c: only process trap/inform PDUs, ignore GET/SET/RESPONSE
        snmpv2_trap_pdu = getattr(p_mod, "SNMPv2TrapPDU", None)
        inform_pdu = getattr(p_mod, "InformRequestPDU", None)
        is_trap = bool(
            (snmpv2_trap_pdu and req_pdu.isSameTypeWith(snmpv2_trap_pdu()))
            or (inform_pdu and req_pdu.isSameTypeWith(inform_pdu()))
        )
        if not is_trap:
            # Also check the generic TrapPDU for v2c compat
            if req_pdu.isSameTypeWith(p_mod.TrapPDU()):
                is_trap = True
        if not is_trap:
            self.logger.debug("Ignoring non-trap SNMP PDU from %s", addr[0])
            return None

        var_binds = p_mod.apiPDU.getVarBinds(req_pdu)
        return self._decode_v2c_trap(var_binds, addr[0])

    def _decode_v1_trap(self, p_mod, pdu, addr: tuple) -> dict:
        """Build an alert dict from an SNMPv1 Trap-PDU."""
        generic_trap = int(p_mod.apiTrapPDU.getGenericTrap(pdu))
        specific_trap = int(p_mod.apiTrapPDU.getSpecificTrap(pdu))
        enterprise = p_mod.apiTrapPDU.getEnterprise(pdu)
        agent_addr_raw = p_mod.apiTrapPDU.getAgentAddr(pdu)
        agent_addr = str(agent_addr_raw) if agent_addr_raw else addr[0]
        var_binds = p_mod.apiTrapPDU.getVarBinds(pdu)

        trap_name = _GENERIC_TRAP_NAMES.get(generic_trap, f"trap-{generic_trap}")
        if generic_trap == 6:
            trap_name = f"{enterprise}.{specific_trap}"

        severity = _SEVERITY_MAP.get(trap_name, AlertSeverity.WARNING)

        labels = {}
        description_parts = []
        for oid, val in var_binds:
            oid_str = self._resolve_oid(oid)
            val_str = val.prettyPrint() if val else ""
            labels[oid_str] = val_str
            description_parts.append(f"{oid_str} = {val_str}")

        description = "; ".join(description_parts) if description_parts else trap_name
        return {
            "name": trap_name,
            "description": description,
            "message": description,
            "status": AlertStatus.FIRING,
            "severity": severity,
            "lastReceived": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            "source": ["snmp"],
            "labels": labels,
            "service": agent_addr,
        }

    def _decode_v2c_trap(self, var_binds, source_addr: str) -> dict:
        """Build an alert dict from SNMPv2c trap varbinds."""
        trap_oid_raw = None
        labels = {}
        description_parts = []
        source_address = None

        for oid, val in var_binds:
            oid_str = self._resolve_oid(oid)
            val_str = val.prettyPrint() if val else ""

            # snmpTrapOID.0 (1.3.6.1.6.3.1.1.4.1.0)
            if "snmpTrapOID" in oid_str or str(oid) == "1.3.6.1.6.3.1.1.4.1.0":
                trap_oid_raw = val_str
                continue

            # snmpTrapAddress.0 (1.3.6.1.6.3.18.1.3.0)
            if "snmpTrapAddress" in oid_str or str(oid) == "1.3.6.1.6.3.18.1.3.0":
                source_address = val_str
                continue

            # sysUpTime.0 -- keep as metadata label, skip description
            if "sysUpTime" in oid_str or str(oid) == "1.3.6.1.2.1.1.3.0":
                labels["sysUpTime"] = val_str
                continue

            labels[oid_str] = val_str
            description_parts.append(f"{oid_str} = {val_str}")

        # Map the trap OID to a human-readable name
        trap_name = "snmpTrap"
        if trap_oid_raw:
            trap_name = _V2_TRAP_OIDS.get(trap_oid_raw, trap_oid_raw)

        severity = _SEVERITY_MAP.get(trap_name, AlertSeverity.WARNING)

        description = "; ".join(description_parts) if description_parts else trap_name
        return {
            "name": trap_name,
            "description": description,
            "message": description,
            "status": AlertStatus.FIRING,
            "severity": severity,
            "lastReceived": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            "source": ["snmp"],
            "labels": labels,
            "service": source_address or source_addr or "snmp-device",
        }
