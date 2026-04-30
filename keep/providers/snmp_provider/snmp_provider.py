"""
SNMP Provider for Keep — receives SNMP traps (push) and polls SNMP devices (pull).

Supports:
  • SNMPv1, v2c, v3 (USM with SHA/MD5 auth + AES/DES privacy)
  • Trap receiver: background UDP listener on configurable port
  • Device polling: GET/WALK IF-MIB interface statuses via bulkCmd
  • Automatic severity mapping from standard trap OIDs
  • Full AlertDto fingerprinting for deduplication
"""

import dataclasses
import datetime
import hashlib
import json
import logging
import threading
import uuid
from typing import Optional

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """Authentication configuration for the SNMP provider."""

    # Trap receiver settings
    listen_port: int = dataclasses.field(
        metadata={
            "required": False,
            "description": "UDP port to listen for incoming SNMP traps",
            "hint": "1162 (use 162 with root/CAP_NET_BIND_SERVICE)",
            "sensitive": False,
        },
        default=1162,
    )
    listen_address: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "IP address to bind the trap listener",
            "hint": "0.0.0.0 (all interfaces)",
            "sensitive": False,
        },
        default="0.0.0.0",
    )

    # SNMPv1/v2c
    community_string: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMP community string for v1/v2c",
            "hint": "public",
            "sensitive": True,
        },
        default="public",
    )
    snmp_version: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMP version to use: 1, 2c, or 3",
            "hint": "2c",
            "sensitive": False,
        },
        default="2c",
    )

    # Pull / polling target (optional)
    target_host: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Hostname or IP of SNMP device to poll (leave blank for trap-only mode)",
            "hint": "192.168.1.1",
            "sensitive": False,
        },
        default="",
    )
    target_port: int = dataclasses.field(
        metadata={
            "required": False,
            "description": "UDP port on target SNMP device",
            "hint": "161",
            "sensitive": False,
        },
        default=161,
    )

    # SNMPv3 USM
    v3_username: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 USM username",
            "sensitive": False,
        },
        default="",
    )
    v3_auth_protocol: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 authentication protocol: SHA or MD5",
            "hint": "SHA",
            "sensitive": False,
        },
        default="SHA",
    )
    v3_auth_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 authentication key (min 8 chars)",
            "sensitive": True,
        },
        default="",
    )
    v3_priv_protocol: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 privacy protocol: AES or DES",
            "hint": "AES",
            "sensitive": False,
        },
        default="AES",
    )
    v3_priv_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 privacy key (min 8 chars)",
            "sensitive": True,
        },
        default="",
    )


class SnmpProvider(BaseProvider):
    """
    Keep provider that ingests SNMP traps and polls SNMP devices.

    Push mode: starts a background UDP listener that converts received traps
    directly to AlertDto objects and forwards them to Keep's alert pipeline.

    Pull mode: when ``target_host`` is set, polls the device's IF-MIB to
    detect interfaces in non-operational states.
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring", "Networking"]
    PROVIDER_TAGS = {"alert"}
    FINGERPRINT_FIELDS = ["host", "trap_oid"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="receive_traps",
            description="Bind a UDP port and receive SNMP trap notifications",
            mandatory=True,
            mandatory_for_webhook=True,
        ),
    ]

    # RFC 1215 standard trap OID → AlertSeverity
    _TRAP_SEVERITY: dict[str, AlertSeverity] = {
        "coldStart": AlertSeverity.WARNING,
        "warmStart": AlertSeverity.INFO,
        "linkDown": AlertSeverity.HIGH,
        "linkUp": AlertSeverity.INFO,
        "authenticationFailure": AlertSeverity.WARNING,
        "egpNeighborLoss": AlertSeverity.HIGH,
    }

    # Standard trap name → AlertStatus
    _TRAP_STATUS: dict[str, AlertStatus] = {
        "linkDown": AlertStatus.FIRING,
        "linkUp": AlertStatus.RESOLVED,
        "coldStart": AlertStatus.FIRING,
        "warmStart": AlertStatus.FIRING,
        "authenticationFailure": AlertStatus.FIRING,
        "egpNeighborLoss": AlertStatus.FIRING,
    }

    # Well-known enterprise OID prefixes → AlertSeverity
    _ENTERPRISE_SEVERITY: dict[str, AlertSeverity] = {
        "1.3.6.1.4.1.9":    AlertSeverity.WARNING,   # Cisco
        "1.3.6.1.4.1.2636": AlertSeverity.WARNING,   # Juniper
        "1.3.6.1.4.1.311":  AlertSeverity.WARNING,   # Microsoft
        "1.3.6.1.4.1.8072": AlertSeverity.INFO,      # Net-SNMP
    }

    # Standard trap OID numeric strings → name
    _STANDARD_TRAP_OIDS: dict[str, str] = {
        "1.3.6.1.6.3.1.1.5.1": "coldStart",
        "1.3.6.1.6.3.1.1.5.2": "warmStart",
        "1.3.6.1.6.3.1.1.5.3": "linkDown",
        "1.3.6.1.6.3.1.1.5.4": "linkUp",
        "1.3.6.1.6.3.1.1.5.5": "authenticationFailure",
        "1.3.6.1.6.3.1.1.5.6": "egpNeighborLoss",
    }

    # snmpTrapOID.0 OID
    _TRAP_OID_VAR = "1.3.6.1.6.3.1.1.4.1.0"

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ) -> None:
        super().__init__(context_manager, provider_id, config)
        self._consumer_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._snmp_engine = None

    # ------------------------------------------------------------------
    # BaseProvider interface
    # ------------------------------------------------------------------

    def validate_config(self) -> None:
        """Instantiate and validate the pydantic authentication config."""
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """Verify we can bind to the configured UDP port."""
        import socket

        validated: dict[str, bool | str] = {}
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(
                (
                    self.authentication_config.listen_address,
                    self.authentication_config.listen_port,
                )
            )
            sock.close()
            validated["receive_traps"] = True
        except OSError as exc:
            validated["receive_traps"] = str(exc)
        return validated

    def dispose(self) -> None:
        """Cleanly stop the trap listener background thread."""
        self._stop_event.set()
        if self._consumer_thread and self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=5)

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull mode: poll target SNMP device for interface statuses.
        Returns an empty list when no ``target_host`` is configured.
        """
        if not self.authentication_config.target_host:
            return []
        return self._poll_device()

    # ------------------------------------------------------------------
    # Push mode — trap receiver
    # ------------------------------------------------------------------

    def _start_consumer(self) -> None:
        """Launch the background UDP trap receiver thread."""
        self._stop_event.clear()
        self._consumer_thread = threading.Thread(
            target=self._trap_listener_loop,
            name=f"snmp-trap-{self.provider_id}",
            daemon=True,
        )
        self._consumer_thread.start()
        self.logger.info(
            "SNMP trap listener started on %s:%d",
            self.authentication_config.listen_address,
            self.authentication_config.listen_port,
        )

    def _trap_listener_loop(self) -> None:
        """
        Background loop: bind UDP socket and process incoming SNMP traps.
        Runs until ``_stop_event`` is set.
        """
        try:
            from pysnmp.carrier.asyncore.dgram import udp
            from pysnmp.entity import config as snmp_config
            from pysnmp.entity import engine as snmp_engine_mod
            from pysnmp.entity.rfc3413 import ntfrcv
        except ImportError:
            self.logger.error(
                "pysnmp-lextudio is not installed. "
                "Run: pip install pysnmp-lextudio"
            )
            return

        snmp_engine = snmp_engine_mod.SnmpEngine()
        self._snmp_engine = snmp_engine

        # Bind transport
        snmp_config.addTransport(
            snmp_engine,
            udp.domainName + (1,),
            udp.UdpSocketTransport().openServerMode(
                (
                    self.authentication_config.listen_address,
                    self.authentication_config.listen_port,
                )
            ),
        )

        # v1/v2c community
        snmp_config.addV1System(
            snmp_engine,
            "keep-snmp-ro",
            self.authentication_config.community_string,
        )

        # SNMPv3 USM
        if self.authentication_config.v3_username:
            self._configure_v3_receiver(snmp_engine, snmp_config)

        def _cb(snmp_engine, state_ref, ctx_engine_id, ctx_name, var_binds, cb_ctx):  # noqa
            try:
                transport_domain, transport_address = (
                    snmp_engine.msgAndPduDsp.getTransportInfo(state_ref)
                )
                source_ip = str(transport_address[0])
                self._process_trap(source_ip, var_binds)
            except Exception:
                self.logger.exception("Error processing SNMP trap")

        ntfrcv.NotificationReceiver(snmp_engine, _cb)
        snmp_engine.transportDispatcher.jobStarted(1)

        try:
            while not self._stop_event.is_set():
                snmp_engine.transportDispatcher.runDispatcher(timeout=1.0)
        except Exception:
            self.logger.exception("SNMP dispatcher exited with error")
        finally:
            try:
                snmp_engine.transportDispatcher.closeDispatcher()
            except Exception:
                pass

    def _configure_v3_receiver(self, snmp_engine, snmp_config) -> None:
        """Register SNMPv3 USM user for the trap receiver."""
        from pysnmp.entity import config as sc

        cfg = self.authentication_config
        auth_proto = sc.usmHMACSHAAuthProtocol if cfg.v3_auth_protocol.upper() == "SHA" \
            else sc.usmHMACMD5AuthProtocol
        priv_proto = sc.usmAesCfb128Protocol if cfg.v3_priv_protocol.upper() == "AES" \
            else sc.usmDESPrivProtocol

        sc.addV3User(
            snmp_engine,
            cfg.v3_username,
            authProtocol=auth_proto if cfg.v3_auth_key else sc.usmNoAuthProtocol,
            authKey=cfg.v3_auth_key or None,
            privProtocol=priv_proto if cfg.v3_priv_key else sc.usmNoPrivProtocol,
            privKey=cfg.v3_priv_key or None,
        )

    def _process_trap(self, source_ip: str, var_binds) -> None:
        """Parse raw trap varbinds and push resulting alerts into Keep."""
        trap_oid: Optional[str] = None
        varbind_dict: dict[str, str] = {}

        for oid, val in var_binds:
            oid_str = str(oid)
            val_str = str(val)
            if oid_str == self._TRAP_OID_VAR:
                trap_oid = val_str
            else:
                varbind_dict[oid_str] = val_str

        trap_name = self._resolve_oid_name(trap_oid or "unknown")

        event = {
            "host": source_ip,
            "trap_oid": trap_oid or "unknown",
            "trap_name": trap_name,
            "varbinds": varbind_dict,
            "snmp_version": self.authentication_config.snmp_version,
            "timestamp": datetime.datetime.now(
                tz=datetime.timezone.utc
            ).isoformat(),
        }

        for alert in self._format_alert(event, provider_instance=self):
            self._push_alert(alert)

    # ------------------------------------------------------------------
    # Pull mode — SNMP GET/WALK
    # ------------------------------------------------------------------

    def _poll_device(self) -> list[AlertDto]:
        """Poll IF-MIB interface statuses on the configured target device."""
        try:
            from pysnmp.hlapi import (
                ContextData,
                ObjectIdentity,
                ObjectType,
                SnmpEngine,
                UdpTransportTarget,
                bulkCmd,
            )
        except ImportError:
            self.logger.warning("pysnmp-lextudio not installed; skipping poll")
            return []

        auth = self._build_poll_auth()
        transport = UdpTransportTarget(
            (
                self.authentication_config.target_host,
                self.authentication_config.target_port,
            ),
            timeout=5,
            retries=2,
        )

        alerts: list[AlertDto] = []
        try:
            for error_indication, error_status, _error_index, var_binds in bulkCmd(
                SnmpEngine(),
                auth,
                transport,
                ContextData(),
                0,
                25,
                ObjectType(ObjectIdentity("IF-MIB", "ifDescr")),
                ObjectType(ObjectIdentity("IF-MIB", "ifOperStatus")),
                lexicographicMode=False,
            ):
                if error_indication:
                    self.logger.warning("SNMP poll error: %s", error_indication)
                    break
                if error_status:
                    self.logger.warning("SNMP PDU error: %s", error_status)
                    break

                # bulkCmd returns pairs of (ifDescr, ifOperStatus) varbinds
                for i in range(0, len(var_binds), 2):
                    if i + 1 >= len(var_binds):
                        break
                    if_name = str(var_binds[i][1])
                    if_oper_status = int(var_binds[i + 1][1])

                    # ifOperStatus: 1=up, everything else is noteworthy
                    if if_oper_status == 1:
                        continue

                    severity = (
                        AlertSeverity.HIGH
                        if if_oper_status == 2
                        else AlertSeverity.WARNING
                    )
                    status_name = {2: "down", 3: "testing", 7: "lowerLayerDown"}.get(
                        if_oper_status, f"status-{if_oper_status}"
                    )
                    trap_key = f"if.{if_name}.{status_name}"

                    alerts.append(
                        AlertDto(
                            id=str(uuid.uuid4()),
                            name=f"Interface {if_name} {status_name}",
                            description=(
                                f"Interface {if_name} on "
                                f"{self.authentication_config.target_host} "
                                f"is {status_name} (ifOperStatus={if_oper_status})"
                            ),
                            status=AlertStatus.FIRING,
                            severity=severity,
                            lastReceived=datetime.datetime.now(
                                tz=datetime.timezone.utc
                            ).isoformat(),
                            source=["snmp"],
                            labels={
                                "host": self.authentication_config.target_host,
                                "interface": if_name,
                                "if_oper_status": str(if_oper_status),
                            },
                            environment="production",
                            fingerprint=self._compute_fingerprint(
                                self.authentication_config.target_host, trap_key
                            ),
                        )
                    )
        except Exception:
            self.logger.exception(
                "Failed to poll SNMP device %s",
                self.authentication_config.target_host,
            )

        return alerts

    def _build_poll_auth(self):
        """Build pysnmp auth data for pull-mode polling."""
        from pysnmp.hlapi import (
            CommunityData,
            UsmUserData,
            usmAesCfb128Protocol,
            usmDESPrivProtocol,
            usmHMACMD5AuthProtocol,
            usmHMACSHAAuthProtocol,
            usmNoAuthProtocol,
            usmNoPrivProtocol,
        )

        cfg = self.authentication_config
        if cfg.snmp_version == "3":
            auth_proto = (
                usmHMACSHAAuthProtocol
                if cfg.v3_auth_protocol.upper() == "SHA"
                else usmHMACMD5AuthProtocol
            )
            priv_proto = (
                usmAesCfb128Protocol
                if cfg.v3_priv_protocol.upper() == "AES"
                else usmDESPrivProtocol
            )
            return UsmUserData(
                cfg.v3_username,
                authKey=cfg.v3_auth_key or None,
                privKey=cfg.v3_priv_key or None,
                authProtocol=auth_proto if cfg.v3_auth_key else usmNoAuthProtocol,
                privProtocol=priv_proto if cfg.v3_priv_key else usmNoPrivProtocol,
            )

        mp_model = 0 if cfg.snmp_version == "1" else 1
        return CommunityData(cfg.community_string, mpModel=mp_model)

    # ------------------------------------------------------------------
    # Alert formatting (called by both push and pull paths)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(
        event: dict,
        provider_instance: "BaseProvider | None" = None,
    ) -> list[AlertDto]:
        """
        Convert a normalised SNMP trap/poll event dict to ``AlertDto`` list.

        ``event`` keys:
          host         — source IP of trap sender or polled device
          trap_oid     — resolved OID string (numeric or name)
          trap_name    — human-readable trap name
          varbinds     — dict mapping OID name/number to value
          snmp_version — "v1" | "v2c" | "v3"
          timestamp    — ISO-8601 string or ``None`` (defaults to now)
          environment  — optional alert environment label
        """
        host = event.get("host", "unknown")
        trap_oid = event.get("trap_oid", "unknown")
        trap_name = event.get("trap_name", trap_oid)
        varbinds: dict = event.get("varbinds", {})
        snmp_version = event.get("snmp_version", "v2c")
        environment = event.get("environment", "production")
        timestamp = event.get("timestamp") or datetime.datetime.now(
            tz=datetime.timezone.utc
        ).isoformat()

        # Severity: standard map → enterprise prefix fallback → WARNING
        severity = SnmpProvider._TRAP_SEVERITY.get(trap_name)
        if severity is None:
            for prefix, sev in SnmpProvider._ENTERPRISE_SEVERITY.items():
                if trap_oid.startswith(prefix):
                    severity = sev
                    break
            else:
                severity = AlertSeverity.WARNING

        status = SnmpProvider._TRAP_STATUS.get(trap_name, AlertStatus.FIRING)

        varbind_str = "; ".join(f"{k}={v}" for k, v in varbinds.items())
        description = f"SNMP {snmp_version} trap from {host}: {trap_name}"
        if varbind_str:
            description += f" — {varbind_str}"

        fingerprint = SnmpProvider._compute_fingerprint_static(host, trap_oid)

        return [
            AlertDto(
                id=event.get("id") or str(uuid.uuid4()),
                name=trap_name,
                description=description,
                status=status,
                severity=severity,
                lastReceived=timestamp,
                source=["snmp"],
                labels={
                    "host": host,
                    "trap_oid": trap_oid,
                    "snmp_version": snmp_version,
                    **{str(k): str(v) for k, v in varbinds.items()},
                },
                environment=environment,
                fingerprint=fingerprint,
                message=varbind_str or None,
            )
        ]

    # ------------------------------------------------------------------
    # Alert simulation (Keep UI "simulate alert" button)
    # ------------------------------------------------------------------

    @classmethod
    def simulate_alert(cls, **kwargs) -> dict:
        """Return a realistic SNMP trap payload for Keep's alert simulator."""
        import random
        from keep.providers.snmp_provider.alerts_mock import ALERTS

        alert_type = kwargs.get("alert_type") or random.choice(list(ALERTS.keys()))
        template = ALERTS.get(alert_type, ALERTS["linkDown"])
        payload: dict = dict(template["payload"])

        for param, options in template.get("parameters", {}).items():
            payload[param] = random.choice(options)

        payload["timestamp"] = datetime.datetime.now(
            tz=datetime.timezone.utc
        ).isoformat()
        return payload

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_oid_name(oid: str) -> str:
        """Resolve a numeric OID to its human-readable name; fallback to raw OID."""
        return SnmpProvider._STANDARD_TRAP_OIDS.get(oid, oid)

    @staticmethod
    def _compute_fingerprint_static(host: str, trap_oid: str) -> str:
        src = json.dumps({"host": host, "trap_oid": trap_oid}, sort_keys=True)
        return hashlib.sha256(src.encode()).hexdigest()

    def _compute_fingerprint(self, host: str, trap_oid: str) -> str:
        return self._compute_fingerprint_static(host, trap_oid)
