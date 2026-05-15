"""
SNMP Provider — native UDP trap listener for SNMPv1, v2c, and v3.

Receives SNMP traps directly (no snmptrapd / HTTP forwarder required) and
pushes them into Keep's alert pipeline via ``_push_alert``.
"""

import dataclasses
import datetime
import hashlib
import logging
from typing import Optional

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.snmp_provider.snmp_provider_constants import (
    IF_INDEX_OID_PREFIX,
    LINK_DOWN_TRAP_OID,
    LINK_UP_TRAP_OID,
    SNMP_TRAP_OID_TO_NAME,
    SNMP_TRAP_OID_TO_SEVERITY,
    SNMP_TRAP_OID_VARBIND,
    SNMPV1_GENERIC_TRAP_TO_NAME,
    SNMPV1_GENERIC_TRAP_TO_SEVERITY,
    SYS_UPTIME_OID,
)

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """SNMP Provider authentication / listener configuration."""

    snmp_version: str = dataclasses.field(
        default="v2c",
        metadata={
            "required": False,
            "description": "SNMP version to use",
            "hint": "v1, v2c, or v3",
            "type": "select",
            "options": ["v1", "v2c", "v3"],
        },
    )

    listen_address: str = dataclasses.field(
        default="0.0.0.0",
        metadata={
            "required": False,
            "description": "Address to bind the SNMP trap listener",
            "hint": "e.g. 0.0.0.0 or 127.0.0.1",
        },
    )

    listen_port: int = dataclasses.field(
        default=162,
        metadata={
            "required": False,
            "description": "UDP port for the SNMP trap listener (1-65535)",
            "hint": "162 (requires CAP_NET_BIND_SERVICE) or 1162 for non-root",
            "validation": "port",
        },
    )

    # v1 / v2c
    community_string: str = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": "SNMP community string (v1/v2c)",
            "hint": "e.g. public",
            "sensitive": True,
        },
    )

    # v3 fields
    security_name: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 security name (username)",
            "hint": "e.g. snmpuser",
        },
    )

    auth_protocol: str = dataclasses.field(
        default="none",
        metadata={
            "required": False,
            "description": "SNMPv3 authentication protocol",
            "hint": "MD5, SHA, SHA256, SHA512, or none",
            "type": "select",
            "options": ["none", "MD5", "SHA", "SHA256", "SHA512"],
        },
    )

    auth_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 authentication key/passphrase",
            "sensitive": True,
        },
    )

    priv_protocol: str = dataclasses.field(
        default="none",
        metadata={
            "required": False,
            "description": "SNMPv3 privacy (encryption) protocol",
            "hint": "DES, AES, AES192, AES256, or none",
            "type": "select",
            "options": ["none", "DES", "AES", "AES192", "AES256"],
        },
    )

    priv_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 privacy key/passphrase",
            "sensitive": True,
        },
    )

    # Custom OID severity overrides
    oid_severity_map: Optional[dict] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Custom OID-to-severity mapping (overrides defaults)",
            "hint": '{"1.3.6.1.4.1.9.9.1": "critical"}',
        },
    )


class SnmpProvider(BaseProvider):
    """
    SNMP Provider: receives SNMP traps (v1/v2c/v3) via a native UDP listener
    and pushes them into Keep as alerts.
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert", "queue"]
    FINGERPRINT_FIELDS = ["source_address", "trap_oid", "ifIndex"]
    WEBHOOK_INSTALLATION_REQUIRED = False

    @staticmethod
    def _get_fingerprint_trap_oid(trap_oid: str, if_index: Optional[str]) -> str:
        """
        Normalize link state traps onto the linkDown OID when an interface index
        is present so linkDown/linkUp share a lifecycle fingerprint.
        """
        if if_index and trap_oid in (LINK_DOWN_TRAP_OID, LINK_UP_TRAP_OID):
            return LINK_DOWN_TRAP_OID
        return trap_oid

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self._running = False
        self._loop = None
        self._thread = None
        self._transport_dispatcher = None
        self._snmp_engine = None

    def validate_config(self):
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

        port = self.authentication_config.listen_port
        if not (1 <= port <= 65535):
            from keep.exceptions.provider_exception import ProviderException

            raise ProviderException("listen_port must be between 1 and 65535")

        version = self.authentication_config.snmp_version
        if version not in ("v1", "v2c", "v3"):
            from keep.exceptions.provider_exception import ProviderException

            raise ProviderException(
                f"Invalid snmp_version '{version}'. Must be v1, v2c, or v3."
            )

        if version == "v3":
            if not self.authentication_config.security_name:
                from keep.exceptions.provider_exception import ProviderException

                raise ProviderException(
                    "security_name is required when snmp_version is v3"
                )
            if (
                self.authentication_config.auth_protocol != "none"
                and not self.authentication_config.auth_key
            ):
                from keep.exceptions.provider_exception import ProviderException

                raise ProviderException(
                    "auth_key is required when auth_protocol is not 'none' (v3)"
                )
            if (
                self.authentication_config.priv_protocol != "none"
                and not self.authentication_config.priv_key
            ):
                from keep.exceptions.provider_exception import ProviderException

                raise ProviderException(
                    "priv_key is required when priv_protocol is not 'none' (v3)"
                )

    def dispose(self):
        self._running = False
        if self._snmp_engine:
            try:
                self._snmp_engine.closeDispatcher()
            except Exception:
                self.logger.debug("Engine dispatcher already closed", exc_info=True)
            self._snmp_engine = None
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        self._loop = None
        self._transport_dispatcher = None

    def status(self):
        return {
            "status": "running" if self._running else "stopped",
            "error": "",
        }

    def _get_severity(self, trap_oid: str) -> "AlertSeverity":
        """Resolve severity for a trap OID, checking user overrides first."""
        from keep.api.models.alert import AlertSeverity

        user_map = self.authentication_config.oid_severity_map or {}
        if trap_oid in user_map:
            raw = user_map[trap_oid]
            try:
                return AlertSeverity(raw)
            except (ValueError, KeyError):
                self.logger.warning(
                    "Invalid severity '%s' in oid_severity_map for OID %s, "
                    "falling back to default",
                    raw,
                    trap_oid,
                )

        return SNMP_TRAP_OID_TO_SEVERITY.get(trap_oid, AlertSeverity.INFO)

    def _build_event_from_v1(
        self,
        var_binds,
        transport_address,
        generic_trap,
        specific_trap,
        enterprise,
        uptime,
    ):
        """Build event dict from an SNMPv1 trap PDU."""
        from keep.api.models.alert import AlertStatus

        generic = int(generic_trap) if generic_trap is not None else 6

        if generic == 6:
            trap_oid = str(enterprise) + ".0." + str(specific_trap)
        else:
            oid_suffix = generic + 1
            trap_oid = f"1.3.6.1.6.3.1.1.5.{oid_suffix}"

        trap_name = SNMPV1_GENERIC_TRAP_TO_NAME.get(generic, "unknown")
        severity = SNMPV1_GENERIC_TRAP_TO_SEVERITY.get(
            generic, self._get_severity(trap_oid)
        )

        varbinds = []
        if_index = None
        for oid, val in var_binds:
            oid_str = str(oid)
            val_str = str(val) if val is not None else ""
            type_name = type(val).__name__ if val is not None else "unknown"
            varbinds.append({"oid": oid_str, "type": type_name, "value": val_str})
            if oid_str.startswith(IF_INDEX_OID_PREFIX):
                if_index = val_str

        source_addr = "unknown"
        source_port = 0
        if transport_address:
            try:
                addr = transport_address
                if isinstance(addr, (list, tuple)) and len(addr) > 0:
                    if isinstance(addr[0], (list, tuple)):
                        addr = addr[0]
                    source_addr = str(addr[0])
                    if len(addr) > 1:
                        source_port = int(addr[1])
            except (IndexError, TypeError, ValueError):
                pass

        status = AlertStatus.FIRING
        if generic == 3 and if_index:
            status = AlertStatus.RESOLVED

        event = {
            "trap_oid": trap_oid,
            "trap_name": trap_name,
            "snmp_version": "v1",
            "source_address": source_addr,
            "source_port": source_port,
            "community": "***",
            "uptime": str(uptime) if uptime is not None else "",
            "varbinds": varbinds,
            "raw_pdu": "",
            "received_at": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            "severity": severity.value if hasattr(severity, "value") else str(severity),
            "status": status.value,
            "ifIndex": if_index,
        }
        return event

    def _build_event_from_v2c_v3(self, var_binds, transport_address, snmp_version):
        """Build event dict from an SNMPv2c or v3 notification PDU."""
        from keep.api.models.alert import AlertStatus

        trap_oid = None
        uptime = None
        varbinds = []
        if_index = None

        for oid, val in var_binds:
            oid_str = str(oid)
            val_str = str(val) if val is not None else ""
            type_name = type(val).__name__ if val is not None else "unknown"

            if oid_str == SNMP_TRAP_OID_VARBIND:
                trap_oid = val_str
            elif oid_str == SYS_UPTIME_OID:
                uptime = val_str
            else:
                varbinds.append({"oid": oid_str, "type": type_name, "value": val_str})

            if oid_str.startswith(IF_INDEX_OID_PREFIX):
                if_index = val_str

        if trap_oid is None:
            trap_oid = "unknown"

        trap_name = SNMP_TRAP_OID_TO_NAME.get(trap_oid, "unknown")
        severity = self._get_severity(trap_oid)

        source_addr = "unknown"
        source_port = 0
        if transport_address:
            try:
                # transport_address may be a tuple like (ip, port) or
                # a nested structure like ((ip, port),)
                addr = transport_address
                if isinstance(addr, (list, tuple)) and len(addr) > 0:
                    if isinstance(addr[0], (list, tuple)):
                        addr = addr[0]
                    source_addr = str(addr[0])
                    if len(addr) > 1:
                        source_port = int(addr[1])
            except (IndexError, TypeError, ValueError):
                pass

        status = AlertStatus.FIRING
        if trap_oid == LINK_UP_TRAP_OID and if_index:
            status = AlertStatus.RESOLVED

        event = {
            "trap_oid": trap_oid,
            "trap_name": trap_name,
            "snmp_version": snmp_version,
            "source_address": source_addr,
            "source_port": source_port,
            "community": "***",
            "uptime": uptime or "",
            "varbinds": varbinds,
            "raw_pdu": "",
            "received_at": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            "severity": severity.value if hasattr(severity, "value") else str(severity),
            "status": status.value,
            "ifIndex": if_index,
        }
        return event

    @staticmethod
    def _format_alert(event: dict, provider_instance=None) -> dict:
        """
        Format a raw SNMP trap event dict into the shape expected by
        ``_push_alert`` / ``AlertDto``.
        """
        from keep.api.models.alert import AlertSeverity, AlertStatus

        trap_oid = event.get("trap_oid", "unknown")
        trap_name = event.get("trap_name", "unknown")
        source_address = event.get("source_address", "unknown")
        snmp_version = event.get("snmp_version", "unknown")
        varbinds = event.get("varbinds", [])
        if_index = event.get("ifIndex")
        received_at = event.get(
            "received_at",
            datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
        )

        name = trap_name if trap_name != "unknown" else f"SNMP trap {trap_oid}"

        try:
            severity = event.get("severity", "info")
            if isinstance(severity, AlertSeverity):
                severity = severity.value
        except Exception:
            severity = "info"

        status = event.get("status", AlertStatus.FIRING.value)
        if isinstance(status, AlertStatus):
            status = status.value

        fp_trap_oid = SnmpProvider._get_fingerprint_trap_oid(trap_oid, if_index)
        fp_parts = f"{source_address}|{fp_trap_oid}|{if_index or ''}"
        fingerprint = hashlib.sha256(fp_parts.encode()).hexdigest()

        description = (
            f"SNMP trap '{trap_name}' (OID {trap_oid}) from {source_address}"
            f" with {len(varbinds)} varbind(s)"
        )

        labels = {
            "source_address": source_address,
            "snmp_version": snmp_version,
            "trap_oid": trap_oid,
        }
        if if_index is not None:
            labels["ifIndex"] = if_index

        annotations = {
            "uptime": event.get("uptime", ""),
            "varbinds": varbinds,
        }

        alert = {
            "id": None,
            "name": name,
            "severity": severity,
            "status": status,
            "source": ["snmp"],
            "description": description,
            "labels": labels,
            "lastReceived": received_at,
            "fingerprint": fingerprint,
            "annotations": annotations,
        }
        return alert

    def start_consume(self):
        """
        Start the SNMP trap listener. Runs in a background thread with its
        own asyncio event loop so it does not block Keep's main thread.
        """
        from pysnmp.carrier.asyncio.dgram import udp
        from pysnmp.entity import config as snmp_config
        from pysnmp.entity import engine
        from pysnmp.entity.rfc3413 import ntfrcv

        import asyncio

        self._running = True
        self.logger.info(
            "Starting SNMP trap listener on %s:%d (version %s)",
            self.authentication_config.listen_address,
            self.authentication_config.listen_port,
            self.authentication_config.snmp_version,
        )

        # Ensure an asyncio event loop exists for this thread (pysnmp v6
        # uses asyncio transports that require a running loop).
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        self._loop = loop

        snmp_engine = engine.SnmpEngine()
        self._snmp_engine = snmp_engine

        # Configure transport - UDP IPv4
        try:
            snmp_config.addTransport(
                snmp_engine,
                udp.domainName,
                udp.UdpAsyncioTransport().openServerMode(
                    (
                        self.authentication_config.listen_address,
                        self.authentication_config.listen_port,
                    )
                ),
            )
            self.logger.info(
                "UDP transport bound on %s:%d",
                self.authentication_config.listen_address,
                self.authentication_config.listen_port,
            )
        except Exception:
            self.logger.exception(
                "Failed to bind UDP transport on %s:%d",
                self.authentication_config.listen_address,
                self.authentication_config.listen_port,
            )
            self._running = False
            return

        version = self.authentication_config.snmp_version

        if version in ("v1", "v2c"):
            snmp_config.addV1System(
                snmp_engine,
                "my-area",
                self.authentication_config.community_string,
            )
        elif version == "v3":
            auth_proto = self._get_auth_protocol()
            priv_proto = self._get_priv_protocol()

            auth_key = self.authentication_config.auth_key or ""
            priv_key = self.authentication_config.priv_key or ""

            snmp_config.addV3User(
                snmp_engine,
                self.authentication_config.security_name,
                auth_proto,
                auth_key,
                priv_proto,
                priv_key,
            )

        provider_ref = self

        def _trap_callback(
            snmp_engine_cb, context_engine_id, context_name, var_binds, cb_ctx
        ):
            """Called for every incoming trap/notification."""
            try:
                # In pysnmp v6, transport info is passed differently.
                # Try to extract the transport address from the engine's
                # message dispatcher.
                transport_address = None
                try:
                    exec_context = snmp_engine_cb.observer.getExecutionContext(
                        "rfc3412.receiveMessage:request"
                    )
                    transport_address = exec_context.get(
                        "transportAddress", ("unknown", 0)
                    )
                except Exception:
                    transport_address = ("unknown", 0)

                event = provider_ref._build_event_from_v2c_v3(
                    var_binds=var_binds,
                    transport_address=transport_address,
                    snmp_version=version,
                )

                formatted = SnmpProvider._format_alert(event)
                provider_ref._push_alert(formatted)

            except Exception:
                provider_ref.logger.exception(
                    "Error processing SNMP trap - listener continues"
                )

        ntfrcv.NotificationReceiver(snmp_engine, _trap_callback)

        self.logger.info("SNMP trap listener is running")
        try:
            snmp_engine.openDispatcher()
        except Exception:
            if self._running:
                self.logger.exception("SNMP dispatcher exited unexpectedly")
        finally:
            self._running = False
            self.logger.info("SNMP trap listener stopped")

    def stop_consume(self):
        self.dispose()

    def _get_auth_protocol(self):
        """Map config auth_protocol string to pysnmp OID tuple."""
        from pysnmp.entity import config as snmp_config

        mapping = {
            "none": snmp_config.usmNoAuthProtocol,
            "MD5": snmp_config.usmHMACMD5AuthProtocol,
            "SHA": snmp_config.usmHMACSHAAuthProtocol,
        }
        for name, attr in [
            ("SHA256", "usmHMAC192SHA256AuthProtocol"),
            ("SHA512", "usmHMAC384SHA512AuthProtocol"),
        ]:
            if hasattr(snmp_config, attr):
                mapping.setdefault(name, getattr(snmp_config, attr))

        proto = self.authentication_config.auth_protocol
        result = mapping.get(proto)
        if result is None:
            self.logger.warning(
                "Unknown auth_protocol '%s', falling back to none", proto
            )
            result = snmp_config.usmNoAuthProtocol
        return result

    def _get_priv_protocol(self):
        """Map config priv_protocol string to pysnmp OID tuple."""
        from pysnmp.entity import config as snmp_config

        mapping = {
            "none": snmp_config.usmNoPrivProtocol,
            "DES": snmp_config.usmDESPrivProtocol,
        }
        for name, attr in [
            ("AES", "usmAesCfb128Protocol"),
            ("AES192", "usmAesCfb192Protocol"),
            ("AES192", "usmAesBlumenthalCfb192Protocol"),
            ("AES256", "usmAesCfb256Protocol"),
            ("AES256", "usmAesBlumenthalCfb256Protocol"),
        ]:
            if hasattr(snmp_config, attr):
                mapping.setdefault(name, getattr(snmp_config, attr))

        proto = self.authentication_config.priv_protocol
        result = mapping.get(proto)
        if result is None:
            self.logger.warning(
                "Unknown priv_protocol '%s', falling back to none", proto
            )
            result = snmp_config.usmNoPrivProtocol
        return result
