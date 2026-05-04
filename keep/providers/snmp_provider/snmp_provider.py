"""
SNMP Provider – receive SNMP traps (v1, v2c, v3) and poll SNMP OIDs.

Uses pysnmp-lextudio (v6+ CamelCase API) for both:
  • Trap receiving  – low-level NotificationReceiver in a daemon thread
  • OID polling     – high-level hlapi.asyncio generators (getCmd / nextCmd / bulkCmd)
"""

import dataclasses
import datetime
import logging
import threading
import uuid
from typing import Any, Dict, List, Optional

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Well-known OID mappings used to enrich trap / poll data
# ---------------------------------------------------------------------------
SNMP_TRAP_OID = "1.3.6.1.2.1.1.3.0"  # sysUpTime
SNMP_TRAP_NAME_OID = "1.3.6.1.6.3.1.1.4.1.0"  # snmpTrapOID

# Common trap OID → human-readable name (can be extended by users via labels)
WELL_KNOWN_TRAPS: Dict[str, str] = {
    "1.3.6.1.6.3.1.1.5.1": "coldStart",
    "1.3.6.1.6.3.1.1.5.2": "warmStart",
    "1.3.6.1.6.3.1.1.5.3": "linkDown",
    "1.3.6.1.6.3.1.1.5.4": "linkUp",
    "1.3.6.1.6.3.1.1.5.5": "authenticationFailure",
    "1.3.6.1.6.3.1.1.5.6": "egpNeighborLoss",
}

# ---------------------------------------------------------------------------
# Severity heuristic based on generic trap type (v1) or trap OID
# ---------------------------------------------------------------------------
TRAP_SEVERITY_MAP: Dict[str, AlertSeverity] = {
    "coldStart": AlertSeverity.CRITICAL,
    "warmStart": AlertSeverity.WARNING,
    "linkDown": AlertSeverity.HIGH,
    "linkUp": AlertSeverity.INFO,
    "authenticationFailure": AlertSeverity.WARNING,
    "egpNeighborLoss": AlertSeverity.HIGH,
}

# ---------------------------------------------------------------------------
# Auth config
# ---------------------------------------------------------------------------

@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """SNMP provider authentication configuration.

    Supports SNMPv1/v2c (community string) and SNMPv3 (USM credentials).
    """

    # -- transport --
    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Host to poll or listen on (0.0.0.0 for trap listener)",
            "hint": "0.0.0.0",
        },
    )
    port: int = dataclasses.field(
        default=162,
        metadata={
            "required": False,
            "description": "UDP port for trap listener (default 162) or SNMP agent (default 161)",
            "hint": "162",
        },
    )

    # -- SNMP version --
    snmp_version: str = dataclasses.field(
        default="2c",
        metadata={
            "required": False,
            "description": "SNMP version: 1, 2c, or 3",
            "hint": "2c",
        },
    )

    # -- SNMPv1 / v2c --
    community: str = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": "SNMP community string (v1/v2c)",
            "hint": "public",
            "sensitive": True,
        },
    )

    # -- SNMPv3 --
    v3_username: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "SNMPv3 USM username",
            "hint": "usr-md5-des",
        },
    )
    v3_auth_key: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "SNMPv3 authentication key (required if authProtocol is set)",
            "hint": "authkey123",
            "sensitive": True,
        },
    )
    v3_auth_protocol: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "SNMPv3 auth protocol: MD5, SHA, SHA224, SHA256, SHA384, SHA512",
            "hint": "MD5",
        },
    )
    v3_priv_key: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "SNMPv3 privacy key (required if privProtocol is set)",
            "hint": "privkey123",
            "sensitive": True,
        },
    )
    v3_priv_protocol: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "SNMPv3 privacy protocol: DES, 3DES, AES128, AES192, AES256",
            "hint": "DES",
        },
    )
    v3_context_engine_id: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "SNMPv3 context engine ID (optional)",
            "hint": "",
        },
    )
    v3_context_name: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "SNMPv3 context name (optional)",
            "hint": "",
        },
    )

    # -- Polling --
    polling_host: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "Target host for SNMP polling (if different from trap host)",
            "hint": "192.168.1.1",
        },
    )
    polling_port: int = dataclasses.field(
        default=161,
        metadata={
            "required": False,
            "description": "Target port for SNMP polling (default 161)",
            "hint": "161",
        },
    )


# ---------------------------------------------------------------------------
# Provider class
# ---------------------------------------------------------------------------

class SnmpProvider(BaseProvider):
    """Receive SNMP traps and poll SNMP OIDs with Keep."""

    PROVIDER_DISPLAY_NAME = "SNMP"

    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="trap_receive",
            description="Ability to receive SNMP traps on the configured UDP port",
            mandatory=False,
            alias="Trap Receive",
        ),
        ProviderScope(
            name="snmp_poll",
            description="Ability to poll SNMP OIDs from target agents",
            mandatory=False,
            alias="SNMP Poll",
        ),
    ]

    FINGERPRINT_FIELDS = ["name"]

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self._consume = False
        self._snmp_engine = None
        self._trap_thread: Optional[threading.Thread] = None
        self._loop = None
        self.err = ""

    # ------------------------------------------------------------------
    # Config / scope validation
    # ------------------------------------------------------------------

    def validate_config(self):
        """Validate SNMP authentication configuration."""
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )
        # Basic version sanity check
        if self.authentication_config.snmp_version not in ("1", "2c", "3"):
            raise ValueError(
                f"Invalid SNMP version '{self.authentication_config.snmp_version}'. "
                "Must be one of: 1, 2c, 3"
            )

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes: dict[str, bool | str] = {}
        # Trap receive scope – always True (it's a local listener)
        scopes["trap_receive"] = True
        # Poll scope – try a simple SNMP GET to sysDescr.0
        try:
            result = self._snmp_get(["1.3.6.1.2.1.1.1.0"])
            if result is not None:
                scopes["snmp_poll"] = True
            else:
                scopes["snmp_poll"] = "No response from target"
        except Exception as exc:
            scopes["snmp_poll"] = str(exc)
        return scopes

    # ------------------------------------------------------------------
    # Dispose / status
    # ------------------------------------------------------------------

    def dispose(self):
        """Clean up SNMP engine and listener."""
        self.stop_consume()

    def status(self) -> dict:
        """Return current provider status."""
        status = "running" if self._consume else "stopped"
        return {
            "status": status,
            "error": self.err,
        }

    # ------------------------------------------------------------------
    # Consumer interface – trap listener
    # ------------------------------------------------------------------

    def start_consume(self):
        """Start the SNMP trap listener in a daemon thread."""
        self._consume = True
        self._trap_thread = threading.Thread(
            target=self._run_trap_listener, daemon=True, name="snmp-trap-listener"
        )
        self._trap_thread.start()
        self.logger.info("SNMP trap listener thread started")

    def stop_consume(self):
        """Signal the trap listener to stop and shut down the engine."""
        self._consume = False
        if self._snmp_engine is not None:
            try:
                self._snmp_engine.transportDispatcher.closeDispatcher()
            except Exception:
                pass
            self._snmp_engine = None
        if self._loop is not None:
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass
            self._loop = None
        if self._trap_thread is not None:
            self._trap_thread.join(timeout=5)
            self._trap_thread = None
        self.logger.info("SNMP trap listener stopped")

    # ------------------------------------------------------------------
    # Internal trap listener
    # ------------------------------------------------------------------

    def _run_trap_listener(self):
        """Set up and run the pysnmp trap receiver (blocking)."""
        try:
            from pysnmp.hlapi import udp
            from pysnmp.entity import config, engine
            from pysnmp.entity.rfc3413 import ntfrcv

            self._snmp_engine = engine.SnmpEngine()

            # -- v1 / v2c community --
            ver = self.authentication_config.snmp_version
            if ver in ("1", "2c"):
                config.addV1System(
                    self._snmp_engine,
                    "keep-community",
                    self.authentication_config.community,
                )

            # -- v3 USM user --
            if ver == "3" and self.authentication_config.v3_username:
                auth_proto, priv_proto = self._resolve_v3_protocols()
                config.addV3User(
                    self._snmp_engine,
                    self.authentication_config.v3_username,
                    auth_proto,
                    self.authentication_config.v3_auth_key or None,
                    priv_proto,
                    self.authentication_config.v3_priv_key or None,
                )

            # -- transport --
            config.addTransport(
                self._snmp_engine,
                udp.domainName,
                config.UdpTransport().openServerMode(
                    (self.authentication_config.host, self.authentication_config.port)
                ),
            )

            # -- callback --
            def _trap_cb(
                snmpEngine,
                stateReference,
                contextEngineId,
                contextName,
                varBinds,
                cbCtx,
            ):
                if not self._consume:
                    return
                try:
                    self._handle_trap(varBinds)
                except Exception:
                    self.logger.exception("Error handling SNMP trap")

            ntfrcv.NotificationReceiver(self._snmp_engine, _trap_cb)

            self.logger.info(
                "SNMP trap listener bound on %s:%d (v%s)",
                self.authentication_config.host,
                self.authentication_config.port,
                self.authentication_config.snmp_version,
            )

            # openDispatcher runs the asyncio loop (blocking)
            self._snmp_engine.openDispatcher()

        except Exception:
            self.err = "Trap listener failed to start"
            self.logger.exception("Failed to start SNMP trap listener")

    # ------------------------------------------------------------------
    # Trap → AlertDto mapping
    # ------------------------------------------------------------------

    def _handle_trap(self, varBinds: list):
        """Convert pysnmp varBinds into a Keep alert dict and push it."""

        trap_oid = ""
        trap_name = "SNMP Trap"
        uptime = ""
        extra_labels: Dict[str, str] = {}

        for oid, val in varBinds:
            oid_str = str(oid)
            val_pretty = val.prettyPrint()

            # sysUpTime
            if oid_str == SNMP_TRAP_OID:
                uptime = val_pretty
                extra_labels["sysUpTime"] = uptime
                continue

            # snmpTrapOID
            if oid_str == SNMP_TRAP_NAME_OID:
                trap_oid = str(val)
                trap_name = WELL_KNOWN_TRAPS.get(trap_oid, trap_oid)
                continue

            # generic varbind
            extra_labels[oid_str] = val_pretty

        # Determine severity from well-known trap name or default WARNING
        severity = TRAP_SEVERITY_MAP.get(trap_name, AlertSeverity.WARNING)

        # Infer status: linkUp → resolved, everything else → firing
        if trap_name == "linkUp":
            status = AlertStatus.RESOLVED
        else:
            status = AlertStatus.FIRING

        now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

        alert_dict = {
            "id": str(uuid.uuid4()),
            "name": trap_name or "SNMP Trap",
            "description": self._build_description(trap_name, trap_oid, uptime, extra_labels),
            "status": status,
            "severity": severity,
            "lastReceived": now,
            "source": ["snmp"],
            "labels": extra_labels,
            "environment": "production",
        }

        self._push_alert(alert_dict)

    @staticmethod
    def _build_description(
        trap_name: str,
        trap_oid: str,
        uptime: str,
        extra_labels: Dict[str, str],
    ) -> str:
        parts = [f"SNMP Trap: {trap_name}"]
        if trap_oid:
            parts.append(f"Trap OID: {trap_oid}")
        if uptime:
            parts.append(f"sysUpTime: {uptime}")
        if extra_labels:
            varbind_summary = ", ".join(
                f"{k}={v}" for k, v in extra_labels.items()
            )
            parts.append(f"VarBinds: {varbind_summary}")
        return " | ".join(parts)

    # ------------------------------------------------------------------
    # Polling – _query
    # ------------------------------------------------------------------

    def _query(self, oids: list[str] = None, **kwargs) -> list[AlertDto]:
        """Poll one or more SNMP OIDs and return alerts.

        Args:
            oids: list of OID strings to poll (e.g. ["1.3.6.1.2.1.1.1.0"])
            **kwargs: additional keyword args:
                operation: "get" (default), "next", or "bulk"
                non_repeaters: for bulk walk
                max_repetitions: for bulk walk

        Returns:
            list[AlertDto]: one AlertDto per OID result
        """
        if not oids:
            return []

        operation = kwargs.get("operation", "get")
        results: list[AlertDto] = []

        try:
            if operation == "next":
                raw = self._snmp_next(oids)
            elif operation == "bulk":
                non_reps = int(kwargs.get("non_repeaters", 0))
                max_reps = int(kwargs.get("max_repetitions", 25))
                raw = self._snmp_bulk(oids, non_reps, max_reps)
            else:
                raw = self._snmp_get(oids)
        except Exception as exc:
            self.logger.exception("SNMP poll failed")
            raise

        if raw is None:
            return []

        # raw is list of (oid, value) tuples or list-of-lists
        now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                oid_str, val_str = item
            elif isinstance(item, (list, tuple)):
                # nextCmd / bulkCmd return list of varbind-lists
                for inner in item:
                    if isinstance(inner, (list, tuple)) and len(inner) == 2:
                        oid_str, val_str = inner
                    else:
                        continue
                if not isinstance(item[0], str):
                    continue
            else:
                continue

            results.append(
                AlertDto(
                    id=str(uuid.uuid4()),
                    name=f"SNMP Poll: {oid_str}",
                    description=f"OID {oid_str} = {val_str}",
                    status=AlertStatus.FIRING,
                    severity=AlertSeverity.INFO,
                    lastReceived=now,
                    source=["snmp"],
                    labels={"oid": oid_str, "value": val_str},
                )
            )

        return results

    # ------------------------------------------------------------------
    # High-level SNMP helpers (asyncio generators)
    # ------------------------------------------------------------------

    def _build_auth_data(self):
        """Return the appropriate CommunityData / UsmUserData object."""
        from pysnmp.hlapi import CommunityData, UsmUserData

        ver = self.authentication_config.snmp_version
        if ver in ("1", "2c"):
            return CommunityData(self.authentication_config.community, mpModel=(0 if ver == "1" else 1))

        if ver == "3" and self.authentication_config.v3_username:
            auth_proto, priv_proto = self._resolve_v3_protocols()
            return UsmUserData(
                self.authentication_config.v3_username,
                self.authentication_config.v3_auth_key or None,
                self.authentication_config.v3_priv_key or None,
                authProtocol=auth_proto,
                privProtocol=priv_proto,
            )

        # Default fallback – v2c
        return CommunityData(self.authentication_config.community, mpModel=1)

    def _build_transport_target(self):
        """Return a UdpTransportTarget for polling."""
        from pysnmp.hlapi import UdpTransportTarget

        host = self.authentication_config.polling_host or self.authentication_config.host
        port = 161 if self.authentication_config.polling_port == 162 else self.authentication_config.polling_port
        return UdpTransportTarget((host, port), timeout=5.0, retries=2)

    def _snmp_get(self, oids: list[str]) -> Optional[list]:
        """SNMP GET one or more OIDs. Returns list of (oid, value) tuples."""
        from pysnmp.hlapi import ContextData, ObjectType, getCmd

        from pysnmp.hlapi import ObjectIdentity

        auth = self._build_auth_data()
        transport = self._build_transport_target()

        object_types = [ObjectType(ObjectIdentity(oid)) for oid in oids]

        error_indication, error_status, error_index, var_binds = next(
            getCmd(
                self._get_snmp_engine_hlapi(),
                auth,
                transport,
                ContextData(),
                *object_types,
            )
        )

        if error_indication or error_status:
            self.logger.warning(
                "SNMP GET error: %s / %s", error_indication, error_status
            )
            return None

        return [(str(oid), val.prettyPrint()) for oid, val in var_binds]

    def _snmp_next(self, oids: list[str]) -> Optional[list]:
        """SNMP GETNEXT (walk one step). Returns list of (oid, value) tuples."""
        from pysnmp.hlapi import ContextData, ObjectIdentity, ObjectType, nextCmd

        auth = self._build_auth_data()
        transport = self._build_transport_target()

        object_types = [ObjectType(ObjectIdentity(oid)) for oid in oids]
        results = []

        for error_indication, error_status, error_index, var_bind_table in nextCmd(
            self._get_snmp_engine_hlapi(),
            auth,
            transport,
            ContextData(),
            *object_types,
        ):
            if error_indication or error_status:
                self.logger.warning(
                    "SNMP NEXT error: %s / %s", error_indication, error_status
                )
                break
            for var_binds in var_bind_table:
                for oid, val in var_binds:
                    results.append((str(oid), val.prettyPrint()))

        return results or None

    def _snmp_bulk(
        self, oids: list[str], non_repeaters: int = 0, max_repetitions: int = 25
    ) -> Optional[list]:
        """SNMP GETBULK. Returns list of (oid, value) tuples."""
        from pysnmp.hlapi import ContextData, ObjectIdentity, ObjectType, bulkCmd

        auth = self._build_auth_data()
        transport = self._build_transport_target()

        object_types = [ObjectType(ObjectIdentity(oid)) for oid in oids]
        results = []

        for error_indication, error_status, error_index, var_bind_table in bulkCmd(
            self._get_snmp_engine_hlapi(),
            auth,
            transport,
            ContextData(),
            non_repeaters,
            max_repetitions,
            *object_types,
        ):
            if error_indication or error_status:
                self.logger.warning(
                    "SNMP BULK error: %s / %s", error_indication, error_status
                )
                break
            for var_binds in var_bind_table:
                for oid, val in var_binds:
                    results.append((str(oid), val.prettyPrint()))

        return results or None

    def _get_snmp_engine_hlapi(self):
        """Create a fresh SnmpEngine for hlapi calls (separate from trap engine)."""
        from pysnmp.hlapi import SnmpEngine
        return SnmpEngine()

    # ------------------------------------------------------------------
    # v3 protocol resolution
    # ------------------------------------------------------------------

    def _resolve_v3_protocols(self):
        """Map user-friendly strings to pysnmp auth/priv protocol constants.

        Returns (authProtocol, privProtocol) where either may be None.
        """
        from pysnmp.hlapi import (
            usmDESPrivProtocol,
            usmHMACMD5AuthProtocol,
            usmHMACSHAAuthProtocol,
            usm3DESEDEPrivProtocol,
            usmAesCfb128Protocol,
        )

        AUTH_MAP = {
            "MD5": usmHMACMD5AuthProtocol,
            "SHA": usmHMACSHAAuthProtocol,
        }

        PRIV_MAP = {
            "DES": usmDESPrivProtocol,
            "3DES": usm3DESEDEPrivProtocol,
            "AES128": usmAesCfb128Protocol,
            "AES": usmAesCfb128Protocol,  # convenience alias
        }

        # Try to import extended protocol constants (available in pysnmp-lextudio)
        try:
            from pysnmp.hlapi import (
                usmHMAC128SHA224AuthProtocol,
                usmHMAC192SHA256AuthProtocol,
                usmHMAC256SHA384AuthProtocol,
                usmHMAC384SHA512AuthProtocol,
                usmAesCfb192Protocol,
                usmAesCfb256Protocol,
            )
            AUTH_MAP.update(
                {
                    "SHA224": usmHMAC128SHA224AuthProtocol,
                    "SHA256": usmHMAC192SHA256AuthProtocol,
                    "SHA384": usmHMAC256SHA384AuthProtocol,
                    "SHA512": usmHMAC384SHA512AuthProtocol,
                }
            )
            PRIV_MAP.update(
                {
                    "AES192": usmAesCfb192Protocol,
                    "AES256": usmAesCfb256Protocol,
                }
            )
        except ImportError:
            pass

        auth_proto = AUTH_MAP.get(
            self.authentication_config.v3_auth_protocol.upper()
            if self.authentication_config.v3_auth_protocol
            else "",
            None,
        )
        priv_proto = PRIV_MAP.get(
            self.authentication_config.v3_priv_protocol.upper()
            if self.authentication_config.v3_priv_protocol
            else "",
            None,
        )

        return auth_proto, priv_proto

    # ------------------------------------------------------------------
    # Static formatter used by webhook / push path
    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(event: dict, provider_instance: BaseProvider = None) -> AlertDto:
        """Format an incoming webhook/dict event into an AlertDto.

        This is useful when alerts are pushed into Keep via the generic
        webhook endpoint and need to be mapped to AlertDto fields.
        """
        return AlertDto(
            id=event.get("id", str(uuid.uuid4())),
            name=event.get("name", "SNMP Alert"),
            description=event.get("description", ""),
            status=AlertStatus(event.get("status", "firing")),
            severity=AlertSeverity(event.get("severity", "warning")),
            lastReceived=event.get(
                "lastReceived",
                datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            ),
            source=["snmp"],
            labels=event.get("labels", {}),
            environment=event.get("environment", "production"),
        )


if __name__ == "__main__":
    import os

    os.environ.setdefault("KEEP_API_URL", "http://localhost:8080")
    from keep.api.core.dependencies import SINGLE_TENANT_UUID

    context_manager = ContextManager(tenant_id=SINGLE_TENANT_UUID)
    config = ProviderConfig(
        authentication={
            "host": "0.0.0.0",
            "port": 1162,
            "snmp_version": "2c",
            "community": "public",
        }
    )
    provider = SnmpProvider(context_manager, "snmp-test", config)
    provider.start_consume()