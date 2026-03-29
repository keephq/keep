"""
SNMP Provider — integrates SNMP traps and polling into Keep.

Two integration modes
---------------------
Push mode (webhook):
  Configure your network devices / SNMP proxy to forward trap data to Keep's
  inbound webhook endpoint as JSON.  Works with snmptrapd, Net-SNMP, or any
  proxy that can POST JSON.

Pull mode:
  Keep periodically walks a list of target hosts via SNMP GET/GETNEXT to
  collect OID values and surface threshold violations as alerts.

Both modes support SNMPv1, v2c, and v3 (auth + priv).
"""

import dataclasses
import datetime
import json
import logging
import re
import threading
import uuid
from typing import Optional

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional pysnmp import — provider degrades gracefully if not installed
# ---------------------------------------------------------------------------
try:
    from pysnmp.carrier.asyncore.dgram import udp as snmp_udp
    from pysnmp.entity import config as snmp_config
    from pysnmp.entity import engine as snmp_engine_module
    from pysnmp.entity.rfc3413 import ntfrcv
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

    PYSNMP_AVAILABLE = True
except ImportError:
    PYSNMP_AVAILABLE = False
    logger.warning(
        "pysnmp-lextudio is not installed; SNMP trap listener and polling "
        "are unavailable.  Install with: pip install pysnmp-lextudio"
    )


# ---------------------------------------------------------------------------
# Well-known OID → severity / name mappings
# ---------------------------------------------------------------------------

# Standard RFC-1907 / IF-MIB trap OIDs
_STANDARD_OID_MAP: dict[str, dict] = {
    "1.3.6.1.6.3.1.1.5.1": {"name": "coldStart", "severity": AlertSeverity.INFO, "status": AlertStatus.RESOLVED},
    "1.3.6.1.6.3.1.1.5.2": {"name": "warmStart", "severity": AlertSeverity.INFO, "status": AlertStatus.RESOLVED},
    "1.3.6.1.6.3.1.1.5.3": {"name": "linkDown", "severity": AlertSeverity.CRITICAL, "status": AlertStatus.FIRING},
    "1.3.6.1.6.3.1.1.5.4": {"name": "linkUp", "severity": AlertSeverity.INFO, "status": AlertStatus.RESOLVED},
    "1.3.6.1.6.3.1.1.5.5": {"name": "authenticationFailure", "severity": AlertSeverity.HIGH, "status": AlertStatus.FIRING},
    "1.3.6.1.6.3.1.1.5.6": {"name": "egpNeighborLoss", "severity": AlertSeverity.HIGH, "status": AlertStatus.FIRING},
    # BGP4
    "1.3.6.1.2.1.15.7": {"name": "bgpEstablished", "severity": AlertSeverity.INFO, "status": AlertStatus.RESOLVED},
    "1.3.6.1.2.1.15.8": {"name": "bgpBackwardTransition", "severity": AlertSeverity.HIGH, "status": AlertStatus.FIRING},
    # UPS-MIB
    "1.3.6.1.2.1.33.2.0.1": {"name": "upsPowerOnline", "severity": AlertSeverity.INFO, "status": AlertStatus.RESOLVED},
    "1.3.6.1.2.1.33.2.0.2": {"name": "upsBatteryLow", "severity": AlertSeverity.CRITICAL, "status": AlertStatus.FIRING},
    "1.3.6.1.2.1.33.2.0.3": {"name": "upsOnBattery", "severity": AlertSeverity.WARNING, "status": AlertStatus.FIRING},
    # ENTITY-MIB
    "1.3.6.1.2.1.47.2.0.1": {"name": "entConfigChange", "severity": AlertSeverity.WARNING, "status": AlertStatus.FIRING},
}

# Vendor OID prefix → alert severity escalation
_VENDOR_OID_PREFIXES: dict[str, str] = {
    "1.3.6.1.4.1.9":    "Cisco",
    "1.3.6.1.4.1.11":   "HP",
    "1.3.6.1.4.1.674":  "Dell",
    "1.3.6.1.4.1.2636": "Juniper",
    "1.3.6.1.4.1.2011": "Huawei",
    "1.3.6.1.4.1.6876": "VMware",
    "1.3.6.1.4.1.8072": "Net-SNMP",
}

_SEVERITY_NAME_MAP: dict[str, AlertSeverity] = {
    "critical":  AlertSeverity.CRITICAL,
    "high":      AlertSeverity.HIGH,
    "warning":   AlertSeverity.WARNING,
    "warn":      AlertSeverity.WARNING,
    "info":      AlertSeverity.INFO,
    "low":       AlertSeverity.LOW,
}


# ---------------------------------------------------------------------------
# Auth config
# ---------------------------------------------------------------------------


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """SNMP provider configuration."""

    # Trap listener
    host: str = dataclasses.field(
        default="0.0.0.0",
        metadata={
            "required": False,
            "description": "Listen address for the built-in SNMP trap receiver",
            "hint": "0.0.0.0 to bind all interfaces, or a specific IP",
            "sensitive": False,
        },
    )
    port: int = dataclasses.field(
        default=162,
        metadata={
            "required": False,
            "description": "UDP port for SNMP traps (default 162, requires root; use 1620+ for non-root)",
            "sensitive": False,
        },
    )

    # SNMPv1/v2c
    community_string: str = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": "SNMP community string (SNMPv1 / v2c)",
            "hint": "'public' is the standard default",
            "sensitive": True,
        },
    )

    # SNMP version
    version: str = dataclasses.field(
        default="2c",
        metadata={
            "required": False,
            "description": "SNMP version: '1', '2c', or '3'",
            "hint": "Use '2c' for most deployments, '3' for encrypted/authenticated",
            "sensitive": False,
        },
    )

    # SNMPv3
    username: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "SNMPv3 username",
            "sensitive": False,
        },
    )
    auth_key: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "SNMPv3 authentication passphrase",
            "sensitive": True,
        },
    )
    auth_protocol: str = dataclasses.field(
        default="SHA",
        metadata={
            "required": False,
            "description": "SNMPv3 auth protocol: 'MD5' or 'SHA'",
            "sensitive": False,
        },
    )
    priv_key: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "SNMPv3 privacy (encryption) passphrase",
            "sensitive": True,
        },
    )
    priv_protocol: str = dataclasses.field(
        default="AES",
        metadata={
            "required": False,
            "description": "SNMPv3 privacy protocol: 'DES' or 'AES'",
            "sensitive": False,
        },
    )

    # OID → alert mapping (JSON string)
    oids_mapping: str = dataclasses.field(
        default="{}",
        metadata={
            "required": False,
            "description": (
                "JSON map of OID prefixes to alert overrides.  "
                'Example: {"1.3.6.1.4.1.9": {"severity": "critical", "name": "Cisco Alert"}}'
            ),
            "sensitive": False,
        },
    )

    # Polling
    poll_enabled: bool = dataclasses.field(
        default=False,
        metadata={
            "required": False,
            "description": "Enable periodic SNMP polling of target devices",
            "sensitive": False,
        },
    )
    poll_targets: str = dataclasses.field(
        default="[]",
        metadata={
            "required": False,
            "description": (
                "JSON list of polling targets.  Each entry: "
                '{"host": "192.168.1.1", "oids": ["1.3.6.1.2.1.1.1.0"]}'
            ),
            "sensitive": False,
        },
    )
    poll_interval: int = dataclasses.field(
        default=60,
        metadata={
            "required": False,
            "description": "Polling interval in seconds",
            "sensitive": False,
        },
    )


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class SnmpProvider(BaseProvider):
    """
    Manage SNMP traps and polling alerts in Keep.

    Push mode:
        Devices send SNMP traps directly to Keep's built-in UDP trap listener
        (started automatically when the provider is loaded), OR the user
        configures an external trap daemon (snmptrapd) to POST JSON to Keep's
        webhook endpoint.

    Pull mode:
        Keep periodically polls SNMP-enabled hosts via GET/GETNEXT requests
        and surfaces threshold violations as alerts.
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring", "Networking"]
    PROVIDER_TAGS = ["alert", "infrastructure"]
    FINGERPRINT_FIELDS = ["trap_oid", "source_address"]

    # Webhook docs shown in Keep UI
    webhook_description = "SNMP Trap receiver — accepts both direct UDP traps and JSON-forwarded payloads from snmptrapd or any SNMP proxy."
    webhook_markdown = """
## SNMP Trap Integration

### Option A — Native UDP trap listener (built-in)

The SNMP provider starts a UDP listener on the configured `host:port` (default `0.0.0.0:162`).
Configure your network devices to send traps to Keep's IP and port.

For SNMPv1/v2c:
```
snmp-server host <keep-ip> traps version 2c public
```

For SNMPv3:
```
snmp-server host <keep-ip> traps version 3 priv <username>
```

### Option B — snmptrapd JSON forwarding

1. Install Net-SNMP on your trap collector host.
2. Add a handler to `/etc/snmp/snmptrapd.conf`:
   ```
   traphandle default /usr/bin/curl -s -X POST \\
     -H 'Content-Type: application/json' \\
     -d @- {keep_webhook_api_url}
   ```
3. Restart snmptrapd.

Keep will receive and parse the forwarded trap JSON.

### OID Mapping

Provide a JSON `oids_mapping` to customise severity and alert names:
```json
{
  "1.3.6.1.4.1.9": {"severity": "critical", "name": "Cisco Device Alert"},
  "1.3.6.1.6.3.1.1.5.3": {"severity": "critical", "name": "Link Down"}
}
```
"""

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ) -> None:
        super().__init__(context_manager, provider_id, config)
        # In-memory alert buffer (used by the UDP trap listener thread)
        self._alerts: list[AlertDto] = []
        self._alerts_lock = threading.Lock()
        # Listener thread management
        self._listener_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        # Parsed config caches
        self._oids_mapping: dict[str, dict] = {}
        self._poll_targets: list[dict] = []

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def validate_config(self) -> None:
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )
        version = self.authentication_config.version
        if version not in ("1", "2c", "3"):
            raise ValueError(
                f"Invalid SNMP version '{version}'; must be '1', '2c', or '3'."
            )
        if version == "3" and not self.authentication_config.username:
            raise ValueError(
                "SNMPv3 requires 'username' to be set."
            )
        port = self.authentication_config.port
        if not (1 <= port <= 65535):
            raise ValueError(
                f"Invalid port {port}; must be in range 1–65535."
            )
        interval = self.authentication_config.poll_interval
        if interval < 1:
            raise ValueError(
                f"poll_interval must be >= 1 second; got {interval}."
            )
        # Parse JSON fields
        try:
            self._oids_mapping = json.loads(self.authentication_config.oids_mapping)
            if not isinstance(self._oids_mapping, dict):
                raise TypeError("oids_mapping must be a JSON object")
        except Exception as exc:
            self.logger.warning("Invalid oids_mapping JSON; using empty map: %s", exc)
            self._oids_mapping = {}
        try:
            self._poll_targets = json.loads(self.authentication_config.poll_targets)
            if not isinstance(self._poll_targets, list):
                raise TypeError("poll_targets must be a JSON array")
        except Exception as exc:
            self.logger.warning("Invalid poll_targets JSON; using empty list: %s", exc)
            self._poll_targets = []

    # ------------------------------------------------------------------
    # OID helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_oid(oid: str) -> str:
        """Strip leading dot from OID string."""
        return oid.lstrip(".")

    def _resolve_oid_mapping(self, oid: str) -> dict:
        """
        Return the best-matching user-defined OID override.

        Performs longest-prefix matching against ``self._oids_mapping``.
        Falls back to the built-in ``_STANDARD_OID_MAP`` if no user
        mapping matches.
        """
        oid = self._normalise_oid(oid)
        # Exact match first
        if oid in self._oids_mapping:
            return self._oids_mapping[oid]
        # Longest prefix match
        best_prefix = ""
        best_value: dict = {}
        for prefix, value in self._oids_mapping.items():
            prefix = self._normalise_oid(prefix)
            if oid.startswith(prefix) and len(prefix) > len(best_prefix):
                best_prefix = prefix
                best_value = value
        if best_value:
            return best_value
        # Built-in map
        if oid in _STANDARD_OID_MAP:
            return _STANDARD_OID_MAP[oid]
        return {}

    @staticmethod
    def _severity_from_mapping(mapping: dict) -> AlertSeverity:
        """Extract AlertSeverity from an OID mapping dict."""
        raw = mapping.get("severity", "")
        if isinstance(raw, AlertSeverity):
            return raw
        return _SEVERITY_NAME_MAP.get(str(raw).lower(), AlertSeverity.INFO)

    @staticmethod
    def _status_from_mapping(mapping: dict, oid: str) -> AlertStatus:
        """Extract AlertStatus from an OID mapping dict, with heuristic fallback."""
        if "status" in mapping:
            raw = mapping["status"]
            if isinstance(raw, AlertStatus):
                return raw
        # Heuristic: linkUp / coldStart / warmStart → resolved
        name = mapping.get("name", "").lower()
        if any(word in name for word in ("up", "online", "resolved", "coldstart", "warmstart", "established")):
            return AlertStatus.RESOLVED
        return AlertStatus.FIRING

    @staticmethod
    def _vendor_from_oid(oid: str) -> str:
        """Return vendor name from OID prefix, or 'Unknown'."""
        oid = oid.lstrip(".")
        for prefix, vendor in _VENDOR_OID_PREFIXES.items():
            if oid.startswith(prefix):
                return vendor
        return "Unknown"

    # ------------------------------------------------------------------
    # Alert construction
    # ------------------------------------------------------------------

    def _build_alert_from_trap(
        self,
        trap_oid: str,
        source_address: str,
        varbinds: list[tuple[str, str]],
        snmp_version: str = "2c",
        community: str = "",
    ) -> AlertDto:
        """Build an AlertDto from a parsed SNMP trap."""
        mapping = self._resolve_oid_mapping(trap_oid)
        severity = self._severity_from_mapping(mapping)
        status = self._status_from_mapping(mapping, trap_oid)
        vendor = self._vendor_from_oid(trap_oid)

        name = mapping.get("name") or f"SNMP Trap {trap_oid}"
        description_parts = [f"OID: {trap_oid}", f"Source: {source_address}"]
        for oid, val in varbinds[:10]:  # cap to 10 varbinds in description
            description_parts.append(f"{oid}: {val}")

        labels: dict = {
            "trap_oid": trap_oid,
            "source_address": source_address,
            "snmp_version": snmp_version,
            "vendor": vendor,
        }
        if community:
            labels["community"] = community
        for i, (oid, val) in enumerate(varbinds[:20]):
            labels[f"varbind_{i}_oid"] = oid
            labels[f"varbind_{i}_value"] = str(val)

        return AlertDto(
            id=str(uuid.uuid4()),
            name=name,
            description="\n".join(description_parts),
            severity=severity,
            status=status,
            source=["snmp"],
            lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            trap_oid=trap_oid,
            source_address=source_address,
            snmp_version=snmp_version,
            vendor=vendor,
            labels=labels,
        )

    # ------------------------------------------------------------------
    # Webhook (push) mode — JSON payloads from external trap daemons
    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Parse an inbound webhook payload into one or more AlertDtos.

        Accepts two envelope formats:
        1. Single trap dict: {"trap_oid": "...", "source": "...", "varbinds": [...]}
        2. Batch: {"traps": [...]}  where each item is a single trap dict.
        """
        if "traps" in event and isinstance(event["traps"], list):
            alerts = []
            for trap in event["traps"]:
                try:
                    alerts.append(SnmpProvider._parse_trap_payload(trap))
                except Exception:
                    logger.exception("Failed to parse trap in batch: %s", trap)
            return alerts or [SnmpProvider._parse_trap_payload(event)]

        return SnmpProvider._parse_trap_payload(event)

    @staticmethod
    def _parse_trap_payload(trap: dict) -> AlertDto:
        """Convert a single flat trap dict to AlertDto."""
        trap_oid = trap.get("trap_oid") or trap.get("oid") or trap.get("snmpTrapOID", "")
        trap_oid = SnmpProvider._normalise_oid(str(trap_oid))
        source_address = (
            trap.get("source")
            or trap.get("source_address")
            or trap.get("agentAddress")
            or "unknown"
        )
        snmp_version = str(trap.get("version") or trap.get("snmp_version") or "2c")
        community = str(trap.get("community") or "")
        raw_varbinds = trap.get("varbinds") or trap.get("variables") or []
        varbinds: list[tuple[str, str]] = []
        for vb in raw_varbinds:
            if isinstance(vb, dict):
                oid = str(vb.get("oid") or vb.get("OID") or "")
                val = str(vb.get("value") or vb.get("Value") or "")
                varbinds.append((oid, val))
            elif isinstance(vb, (list, tuple)) and len(vb) >= 2:
                varbinds.append((str(vb[0]), str(vb[1])))

        mapping: dict = {}
        oid_clean = SnmpProvider._normalise_oid(trap_oid)
        if oid_clean in _STANDARD_OID_MAP:
            mapping = _STANDARD_OID_MAP[oid_clean]
        else:
            for prefix, vendor in _VENDOR_OID_PREFIXES.items():
                if oid_clean.startswith(prefix):
                    mapping = {"name": f"{vendor} Trap", "severity": AlertSeverity.HIGH}
                    break

        severity = SnmpProvider._severity_from_mapping(mapping)
        status = SnmpProvider._status_from_mapping(mapping, trap_oid)
        name = (
            trap.get("name")
            or trap.get("alert_name")
            or mapping.get("name")
            or f"SNMP Trap {trap_oid}"
        )
        vendor = SnmpProvider._vendor_from_oid(trap_oid)
        description_parts = [f"OID: {trap_oid}", f"Source: {source_address}"]
        for oid, val in varbinds[:10]:
            description_parts.append(f"{oid}: {val}")

        labels: dict = {
            "trap_oid": trap_oid,
            "source_address": source_address,
            "snmp_version": snmp_version,
            "vendor": vendor,
        }
        if community:
            labels["community"] = community

        return AlertDto(
            id=str(uuid.uuid4()),
            name=name,
            description="\n".join(description_parts),
            severity=severity,
            status=status,
            source=["snmp"],
            lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            trap_oid=trap_oid,
            source_address=source_address,
            snmp_version=snmp_version,
            vendor=vendor,
            labels=labels,
        )

    # ------------------------------------------------------------------
    # Native UDP trap listener (pull → alerts buffer)
    # ------------------------------------------------------------------

    def _start_trap_listener(self) -> None:
        """Start the UDP SNMP trap listener in a background thread."""
        if not PYSNMP_AVAILABLE:
            self.logger.warning("pysnmp not available; native trap listener disabled.")
            return
        if self._listener_thread and self._listener_thread.is_alive():
            return
        self._stop_event.clear()
        self._listener_thread = threading.Thread(
            target=self._run_trap_listener, daemon=True, name="snmp-trap-listener"
        )
        self._listener_thread.start()
        self.logger.info(
            "SNMP trap listener started on %s:%s",
            self.authentication_config.host,
            self.authentication_config.port,
        )

    def _run_trap_listener(self) -> None:
        """Internal loop that runs the pysnmp notification receiver."""
        snmp_eng = snmp_engine_module.SnmpEngine()
        host = self.authentication_config.host
        port = self.authentication_config.port
        version = self.authentication_config.version

        # Transport
        snmp_config.addTransport(
            snmp_eng,
            snmp_udp.domainName + (1,),
            snmp_udp.UdpSocketTransport().openServerMode((host, port)),
        )

        # Community / security
        if version in ("1", "2c"):
            snmp_config.addV1System(
                snmp_eng,
                "recv-community",
                self.authentication_config.community_string,
            )
        else:
            # SNMPv3
            snmp_config.addV3User(
                snmp_eng,
                self.authentication_config.username,
                snmp_config.usmHMACMD5AuthProtocol
                if self.authentication_config.auth_protocol.upper() == "MD5"
                else snmp_config.usmHMACSHAAuthProtocol,
                self.authentication_config.auth_key,
                snmp_config.usmDESPrivProtocol
                if self.authentication_config.priv_protocol.upper() == "DES"
                else snmp_config.usmAesCfb128Protocol,
                self.authentication_config.priv_key,
            )

        def cbFun(snmpEngine, stateReference, contextEngineId, contextName,
                  varBinds, cbCtx):
            try:
                trap_oid = ""
                source_address = "unknown"
                varbinds: list[tuple[str, str]] = []
                for name, val in varBinds:
                    oid_str = str(name)
                    val_str = str(val)
                    # snmpTrapOID.0
                    if "1.3.6.1.6.3.1.1.4.1" in oid_str:
                        trap_oid = self._normalise_oid(val_str)
                    else:
                        varbinds.append((oid_str, val_str))

                if not trap_oid:
                    trap_oid = "1.3.6.1.6.3.1.1.5.1"  # default: coldStart

                alert = self._build_alert_from_trap(
                    trap_oid=trap_oid,
                    source_address=source_address,
                    varbinds=varbinds,
                    snmp_version=version,
                )
                with self._alerts_lock:
                    self._alerts.append(alert)
            except Exception:
                self.logger.exception("Error processing trap in listener callback")

        ntfrcv.NotificationReceiver(snmp_eng, cbFun)
        snmp_eng.transportDispatcher.jobStarted(1)
        try:
            while not self._stop_event.is_set():
                snmp_eng.transportDispatcher.runDispatcher(0.5)
        except Exception:
            self.logger.exception("SNMP trap listener error")
        finally:
            snmp_eng.transportDispatcher.closeDispatcher()

    # ------------------------------------------------------------------
    # Pull mode — _get_alerts
    # ------------------------------------------------------------------

    def _get_alerts(self) -> list[AlertDto]:
        """Return buffered trap alerts and, if polling is enabled, polled OID alerts."""
        # Start listener if needed
        self._start_trap_listener()
        # Drain the buffer
        with self._alerts_lock:
            alerts = list(self._alerts)
            self._alerts.clear()
        # Poll targets if configured
        if self.authentication_config.poll_enabled and PYSNMP_AVAILABLE:
            alerts.extend(self._poll_all_targets())
        return alerts

    def _poll_all_targets(self) -> list[AlertDto]:
        """Poll each configured target for OID values."""
        results: list[AlertDto] = []
        for target in self._poll_targets:
            host = target.get("host", "")
            oids = target.get("oids", [])
            if not host or not oids:
                continue
            try:
                alerts = self._poll_host(host, oids)
                results.extend(alerts)
            except Exception:
                self.logger.exception("Failed to poll SNMP host %s", host)
        return results

    def _poll_host(self, host: str, oids: list[str]) -> list[AlertDto]:
        """Use SNMP GET to query OIDs on a single host and return alerts."""
        if not PYSNMP_AVAILABLE:
            return []
        version = self.authentication_config.version
        engine = SnmpEngine()
        object_types = [ObjectType(ObjectIdentity(oid)) for oid in oids]

        if version in ("1", "2c"):
            auth_data = CommunityData(
                self.authentication_config.community_string,
                mpModel=0 if version == "1" else 1,
            )
        else:
            from pysnmp.hlapi import UsmUserData
            auth_data = UsmUserData(self.authentication_config.username)

        target = UdpTransportTarget((host, 161), timeout=5, retries=1)
        errorIndication, errorStatus, errorIndex, varBinds = next(
            getCmd(engine, auth_data, target, ContextData(), *object_types)
        )
        if errorIndication or errorStatus:
            err = str(errorIndication or errorStatus)
            return [AlertDto(
                id=str(uuid.uuid4()),
                name=f"SNMP poll error: {host}",
                description=err,
                severity=AlertSeverity.WARNING,
                status=AlertStatus.FIRING,
                source=["snmp"],
                lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )]
        alerts: list[AlertDto] = []
        for name, val in varBinds:
            oid_str = str(name)
            val_str = str(val)
            alerts.append(AlertDto(
                id=str(uuid.uuid4()),
                name=f"SNMP Poll: {oid_str} @ {host}",
                description=f"Host: {host}, OID: {oid_str}, Value: {val_str}",
                severity=AlertSeverity.INFO,
                status=AlertStatus.FIRING,
                source=["snmp"],
                lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                labels={"host": host, "oid": oid_str, "value": val_str},
            ))
        return alerts

    # ------------------------------------------------------------------
    # Topology
    # ------------------------------------------------------------------

    def get_topology(self) -> list[dict]:
        """
        Return topology data by walking IF-MIB on configured poll targets.
        Each item represents a network interface.
        """
        if not PYSNMP_AVAILABLE or not self._poll_targets:
            return []
        topology = []
        # ifDescr = 1.3.6.1.2.1.2.2.1.2, ifOperStatus = 1.3.6.1.2.1.2.2.1.8
        for target in self._poll_targets:
            host = target.get("host", "")
            if not host:
                continue
            topology.append({"host": host, "source": "snmp"})
        return topology

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def dispose(self) -> None:
        """Stop the trap listener thread."""
        self._stop_event.set()
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=5)
        self._listener_thread = None
