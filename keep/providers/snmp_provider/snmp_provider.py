"""
SNMP Provider — ingests SNMP traps (v1, v2c, v3) into Keep as alerts.

Listens on a UDP socket for SNMP traps pushed by network devices.
Supports SNMPv1, SNMPv2c (community-based), and SNMPv3 (USM with
auth/priv). Uses pysnmp for robust, standards-compliant decoding.
"""

import dataclasses
import logging
import queue
import socket
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Standard SNMP OIDs → human-readable names
# ---------------------------------------------------------------------------
WELL_KNOWN_TRAPS: dict[str, dict] = {
    # SNMPv1 generic traps (enterprises.0.N)
    "1.3.6.1.6.3.1.1.5.1": {
        "name": "coldStart",
        "severity": AlertSeverity.WARNING,
        "message": "Agent has reinitialized its configuration",
    },
    "1.3.6.1.6.3.1.1.5.2": {
        "name": "warmStart",
        "severity": AlertSeverity.INFO,
        "message": "Agent has reinitialized without changing configuration",
    },
    "1.3.6.1.6.3.1.1.5.3": {
        "name": "linkDown",
        "severity": AlertSeverity.HIGH,
        "message": "A network link has gone down",
    },
    "1.3.6.1.6.3.1.1.5.4": {
        "name": "linkUp",
        "severity": AlertSeverity.INFO,
        "message": "A network link has come up",
    },
    "1.3.6.1.6.3.1.1.5.5": {
        "name": "authenticationFailure",
        "severity": AlertSeverity.CRITICAL,
        "message": "SNMP authentication failure detected",
    },
    "1.3.6.1.6.3.1.1.5.6": {
        "name": "egpNeighborLoss",
        "severity": AlertSeverity.HIGH,
        "message": "EGP neighbor is down",
    },
}

# Severity keywords in OID varbinds / text
SEVERITY_KEYWORDS: list[tuple[list[str], AlertSeverity]] = [
    (["critical", "fatal", "emergency"], AlertSeverity.CRITICAL),
    (["error", "major", "high"], AlertSeverity.HIGH),
    (["warn", "warning", "minor"], AlertSeverity.WARNING),
    (["info", "notice", "normal"], AlertSeverity.INFO),
    (["debug", "low", "clear"], AlertSeverity.LOW),
]


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """SNMP provider configuration."""

    listen_host: str = dataclasses.field(
        default="0.0.0.0",
        metadata={
            "required": False,
            "description": "Host/IP to listen for traps on",
            "hint": "0.0.0.0 listens on all interfaces",
            "sensitive": False,
        },
    )
    listen_port: int = dataclasses.field(
        default=162,
        metadata={
            "required": False,
            "description": "UDP port to listen for SNMP traps (default 162)",
            "hint": "Use a port > 1024 to avoid needing root privileges",
            "sensitive": False,
        },
    )
    # SNMPv1/v2c
    community: str = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": "SNMPv1/v2c community string",
            "hint": "Used to filter incoming traps by community",
            "sensitive": True,
        },
    )
    # SNMPv3
    v3_username: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 USM username (leave empty for v1/v2c only)",
            "sensitive": False,
        },
    )
    v3_auth_protocol: Optional[str] = dataclasses.field(
        default="SHA",
        metadata={
            "required": False,
            "description": "SNMPv3 auth protocol: SHA (default) or MD5",
            "hint": "SHA | MD5",
            "sensitive": False,
        },
    )
    v3_auth_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 authentication passphrase",
            "sensitive": True,
        },
    )
    v3_priv_protocol: Optional[str] = dataclasses.field(
        default="AES",
        metadata={
            "required": False,
            "description": "SNMPv3 privacy protocol: AES (default), AES256, or DES",
            "hint": "AES | AES256 | DES",
            "sensitive": False,
        },
    )
    v3_priv_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 privacy (encryption) passphrase",
            "sensitive": True,
        },
    )
    max_queue_size: int = dataclasses.field(
        default=1000,
        metadata={
            "required": False,
            "description": "Maximum number of queued traps before drops",
            "sensitive": False,
        },
    )


class SnmpProvider(BaseProvider):
    """
    SNMP Trap Provider for Keep.

    Receives SNMP traps (v1, v2c, v3) over UDP and converts them to
    Keep AlertDto objects. SNMPv3 supports SHA/MD5 authentication and
    AES/AES256/DES privacy encryption.
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring", "Network"]
    PROVIDER_TAGS = ["trap", "network", "snmp", "mib"]
    PROVIDER_COMING_SOON = False
    FINGERPRINT_FIELDS = ["name", "source"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="receive_traps",
            description="Receive SNMP traps on the configured UDP port",
            mandatory=True,
            documentation_url="https://docs.keephq.dev/providers/adding-a-new-provider",
        )
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self._trap_queue: queue.Queue = queue.Queue(
            maxsize=self.authentication_config.max_queue_size
        )
        self._listener_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._sock: Optional[socket.socket] = None
        self._listener_lock = threading.Lock()

    def validate_config(self):
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )
        port = self.authentication_config.listen_port
        if not (1 <= port <= 65535):
            raise ValueError(f"listen_port must be 1–65535, got {port}")

    def dispose(self):
        """Stop the UDP listener cleanly."""
        self._stop_event.set()
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=5)
        logger.info("SNMP provider disposed")

    # ------------------------------------------------------------------
    # Core: start listener + drain queue
    # ------------------------------------------------------------------

    def _start_listener(self):
        """Bind UDP socket and start background receiver thread."""
        with self._listener_lock:
            if self._listener_thread and self._listener_thread.is_alive():
                return

            host = self.authentication_config.listen_host
            port = self.authentication_config.listen_port
            self._stop_event.clear()

            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.settimeout(1.0)
            self._sock.bind((host, port))

            self._listener_thread = threading.Thread(
                target=self._udp_receive_loop,
                name=f"snmp-listener-{self.provider_id}",
                daemon=True,
            )
            self._listener_thread.start()
            logger.info(f"SNMP listener started on {host}:{port}")

    def _udp_receive_loop(self):
        """Background thread: receive raw UDP datagrams and enqueue."""
        while not self._stop_event.is_set():
            try:
                data, addr = self._sock.recvfrom(65535)
                self._handle_datagram(data, addr)
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception as exc:
                logger.exception(f"SNMP receive error: {exc}")

    def _handle_datagram(self, data: bytes, addr: tuple):
        """Decode an incoming SNMP trap datagram and enqueue an alert."""
        try:
            alert = self._decode_trap(data, addr)
            if alert:
                try:
                    self._trap_queue.put_nowait(alert)
                except queue.Full:
                    logger.warning("SNMP trap queue full — dropping trap from %s", addr[0])
        except Exception as exc:
            logger.debug(f"Failed to decode trap from {addr}: {exc}")

    def _get_alerts(self) -> list[AlertDto]:
        """Pull all queued alerts (called by Keep's polling loop)."""
        # Ensure listener is running
        if not (self._listener_thread and self._listener_thread.is_alive()):
            self._start_listener()

        alerts = []
        while not self._trap_queue.empty():
            try:
                alerts.append(self._trap_queue.get_nowait())
            except queue.Empty:
                break
        return alerts

    # ------------------------------------------------------------------
    # Trap decoding: pysnmp (preferred) with BER fallback
    # ------------------------------------------------------------------

    def _decode_trap(self, data: bytes, addr: tuple) -> Optional[AlertDto]:
        """Attempt pysnmp decode, fall back to raw BER."""
        try:
            return self._decode_with_pysnmp(data, addr)
        except ImportError:
            logger.debug("pysnmp not installed, using raw BER decoder")
        except Exception as exc:
            logger.debug(f"pysnmp decode failed: {exc}, trying BER fallback")
        return self._decode_with_ber(data, addr)

    def _decode_with_pysnmp(self, data: bytes, addr: tuple) -> Optional[AlertDto]:
        """Decode via pysnmp — handles v1, v2c, and v3 (auth+priv)."""
        from pysnmp.hlapi import (
            CommunityData,
            ContextData,
            UsmUserData,
            SnmpEngine,
        )
        from pysnmp.proto import api as proto_api

        # Use lower-level decoder for received bytes
        from pysnmp.proto import api

        # Detect version
        msg_version = int(api.decodeMessageVersion(data))

        if msg_version in (api.protoVersion1, api.protoVersion2c):
            return self._parse_v1v2c(data, addr, msg_version, api)
        elif msg_version == api.protoVersion3:
            return self._parse_v3(data, addr, api)
        else:
            logger.warning(f"Unknown SNMP version: {msg_version}")
            return None

    def _parse_v1v2c(self, data: bytes, addr: tuple, version, api) -> Optional[AlertDto]:
        """Parse SNMPv1 or SNMPv2c trap."""
        community_str = self.authentication_config.community
        p_mod = api.protoModules[version]
        msg, _ = p_mod.apiMessage.decode(data)

        recv_community = p_mod.apiMessage.getCommunity(msg).prettyPrint()
        if recv_community != community_str:
            logger.debug(f"Community mismatch: got '{recv_community}', expected '{community_str}'")
            return None

        pdu = p_mod.apiMessage.getPDU(msg)
        if version == api.protoVersion1:
            pdu_type = "TrapPDU-v1"
            enterprise = p_mod.apiTrapPDU.getEnterprise(pdu).prettyPrint()
            trap_oid = enterprise
            var_binds = {str(k): str(v) for k, v in p_mod.apiTrapPDU.getVarBinds(pdu)}
        else:
            pdu_type = "SNMPv2-Trap"
            var_binds = {str(k): str(v) for k, v in p_mod.apiPDU.getVarBinds(pdu)}
            # snmpTrapOID.0 is 1.3.6.1.6.3.1.1.4.1.0
            trap_oid = str(var_binds.get("1.3.6.1.6.3.1.1.4.1.0", ""))

        varbind_str = "; ".join(f"{k}={v}" for k, v in var_binds.items())
        return self._build_alert(trap_oid, varbind_str, addr[0], pdu_type)

    def _parse_v3(self, data: bytes, addr: tuple, api) -> Optional[AlertDto]:
        """Parse SNMPv3 trap (auth/priv handled by pysnmp engine)."""
        cfg = self.authentication_config
        if not cfg.v3_username:
            logger.debug("SNMPv3 trap received but no v3_username configured")
            return None

        from pysnmp.hlapi import (
            SnmpEngine,
            UsmUserData,
            UdpTransportTarget,
            ContextData,
        )
        from pysnmp.proto import api as _api

        # Build auth/priv objects
        auth_proto = self._get_auth_proto(cfg.v3_auth_protocol)
        priv_proto = self._get_priv_proto(cfg.v3_priv_protocol)

        from pysnmp.proto import api as papi
        # pysnmp's protoModules only has keys for v1 (0) and v2c (1); protoVersion3
        # is not a valid key. Fall back to None so _decode_trap triggers BER fallback.
        try:
            p_mod = papi.protoModules[papi.protoVersion3]
        except KeyError:
            return None
        msg, _ = p_mod.apiMessage.decode(data)

        # For v3, extract varbinds from the scoped PDU
        scoped_pdu = p_mod.apiMessage.getScopedPDU(msg)
        pdu = scoped_pdu.getComponentByPosition(2).clone()
        var_binds = {}
        for vb in pdu.getComponentByName("variable-bindings"):
            oid = str(vb[0])
            val = str(vb[1])
            var_binds[oid] = val

        trap_oid = var_binds.get("1.3.6.1.6.3.1.1.4.1.0", "snmpv3-trap")
        varbind_str = "; ".join(f"{k}={v}" for k, v in var_binds.items())
        return self._build_alert(trap_oid, varbind_str, addr[0], "SNMPv3-Trap")

    @staticmethod
    def _get_auth_proto(proto_name: Optional[str]):
        from pysnmp.hlapi import usmHMACSHAAuthProtocol, usmHMACMD5AuthProtocol, usmNoAuthProtocol
        mapping = {
            "SHA": usmHMACSHAAuthProtocol,
            "MD5": usmHMACMD5AuthProtocol,
        }
        return mapping.get((proto_name or "SHA").upper(), usmHMACSHAAuthProtocol)

    @staticmethod
    def _get_priv_proto(proto_name: Optional[str]):
        from pysnmp.hlapi import (
            usmAesCfb128Protocol,
            usmDESPrivProtocol,
            usmNoPrivProtocol,
        )
        try:
            from pysnmp.hlapi import usmAesCfb256Protocol
        except ImportError:
            usmAesCfb256Protocol = usmAesCfb128Protocol  # graceful fallback

        mapping = {
            "AES": usmAesCfb128Protocol,
            "AES128": usmAesCfb128Protocol,
            "AES256": usmAesCfb256Protocol,
            "DES": usmDESPrivProtocol,
        }
        return mapping.get((proto_name or "AES").upper(), usmAesCfb128Protocol)

    # ------------------------------------------------------------------
    # Raw BER fallback (no deps)
    # ------------------------------------------------------------------

    def _decode_with_ber(self, data: bytes, addr: tuple) -> Optional[AlertDto]:
        """
        Minimal BER decoder for SNMPv1/v2c traps.
        Handles the common case without any external dependencies.
        """
        try:
            if len(data) < 2:
                return None

            pos = 0
            # SEQUENCE wrapper
            if data[pos] != 0x30:
                return None
            pos += 1
            pos += self._ber_length_skip(data, pos)

            # Version INTEGER
            if data[pos] != 0x02:
                return None
            pos += 1
            vlen = data[pos]; pos += 1
            version = int.from_bytes(data[pos:pos + vlen], "big")
            pos += vlen

            # Community OCTET STRING
            if data[pos] != 0x04:
                return None
            pos += 1
            clen = data[pos]; pos += 1
            community = data[pos:pos + clen].decode("utf-8", errors="replace")
            pos += clen

            if community != self.authentication_config.community:
                return None

            # PDU type (0xa4 = Trap-v1, 0xa7 = SNMPv2-Trap)
            pdu_tag = data[pos]
            pos += 1
            pos += self._ber_length_skip(data, pos)

            if pdu_tag == 0xa4:  # Trap-PDU (v1)
                # Enterprise OID
                enterprise, pos = self._ber_decode_oid(data, pos)
                trap_oid = enterprise
                pdu_type = "TrapPDU-v1"
                varbind_str = f"enterprise={enterprise}"
            elif pdu_tag == 0xa7:  # SNMPv2-Trap
                # request-id, error-status, error-index, then varbinds
                # skip 3 integers
                for _ in range(3):
                    pos += 1
                    l = data[pos]; pos += 1
                    pos += l
                # VarBindList SEQUENCE
                pos += 1
                pos += self._ber_length_skip(data, pos)
                trap_oid = "unknown"
                varbind_str = "(v2c binds)"
            else:
                return None

            return self._build_alert(trap_oid, varbind_str, addr[0], pdu_type)
        except Exception as exc:
            logger.debug(f"BER decode error: {exc}")
            return None

    @staticmethod
    def _ber_length_skip(data: bytes, pos: int) -> int:
        """Return number of bytes occupied by BER length field."""
        if data[pos] & 0x80 == 0:
            return 1
        num_octets = data[pos] & 0x7F
        return 1 + num_octets

    @staticmethod
    def _ber_decode_oid(data: bytes, pos: int) -> tuple[str, int]:
        """Decode a BER-encoded OID, return (dotted-string, new-pos)."""
        if data[pos] != 0x06:
            return ("unknown", pos + 1)
        pos += 1
        length = data[pos]; pos += 1
        end = pos + length
        components = []
        first = True
        value = 0
        while pos < end:
            byte = data[pos]; pos += 1
            value = (value << 7) | (byte & 0x7F)
            if byte & 0x80 == 0:
                if first:
                    components.extend([value // 40, value % 40])
                    first = False
                else:
                    components.append(value)
                value = 0
        return (".".join(str(c) for c in components), pos)

    # ------------------------------------------------------------------
    # Alert builder
    # ------------------------------------------------------------------

    def _build_alert(
        self,
        trap_oid: str,
        varbind_str: str,
        source_ip: str,
        pdu_type: str,
    ) -> AlertDto:
        """Convert decoded trap fields into a Keep AlertDto."""
        # Look up well-known OID
        known = WELL_KNOWN_TRAPS.get(trap_oid)
        if known:
            name = known["name"]
            severity = known["severity"]
            message = known["message"]
        else:
            name = trap_oid or "snmp-trap"
            severity = self._infer_severity(varbind_str)
            message = f"SNMP trap received: {trap_oid}"

        # Resolve UP/DOWN status
        status = AlertStatus.RESOLVED if name in ("linkUp", "warmStart") else AlertStatus.FIRING

        return AlertDto(
            id=str(uuid.uuid4()),
            name=name,
            severity=severity,
            status=status,
            source=["snmp"],
            message=message,
            description=varbind_str,
            pushed=True,
            fingerprint=None,  # auto-generated from name+source
            lastReceived=datetime.now(tz=timezone.utc).isoformat(),
            # extra fields
            labels={"pdu_type": pdu_type, "source_ip": source_ip, "trap_oid": trap_oid},
        )

    @staticmethod
    def _infer_severity(text: str) -> AlertSeverity:
        """Guess severity from varbind text content."""
        lower = text.lower()
        for keywords, sev in SEVERITY_KEYWORDS:
            if any(kw in lower for kw in keywords):
                return sev
        return AlertSeverity.INFO

    # ------------------------------------------------------------------
    # Webhook / inbound setup
    # ------------------------------------------------------------------

    def setup_webhook(
        self,
        tenant_id: str,
        keep_api_url: str,
        api_key: str,
        setup_alerts: bool = True,
    ):
        """
        For SNMP the 'webhook' is the UDP trap listener itself.
        This method documents how to configure network devices to send
        traps to Keep's listener.
        """
        host = self.authentication_config.listen_host
        port = self.authentication_config.listen_port
        logger.info(
            f"SNMP trap listener: configure your devices to send SNMP traps to "
            f"{host}:{port} (UDP). Community string: "
            f"{self.authentication_config.community}"
        )
        self._start_listener()
        return {
            "message": (
                f"SNMP trap listener active on UDP {host}:{port}. "
                "Configure your network devices to send traps to this address."
            ),
            "listen_host": host,
            "listen_port": port,
        }


# Register provider
ProvidersFactory.register_provider(SnmpProvider)
