"""
SNMP Provider for Keep — receives SNMP traps and optionally polls OIDs.

Supports:
  - SNMPv1, v2c trap reception
  - SNMPv3 with authentication (MD5/SHA) and privacy (DES/AES)
  - Configurable trap listener (host:port)
  - Optional periodic SNMP polling
  - OID-to-alert severity mapping (JSON configurable)
  - Graceful fallback when pysnmp-lextudio is not installed

Requires: pysnmp-lextudio (optional)
  pip install pysnmp-lextudio
"""

import dataclasses
import datetime
import json
import logging
import threading
import uuid
from typing import Optional

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)

# Optional pysnmp import — provider degrades gracefully without it
try:
    from pysnmp.hlapi import (
        CommunityData,
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        getCmd,
        nextCmd,
    )
    from pysnmp.carrier.asyncore.dgram import udp as snmp_udp
    from pysnmp.entity import engine, config as snmp_config
    from pysnmp.entity.rfc3413 import ntfrcv

    PYSNMP_AVAILABLE = True
except ImportError:
    PYSNMP_AVAILABLE = False
    logger.warning(
        "pysnmp-lextudio is not installed. SNMP trap listener and polling "
        "will be unavailable. Install with: pip install pysnmp-lextudio"
    )


@pydantic.dataclasses.dataclass
class SNMPProviderAuthConfig:
    """SNMP provider configuration."""

    host: str = dataclasses.field(
        default="0.0.0.0",
        metadata={
            "required": False,
            "description": "Listen address for SNMP trap receiver",
            "hint": "0.0.0.0 (all interfaces) or specific IP",
        },
    )
    port: int = dataclasses.field(
        default=162,
        metadata={
            "required": False,
            "description": "UDP port to listen for SNMP traps",
            "hint": "Default SNMP trap port is 162 (requires root) or 1620+",
        },
    )
    community_string: str = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": "SNMP community string (SNMPv1/v2c)",
            "hint": "Default is 'public'",
            "sensitive": True,
        },
    )
    version: str = dataclasses.field(
        default="2c",
        metadata={
            "required": False,
            "description": "SNMP version: 1, 2c, or 3",
            "hint": "Use '2c' for most setups; '3' for encrypted/authenticated",
        },
    )
    # SNMPv3 fields
    username: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "SNMPv3 username",
        },
    )
    auth_key: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "SNMPv3 authentication key",
            "sensitive": True,
        },
    )
    auth_protocol: str = dataclasses.field(
        default="MD5",
        metadata={
            "required": False,
            "description": "SNMPv3 auth protocol: MD5 or SHA",
            "hint": "MD5 or SHA",
        },
    )
    priv_key: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "SNMPv3 privacy (encryption) key",
            "sensitive": True,
        },
    )
    priv_protocol: str = dataclasses.field(
        default="DES",
        metadata={
            "required": False,
            "description": "SNMPv3 privacy protocol: DES or AES",
            "hint": "DES or AES",
        },
    )
    # OID mapping
    oids_mapping: str = dataclasses.field(
        default="{}",
        metadata={
            "required": False,
            "description": (
                "JSON map of OID prefixes to alert settings. "
                'Example: {"1.3.6.1.4.1.9": {"name": "Cisco Alert", "severity": "high"}}'
            ),
            "hint": '{"OID_PREFIX": {"name": "AlertName", "severity": "critical|high|warning|info|low"}}',
        },
    )
    # Polling
    poll_enabled: bool = dataclasses.field(
        default=False,
        metadata={
            "required": False,
            "description": "Enable periodic SNMP polling of target devices",
        },
    )
    poll_targets: str = dataclasses.field(
        default="[]",
        metadata={
            "required": False,
            "description": (
                "JSON list of polling targets. "
                'Example: [{"host": "192.168.1.1", "community": "public", "oids": ["1.3.6.1.2.1.1.3.0"]}]'
            ),
        },
    )
    poll_interval: int = dataclasses.field(
        default=60,
        metadata={
            "required": False,
            "description": "Polling interval in seconds",
            "hint": "Default: 60s",
        },
    )


class SNMPProvider(BaseProvider):
    """
    SNMP Provider — ingests SNMP traps and polls OIDs as Keep alerts.

    This provider runs a background SNMP trap listener and optional poller.
    Configure OID mappings to control how traps become alerts.
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]

    # Maximum number of alerts to retain in memory (oldest are evicted)
    _MAX_ALERTS = 10_000

    # OIDs that indicate recovery / normal state → AlertStatus.RESOLVED
    _RECOVERY_OIDS: set[str] = {
        "1.3.6.1.6.3.1.1.5.1",  # coldStart
        "1.3.6.1.6.3.1.1.5.2",  # warmStart
        "1.3.6.1.6.3.1.1.5.4",  # linkUp
    }

    # The snmpTrapOID.0 varbind OID
    _SNMP_TRAP_OID = "1.3.6.1.6.3.1.1.4.1.0"

    # Severity mapping for well-known enterprise OID prefixes
    _ENTERPRISE_SEVERITY: dict[str, AlertSeverity] = {
        "1.3.6.1.4.1.9.": AlertSeverity.HIGH,       # Cisco
        "1.3.6.1.4.1.11.": AlertSeverity.HIGH,       # HP
        "1.3.6.1.4.1.2636.": AlertSeverity.HIGH,     # Juniper
        "1.3.6.1.4.1.2011.": AlertSeverity.MEDIUM,   # Huawei
        "1.3.6.1.6.3.1.1.5.1": AlertSeverity.INFO,   # coldStart
        "1.3.6.1.6.3.1.1.5.2": AlertSeverity.WARNING,  # warmStart
        "1.3.6.1.6.3.1.1.5.3": AlertSeverity.CRITICAL,  # linkDown
        "1.3.6.1.6.3.1.1.5.4": AlertSeverity.INFO,   # linkUp
        "1.3.6.1.6.3.1.1.5.5": AlertSeverity.CRITICAL,  # authenticationFailure
        "1.3.6.1.6.3.1.1.5.6": AlertSeverity.WARNING,  # egpNeighborLoss
    }

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        self._alerts: list[AlertDto] = []
        self._alerts_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._listener_thread: Optional[threading.Thread] = None
        self._poll_thread: Optional[threading.Thread] = None
        super().__init__(context_manager, provider_id, config)

        # Parse JSON configs (authentication_config set by validate_config)
        try:
            self._oids_mapping: dict = json.loads(
                self.authentication_config.oids_mapping
            )
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid oids_mapping JSON — using empty mapping")
            self._oids_mapping = {}

        try:
            self._poll_targets: list = json.loads(
                self.authentication_config.poll_targets
            )
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid poll_targets JSON — using empty list")
            self._poll_targets = []

    def validate_config(self):
        """Validate SNMP configuration."""
        self.authentication_config = SNMPProviderAuthConfig(
            **self.config.authentication
        )
        cfg = self.authentication_config
        if cfg.version not in ("1", "2c", "3"):
            raise ValueError(
                f"Invalid SNMP version '{cfg.version}'. Must be one of: 1, 2c, 3"
            )
        if cfg.version == "3" and not cfg.username:
            raise ValueError("SNMPv3 requires a username")
        if not (0 < cfg.port <= 65535):
            raise ValueError(
                f"Invalid port {cfg.port}. Must be between 1 and 65535"
            )
        if cfg.poll_interval < 1:
            raise ValueError(
                f"Invalid poll_interval {cfg.poll_interval}. Must be >= 1 second"
            )
        if cfg.auth_protocol not in ("MD5", "SHA"):
            logger.warning(
                "Unknown auth_protocol '%s'. Defaulting to MD5", cfg.auth_protocol
            )
        if cfg.priv_protocol not in ("DES", "AES"):
            logger.warning(
                "Unknown priv_protocol '%s'. Defaulting to DES", cfg.priv_protocol
            )
        if not PYSNMP_AVAILABLE:
            logger.warning(
                "pysnmp-lextudio not installed — trap listener disabled. "
                "Install: pip install pysnmp-lextudio"
            )

    def dispose(self):
        """Stop the trap listener and polling threads."""
        logger.info("SNMP provider disposing — stopping threads")
        self._stop_event.set()
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=5)
            logger.debug("Trap listener thread stopped")
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=5)
            logger.debug("Poll thread stopped")

    def _get_alerts(self) -> list[AlertDto]:
        """Return all alerts captured from SNMP traps and polls."""
        if not self._listener_thread or not self._listener_thread.is_alive():
            self._start_trap_listener()
        if self.authentication_config.poll_enabled:
            if not self._poll_thread or not self._poll_thread.is_alive():
                self._start_polling()
        with self._alerts_lock:
            return list(self._alerts)

    # ------------------------------------------------------------------
    # Trap listener
    # ------------------------------------------------------------------

    def _start_trap_listener(self):
        """Start background trap listener thread."""
        if not PYSNMP_AVAILABLE:
            logger.warning("Cannot start trap listener: pysnmp-lextudio not installed")
            return
        self._stop_event.clear()
        self._listener_thread = threading.Thread(
            target=self._trap_listener_loop,
            name=f"snmp-trap-{self.provider_id}",
            daemon=True,
        )
        self._listener_thread.start()
        logger.info(
            "SNMP trap listener started on %s:%d (version %s)",
            self.authentication_config.host,
            self.authentication_config.port,
            self.authentication_config.version,
        )

    def _trap_listener_loop(self):
        """Main loop for the SNMP trap listener using pysnmp."""
        try:
            snmp_engine = engine.SnmpEngine()

            # Transport — use synchronous (asyncore) UDP for threaded listener
            snmp_config.addTransport(
                snmp_engine,
                snmp_udp.domainName,
                snmp_udp.UdpSocketTransport().openServerMode(
                    (self.authentication_config.host, self.authentication_config.port)
                ),
            )

            # Community/auth
            if self.authentication_config.version in ("1", "2c"):
                snmp_config.addV1System(
                    snmp_engine,
                    "trap-area",
                    self.authentication_config.community_string,
                )
            else:
                self._configure_v3_listener(snmp_engine)

            # Register trap receiver
            ntfrcv.NotificationReceiver(snmp_engine, self._trap_callback)
            snmp_engine.transportDispatcher.jobStarted(1)

            try:
                while not self._stop_event.is_set():
                    snmp_engine.transportDispatcher.runDispatcher(timeout=1.0)
            except Exception as exc:
                logger.warning("Trap dispatcher loop error: %s", exc)
            finally:
                snmp_engine.transportDispatcher.closeDispatcher()

        except PermissionError:
            logger.exception(
                "SNMP trap listener failed to bind %s:%d — "
                "port 162 requires root/elevated privileges. "
                "Use a port >1024 (e.g. 1620) or run with appropriate permissions.",
                self.authentication_config.host,
                self.authentication_config.port,
            )
        except OSError as exc:
            logger.exception(
                "SNMP trap listener failed to bind %s:%d — %s",
                self.authentication_config.host,
                self.authentication_config.port,
                exc,
            )
        except Exception as exc:
            logger.exception("SNMP trap listener crashed: %s", exc)

    def _configure_v3_listener(self, snmp_engine):
        """Configure SNMPv3 authentication and privacy for the listener."""
        auth_proto_map = {
            "MD5": snmp_config.usmHMACMD5AuthProtocol,
            "SHA": snmp_config.usmHMACSHAAuthProtocol,
        }
        priv_proto_map = {
            "DES": snmp_config.usmDESPrivProtocol,
            "AES": snmp_config.usmAesCfb128Protocol,
        }

        auth_proto = auth_proto_map.get(
            self.authentication_config.auth_protocol.upper(),
            snmp_config.usmHMACMD5AuthProtocol,
        )
        priv_proto = priv_proto_map.get(
            self.authentication_config.priv_protocol.upper(),
            snmp_config.usmDESPrivProtocol,
        )

        snmp_config.addV3User(
            snmp_engine,
            self.authentication_config.username,
            auth_proto,
            self.authentication_config.auth_key or None,
            priv_proto,
            self.authentication_config.priv_key or None,
        )

    def _trap_callback(self, snmp_engine, state_reference, context_engine_id,
                       context_name, var_binds, cbCtx):
        """Callback invoked for each received SNMP trap."""
        try:
            # Extract source IP from the transport address via the SNMP engine
            source_ip = None
            try:
                transport_domain, transport_address = snmp_engine.msgAndPduDsp.getTransportInfo(
                    state_reference
                )
                if transport_address:
                    source_ip = str(transport_address[0])
            except Exception:
                logger.debug("Could not extract source IP from transport address")

            alert = self._varbinds_to_alert(var_binds, source_ip=source_ip)
            self._append_alert(alert)
            logger.debug("Trap received → alert: %s (severity=%s)", alert.name, alert.severity)
        except Exception as exc:
            logger.warning("Error processing trap: %s", exc)

    def _varbinds_to_alert(self, var_binds, source_ip: Optional[str] = None) -> AlertDto:
        """Convert SNMP trap varbinds to an AlertDto."""
        trap_oid = None
        last_oid = ""
        values: list[str] = []

        for oid, val in var_binds:
            oid_str = str(oid)
            last_oid = oid_str
            values.append(f"{oid} = {val}")
            # Extract the snmpTrapOID.0 value — this is the actual trap type
            if oid_str == self._SNMP_TRAP_OID:
                trap_oid = str(val)

        # Use trap_oid as primary OID for lookups; fall back to last varbind OID
        primary_oid = trap_oid or last_oid

        # Look up OID in mapping
        mapped = self._map_oid_to_alert_config(primary_oid)
        if not isinstance(mapped, dict):
            mapped = {}
        name = mapped.get("name", f"SNMP Trap: {primary_oid}")
        severity = self._parse_severity(mapped.get("severity", ""))

        if not severity:
            severity = self._infer_severity_from_oid(primary_oid)

        # Determine status: recovery OIDs → RESOLVED, everything else → FIRING
        status = AlertStatus.FIRING
        if primary_oid in self._RECOVERY_OIDS:
            status = AlertStatus.RESOLVED

        # Build fingerprint for deduplication: source_ip + trap_oid
        fingerprint = None
        if source_ip and primary_oid:
            fingerprint = f"{source_ip}:{primary_oid}"

        # Include source_ip and trap_oid in labels for downstream consumers
        labels = {}
        if source_ip:
            labels["source_ip"] = source_ip
        if trap_oid:
            labels["trap_oid"] = trap_oid

        return AlertDto(
            id=str(uuid.uuid4()),
            name=name,
            severity=severity,
            status=status,
            source=["snmp"],
            description="\n".join(values),
            fingerprint=fingerprint,
            labels=labels if labels else None,
            lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    def _start_polling(self):
        """Start background OID polling thread."""
        if not PYSNMP_AVAILABLE:
            logger.warning("Cannot start SNMP polling: pysnmp-lextudio not installed")
            return
        if not self._poll_targets:
            logger.info("No poll_targets configured — polling disabled")
            return
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            name=f"snmp-poll-{self.provider_id}",
            daemon=True,
        )
        self._poll_thread.start()
        logger.info(
            "SNMP polling started — %d targets, interval=%ds",
            len(self._poll_targets),
            self.authentication_config.poll_interval,
        )

    def _poll_loop(self):
        """Poll configured SNMP targets periodically."""
        while not self._stop_event.wait(
            timeout=self.authentication_config.poll_interval
        ):
            for target in self._poll_targets:
                try:
                    self._poll_target(target)
                except Exception as exc:
                    logger.warning("Poll error for %s: %s", target.get("host"), exc)

    def _poll_target(self, target: dict):
        """Poll a single SNMP target and create alerts for OID values."""
        host = target.get("host", "127.0.0.1")
        community = target.get("community", "public")
        oids = target.get("oids", [])

        if not oids:
            return

        for oid in oids:
            for error_indication, error_status, error_index, var_binds in getCmd(
                SnmpEngine(),
                CommunityData(community),
                UdpTransportTarget((host, 161), timeout=5, retries=1),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
            ):
                if error_indication:
                    logger.warning("SNMP poll error for %s OID %s: %s", host, oid, error_indication)
                    break
                if error_status:
                    logger.warning(
                        "SNMP poll error status for %s: %s at %s",
                        host, error_status.prettyPrint(),
                        error_index and var_binds[int(error_index) - 1][0] or "?"
                    )
                    break
                for var_bind in var_binds:
                    oid_str, value = str(var_bind[0]), str(var_bind[1])
                    mapped = self._map_oid_to_alert_config(oid_str)
                    if not isinstance(mapped, dict):
                        mapped = {}
                    name = mapped.get("name", f"SNMP Poll: {oid_str}")
                    severity = self._parse_severity(
                        mapped.get("severity", "")
                    ) or AlertSeverity.INFO
                    alert = AlertDto(
                        id=str(uuid.uuid4()),
                        name=name,
                        severity=severity,
                        status=AlertStatus.FIRING,
                        source=["snmp"],
                        description=f"{oid_str} = {value} (from {host})",
                        lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    )
                    self._append_alert(alert)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _append_alert(self, alert: AlertDto):
        """Thread-safe append with bounded list size."""
        with self._alerts_lock:
            self._alerts.append(alert)
            if len(self._alerts) > self._MAX_ALERTS:
                self._alerts = self._alerts[-self._MAX_ALERTS:]

    def _map_oid_to_alert_config(self, oid: str) -> dict:
        """Find the best matching OID prefix in oids_mapping."""
        if not self._oids_mapping:
            return {}
        # Try exact match first, then progressively shorter prefixes
        best_match = {}
        best_len = 0
        for prefix, config in self._oids_mapping.items():
            if oid.startswith(prefix) and len(prefix) > best_len:
                best_match = config
                best_len = len(prefix)
        return best_match

    def _infer_severity_from_oid(self, oid: str) -> AlertSeverity:
        """Infer alert severity from well-known OID prefixes."""
        for prefix, severity in self._ENTERPRISE_SEVERITY.items():
            if oid.startswith(prefix):
                return severity
        return AlertSeverity.INFO

    _SEVERITY_MAP: dict[str, AlertSeverity] = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "medium": AlertSeverity.MEDIUM,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
    }

    @staticmethod
    def _parse_severity(severity_str: str) -> Optional[AlertSeverity]:
        """Parse a severity string into AlertSeverity enum."""
        return SNMPProvider._SEVERITY_MAP.get(severity_str.lower().strip()) if severity_str else None
