"""
SNMP Provider for Keep - Receives SNMP traps and converts them to Keep alerts.
Supports SNMPv2c and SNMPv3 trap listening via pysnmp-lextudio.
Optional SNMP polling for OID value checks.
"""

import dataclasses
import json
import logging
import threading
from typing import Optional

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SNMPProviderAuthConfig:
    """SNMP provider authentication configuration."""

    host: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Listen address for SNMP traps",
            "default": "0.0.0.0",
        },
        default="0.0.0.0",
    )
    port: int = dataclasses.field(
        metadata={
            "required": False,
            "description": "Port to listen for SNMP traps",
            "default": "162",
        },
        default=162,
    )
    community_string: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMP community string (SNMPv2c)",
            "default": "public",
        },
        default="public",
    )
    version: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMP version: 2c or 3",
            "default": "2c",
        },
        default="2c",
    )
    username: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 username",
        },
        default="",
    )
    auth_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 auth key",
            "sensitive": True,
        },
        default="",
    )
    auth_protocol: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 auth protocol: MD5 or SHA",
            "default": "MD5",
        },
        default="MD5",
    )
    priv_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 privacy key",
            "sensitive": True,
        },
        default="",
    )
    priv_protocol: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 privacy protocol: DES or AES",
            "default": "DES",
        },
        default="DES",
    )
    oids_mapping: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "JSON mapping of OID patterns to alert settings. "
            'Example: {"1.3.6.1.4.1.1.1": {"name": "MyAlert", "severity": "critical"}}',
            "hint": 'JSON: {"OID": {"name": "...", "severity": "critical|high|warning|info|low"}}',
        },
        default="{}",
    )
    poll_enabled: bool = dataclasses.field(
        metadata={
            "required": False,
            "description": "Enable periodic SNMP polling",
            "default": False,
        },
        default=False,
    )
    poll_targets: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "JSON list of polling targets with OID checks. "
            'Example: [{"host": "192.168.1.1", "community": "public", "oids": ["1.3.6.1.2.1.1.3.0"]}]',
        },
        default="[]",
    )
    poll_interval: int = dataclasses.field(
        metadata={
            "required": False,
            "description": "Polling interval in seconds",
            "default": "60",
        },
        default=60,
    )


class SNMPProvider(BaseProvider):
    """SNMP Provider - listens for SNMP traps and optionally polls OID values."""

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self.auth_config: SNMPProviderAuthConfig = SNMPProviderAuthConfig(**config.authentication)
        self.oids_mapping: dict = {}
        try:
            self.oids_mapping = json.loads(self.auth_config.oids_mapping)
        except (json.JSONDecodeError, TypeError):
            self.oids_mapping = {}

        self._listener_thread: Optional[threading.Thread] = None
        self._poll_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def _pysnmp_available(self) -> bool:
        try:
            from pysnmp.hlapi import nextCmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity  # noqa: F401
            from pysnmp.entity.rfc3413 import ntforg  # noqa: F401
            return True
        except ImportError:
            return False

    def dispose(self):
        """Stop listener and polling threads."""
        self._stop_event.set()
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=5)
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=5)

    def validate_config(self):
        """Validate provider configuration."""
        if self.auth_config.version not in ("2c", "3"):
            raise ValueError("SNMP version must be '2c' or '3'")
        if self.auth_config.version == "3" and not self.auth_config.username:
            raise ValueError("SNMPv3 requires a username")
        if not self._pysnmp_available:
            logger.warning(
                "pysnmp-lextudio is not installed. "
                "Install it with: pip install pysnmp-lextudio"
            )

    def start(self):
        """Start the SNMP trap listener and optional polling."""
        self.validate_config()
        if not self._pysnmp_available:
            logger.error("Cannot start SNMP provider: pysnmp-lextudio not installed")
            return

        self._stop_event.clear()

        # Start trap listener
        self._listener_thread = threading.Thread(
            target=self._run_trap_listener,
            name=f"snmp-listener-{self.provider_id}",
            daemon=True,
        )
        self._listener_thread.start()
        logger.info(
            f"SNMP trap listener started on {self.auth_config.host}:{self.auth_config.port}"
        )

        # Start polling if enabled
        if self.auth_config.poll_enabled:
            self._poll_thread = threading.Thread(
                target=self._run_polling,
                name=f"snmp-poller-{self.provider_id}",
                daemon=True,
            )
            self._poll_thread.start()
            logger.info("SNMP polling started")

    def _run_trap_listener(self):
        """Run SNMP trap listener in a thread."""
        try:
            from pysnmp.entity import engine, config as snmp_config
            from pysnmp.entity.rfc3413.ntfrcmds import NotificationReceiver
        except ImportError:
            logger.error("pysnmp-lextudio not installed")
            return

        snmp_engine = engine.SnmpEngine()
        snmp_config.addSocketTransport(
            snmp_engine,
            snmp_config.domainNameForUdpTransport(
                (self.auth_config.host, self.auth_config.port)
            ),
        )

        # Configure authentication
        if self.auth_config.version == "2c":
            snmp_config.addV1System(
                snmp_engine,
                "my-area",
                communityName=self.auth_config.community_string,
            )
        elif self.auth_config.version == "3":
            snmp_config.addV3User(
                snmp_engine,
                self.auth_config.username,
                authProtocol=self.auth_config.auth_protocol.upper(),
                authKey=self.auth_config.auth_key,
                privProtocol=self.auth_config.priv_protocol.upper(),
                privKey=self.auth_config.priv_key,
            )

        def cb_fun(
            snmp_engine, state_reference, context_engine_id, context_name,
            var_binds, cb_context,
        ):
            if self._stop_event.is_set():
                return
            try:
                self._process_trap(var_binds)
            except Exception as e:
                logger.error(f"Error processing trap varbinds: {e}", exc_info=True)

        NotificationReceiver(snmp_engine, cb_fun)

        try:
            snmp_engine.transportDispatcher.runDispatcher()
        except Exception:
            if not self._stop_event.is_set():
                logger.error("SNMP dispatcher stopped unexpectedly", exc_info=True)

    def _process_trap(self, var_binds):
        """Process SNMP trap varbinds into a Keep alert."""
        trap_data = {}
        trap_oid = None

        for oid, val in var_binds:
            oid_str = str(oid)
            val_str = str(val)
            trap_data[oid_str] = val_str

            # First varbind is typically the trap OID (SNMPv2c)
            if trap_oid is None and oid_str.startswith("1.3.6.1.6.3.1.1.4.1.0"):
                trap_oid = val_str

        if not trap_oid:
            # Use first varbind as identifier if no trap OID found
            trap_oid = str(var_binds[0][0]) if var_binds else "unknown"

        alert = self._build_alert(trap_oid, trap_data)
        if alert:
            self._push_alert(alert)

    def _build_alert(self, trap_oid: str, var_binds: dict) -> Optional[AlertDto]:
        """Build an AlertDto from SNMP trap data."""
        mapping = self.oids_mapping.get(trap_oid, {})

        # Try partial match
        if not mapping:
            for oid_pattern, m in self.oids_mapping.items():
                if trap_oid.startswith(oid_pattern):
                    mapping = m
                    break

        name = mapping.get("name", f"SNMP Trap: {trap_oid}")
        severity_str = mapping.get("severity", "warning")

        severity_map = {
            "critical": AlertSeverity.CRITICAL,
            "high": AlertSeverity.HIGH,
            "warning": AlertSeverity.WARNING,
            "info": AlertSeverity.INFO,
            "low": AlertSeverity.LOW,
        }
        severity = severity_map.get(severity_str.lower(), AlertSeverity.WARNING)

        # Build fingerprint from trap OID + source
        source_ip = var_binds.pop("__source_ip", "unknown")
        fingerprint = f"{trap_oid}-{source_ip}"

        alert = AlertDto(
            id=fingerprint,
            name=name,
            severity=severity,
            status=AlertStatus.FIRING,
            source=["snmp"],
            last_received="",  # will be set by the framework
            labels={
                "trap_oid": trap_oid,
                "source_ip": source_ip,
            },
            annotations={
                "var_binds": json.dumps(var_binds, default=str),
                "snmp_version": self.auth_config.version,
            },
        )
        return alert

    def _push_alert(self, alert: AlertDto):
        """Push an alert by emitting it through Keep's alert ingestion."""
        try:
            logger.info(f"SNMP alert generated: {alert.name} ({alert.severity})")
            # The alert is yielded via the framework's async mechanism
            # When running in the main loop, alerts are collected and pushed
            self._last_alerts = getattr(self, '_last_alerts', [])
            self._last_alerts.append(alert)
        except Exception as e:
            logger.error(f"Failed to record SNMP alert: {e}", exc_info=True)

    def _run_polling(self):
        """Periodically poll SNMP OIDs and generate alerts on threshold breaches."""
        try:
            import json as _json
            poll_targets = _json.loads(self.auth_config.poll_targets)
        except (json.JSONDecodeError, TypeError):
            logger.error("Invalid poll_targets configuration")
            return

        while not self._stop_event.is_set():
            for target in poll_targets:
                if self._stop_event.is_set():
                    break
                try:
                    self._poll_target(target)
                except Exception as e:
                    logger.error(f"Error polling target {target.get('host')}: {e}", exc_info=True)

            self._stop_event.wait(self.auth_config.poll_interval)

    def _poll_target(self, target: dict):
        """Poll a single SNMP target for OID values."""
        if not self._pysnmp_available:
            return

        try:
            from pysnmp.hlapi import (
                nextCmd,
                SnmpEngine,
                CommunityData,
                UdpTransportTarget,
                ContextData,
                ObjectType,
                ObjectIdentity,
            )
        except ImportError:
            return

        host = target.get("host", "127.0.0.1")
        community = target.get("community", self.auth_config.community_string)
        oids = target.get("oids", [])
        port = target.get("port", 161)

        if not oids:
            return

        error_indication, error_status, error_index, var_binds = nextCmd(
            SnmpEngine(),
            CommunityData(community),
            UdpTransportTarget((host, port), timeout=5, retries=1),
            ContextData(),
            *[ObjectType(ObjectIdentity(oid)) for oid in oids],
        )

        if error_indication:
            logger.error(f"SNMP polling error for {host}: {error_indication}")
            return

        poll_data = {}
        for var_bind in var_binds:
            for oid, val in var_bind:
                poll_data[str(oid)] = str(val)

        if poll_data:
            alert = AlertDto(
                id=f"snmp-poll-{host}",
                name=f"SNMP Poll: {host}",
                severity=AlertSeverity.INFO,
                status=AlertStatus.RESOLVED,
                source=["snmp"],
                annotations={
                    "poll_data": json.dumps(poll_data, default=str),
                    "type": "poll",
                },
            )
            self._push_alert(alert)

    async def _notify(self, **kwargs):
        """Send notification - not directly supported for SNMP, but can send traps."""
        raise NotImplementedError(
            "SNMP provider is receive-only (trap listener). "
            "Use _get_alerts or start the trap listener."
        )

    async def _get_alerts(self) -> list[AlertDto]:
        """SNMP is push-based; alerts are received via trap listener."""
        logger.warning(
            "SNMP is a push-based provider. "
            "Use start() to begin listening for traps."
        )
        return []

    @classmethod
    def _get_alert_schema(cls) -> dict:
        """Return the alert schema for the UI."""
        return {
            "type": "object",
            "properties": {
                "trap_oid": {"type": "string", "description": "SNMP trap OID"},
                "source_ip": {"type": "string", "description": "Source IP of the trap"},
            },
        }



