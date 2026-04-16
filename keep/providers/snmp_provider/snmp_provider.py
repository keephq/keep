"""
SnmpProvider - receives SNMP traps as Keep alerts and optionally polls OIDs.

Two modes of operation:
  1. Trap Receiver (push/consumer): listens on a UDP port for SNMP v1/v2c/v3
     traps sent by network devices and converts them to Keep AlertDtos.
  2. OID Poller (pull): periodically GETs a list of OIDs from a target agent
     and presents each value as a Keep AlertDto.

Both modes can run simultaneously from the same provider instance.
"""

import dataclasses
import datetime
import hashlib
import json
import logging
import threading
import time
from typing import Optional

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SNMP Generic-Trap type → severity
# RFC 1157 §4.1.6 defines generic trap types 0-5; 6 = enterprise-specific.
# ---------------------------------------------------------------------------
_GENERIC_TRAP_SEVERITY: dict[int, AlertSeverity] = {
    0: AlertSeverity.INFO,       # coldStart
    1: AlertSeverity.LOW,        # warmStart
    2: AlertSeverity.HIGH,       # linkDown
    3: AlertSeverity.INFO,       # linkUp
    4: AlertSeverity.WARNING,    # authenticationFailure
    5: AlertSeverity.HIGH,       # egpNeighborLoss
    6: AlertSeverity.INFO,       # enterpriseSpecific
}

_GENERIC_TRAP_NAMES: dict[int, str] = {
    0: "coldStart",
    1: "warmStart",
    2: "linkDown",
    3: "linkUp",
    4: "authenticationFailure",
    5: "egpNeighborLoss",
    6: "enterpriseSpecific",
}

# snmpTrapOID — used to identify the trap type in v2c notifications
_SNMP_TRAP_OID = "1.3.6.1.6.3.1.1.4.1.0"
# sysUpTime
_SYS_UP_TIME_OID = "1.3.6.1.2.1.1.3.0"


# ---------------------------------------------------------------------------
# Auth config
# ---------------------------------------------------------------------------


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP provider configuration.

    *host* is only required when polling OIDs; it is optional for trap-only mode.
    """

    community: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SNMP community string (v1/v2c) used for authentication",
            "hint": "public",
            "sensitive": True,
        },
        default="public",
    )
    host: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Target SNMP agent hostname/IP for OID polling (leave empty for trap-only mode)",
            "hint": "192.168.1.1",
            "sensitive": False,
        },
        default="",
    )
    port: int = dataclasses.field(
        metadata={
            "required": False,
            "description": "UDP port of the target SNMP agent",
            "hint": "161",
            "sensitive": False,
        },
        default=161,
    )
    trap_port: int = dataclasses.field(
        metadata={
            "required": False,
            "description": "UDP port Keep listens on for incoming SNMP traps (use 1162 to avoid root)",
            "hint": "1162",
            "sensitive": False,
        },
        default=1162,
    )
    oids: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Comma-separated OIDs to poll from the target agent",
            "hint": "1.3.6.1.2.1.1.1.0, 1.3.6.1.2.1.1.5.0",
            "sensitive": False,
        },
        default="",
    )
    snmp_version: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMP version to use for polling: '1', '2c'",
            "hint": "2c",
            "sensitive": False,
        },
        default="2c",
    )
    timeout: float = dataclasses.field(
        metadata={
            "required": False,
            "description": "Socket timeout in seconds for OID polling",
            "hint": "2.0",
            "sensitive": False,
        },
        default=2.0,
    )
    retries: int = dataclasses.field(
        metadata={
            "required": False,
            "description": "Number of retries for OID polling",
            "hint": "2",
            "sensitive": False,
        },
        default=2,
    )


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class SnmpProvider(BaseProvider):
    """
    Keep provider for SNMP — receives traps from network devices as alerts
    and/or polls OIDs on demand.

    **Trap receiver** (push / consumer mode)
    ----------------------------------------
    The provider starts a UDP listener (default port 1162) that accepts
    SNMP v1/v2c trap PDUs. Each trap is converted to a Keep ``AlertDto`` and
    pushed into the alert pipeline immediately.

    Configure your network devices to send traps to::

        udp://<keep-host>:<trap_port>

    **OID polling** (pull mode)
    ---------------------------
    When *host* and *oids* are configured the provider fetches the OID values
    via SNMP GET when Keep calls ``_get_alerts()`` or ``query()``.
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert", "data"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="connectivity",
            description="Validates that Keep can reach the configured SNMP agent "
            "(only relevant when *host* is set).",
            mandatory=False,
        )
    ]
    FINGERPRINT_FIELDS = ["fingerprint"]

    webhook_description = (
        "Configure your network devices to send SNMP traps to the Keep trap "
        "receiver running on the host shown below. "
        "No HTTP webhook is involved — traps are received over UDP."
    )
    webhook_markdown = """
### SNMP Trap Receiver Setup

Keep runs a UDP trap listener on the configured **trap_port** (default **1162**).

Point your devices at::

    <keep-host>:<trap_port>

Use community string matching the one configured in this provider.

#### Example — net-snmp
```bash
snmptrap -v 2c -c public <keep-host>:<trap_port> '' \\
    1.3.6.1.6.3.1.1.5.1
```

#### Example — Cisco IOS
```
snmp-server host <keep-host> traps version 2c public
```
"""

    # ------------------------------------------------------------------
    # Severity / status helpers
    # ------------------------------------------------------------------

    _GENERIC_TRAP_SEVERITY = _GENERIC_TRAP_SEVERITY
    _GENERIC_TRAP_NAMES = _GENERIC_TRAP_NAMES

    @staticmethod
    def _oid_to_severity(trap_oid: str, generic_trap: Optional[int] = None) -> AlertSeverity:
        """
        Derive severity from a trap OID or generic-trap integer.
        Falls back to INFO if the OID is not recognized.
        """
        if generic_trap is not None:
            return _GENERIC_TRAP_SEVERITY.get(generic_trap, AlertSeverity.INFO)
        # Very coarse heuristic based on well-known OID sub-trees
        if "linkDown" in trap_oid or "1.3.6.1.6.3.1.1.5.3" in trap_oid:
            return AlertSeverity.HIGH
        if "authenticationFailure" in trap_oid or "1.3.6.1.6.3.1.1.5.5" in trap_oid:
            return AlertSeverity.WARNING
        if "linkUp" in trap_oid or "1.3.6.1.6.3.1.1.5.4" in trap_oid:
            return AlertSeverity.INFO
        if "coldStart" in trap_oid or "1.3.6.1.6.3.1.1.5.1" in trap_oid:
            return AlertSeverity.INFO
        if "warmStart" in trap_oid or "1.3.6.1.6.3.1.1.5.2" in trap_oid:
            return AlertSeverity.LOW
        return AlertSeverity.INFO

    # ------------------------------------------------------------------
    # BaseProvider interface
    # ------------------------------------------------------------------

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self._trap_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def validate_config(self):
        """Parse and validate provider configuration."""
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Connectivity check — only meaningful when a *host* is configured for polling.
        """
        validated: dict[str, bool | str] = {}
        if not self.authentication_config.host:
            validated["connectivity"] = True
            return validated
        try:
            self.fetch_metrics(["1.3.6.1.2.1.1.2.0"])  # sysObjectID
            validated["connectivity"] = True
        except Exception as exc:
            validated["connectivity"] = str(exc)
        return validated

    def dispose(self):
        """Stop the trap listener if it is running."""
        self._stop_event.set()
        if self._trap_thread and self._trap_thread.is_alive():
            self._trap_thread.join(timeout=5)

    # ------------------------------------------------------------------
    # OID polling (pull)
    # ------------------------------------------------------------------

    def fetch_metrics(self, oids: list[str]) -> dict[str, str]:
        """
        Perform an SNMP GET for each OID in *oids* against the configured
        agent (*host*:*port*).

        Returns:
            dict mapping ``oid_name`` → ``value`` string.

        Raises:
            ValueError:  if *host* is not configured.
            Exception:   on network errors, bad OIDs, or SNMP errors.
        """
        if not self.authentication_config.host:
            raise ValueError(
                "Cannot poll OIDs: 'host' is not configured in this provider."
            )

        # Import here so the provider can still load even if pysnmp is absent
        # during unit tests (tests mock this method directly).
        try:
            from pysnmp.hlapi import (  # type: ignore[import]
                CommunityData,
                ContextData,
                ObjectIdentity,
                ObjectType,
                SnmpEngine,
                UdpTransportTarget,
                getCmd,
            )
        except ImportError:
            try:
                from pysnmp.hlapi.v3arch.sync import (  # type: ignore[import]
                    CommunityData,
                    ContextData,
                    ObjectIdentity,
                    ObjectType,
                    SnmpEngine,
                    UdpTransportTarget,
                    getCmd,
                )
            except ImportError as exc:
                raise ImportError(
                    "pysnmp is not installed. Install it with: pip install pysnmp"
                ) from exc

        mp_model = 1 if self.authentication_config.snmp_version == "2c" else 0
        community_data = CommunityData(
            self.authentication_config.community, mpModel=mp_model
        )
        transport_target = UdpTransportTarget(
            (self.authentication_config.host, self.authentication_config.port),
            timeout=self.authentication_config.timeout,
            retries=self.authentication_config.retries,
        )
        object_types = [ObjectType(ObjectIdentity(oid)) for oid in oids]

        iterator = getCmd(
            SnmpEngine(),
            community_data,
            transport_target,
            ContextData(),
            *object_types,
        )

        try:
            error_indication, error_status, error_index, var_binds = next(iterator)
        except StopIteration:
            return {}
        except Exception as exc:
            raise Exception(
                f"SNMP GET failed for {self.authentication_config.host}: {exc}"
            ) from exc

        if error_indication:
            # Timeout is the most common case
            if "timeout" in str(error_indication).lower():
                raise TimeoutError(
                    f"SNMP timeout reaching {self.authentication_config.host}:"
                    f"{self.authentication_config.port} — host may be unreachable."
                )
            raise Exception(f"SNMP error: {error_indication}")

        if error_status:
            offending = (
                var_binds[int(error_index) - 1][0].prettyPrint()
                if error_index
                else "?"
            )
            raise Exception(
                f"SNMP agent error: {error_status.prettyPrint()} at OID {offending}"
            )

        return {
            name.prettyPrint(): val.prettyPrint() for name, val in var_binds
        }

    def _query(self, oids: str = None, **kwargs) -> list[AlertDto]:
        """
        Query specific OIDs and return them as ``AlertDto`` objects.

        Args:
            oids: Comma-separated OID string. Falls back to the provider's
                  configured *oids* field if not supplied.

        Returns:
            list of AlertDto — one per OID returned by the agent.
        """
        target_oids_str = oids or self.authentication_config.oids
        if not target_oids_str:
            raise ValueError(
                "No OIDs specified. Pass 'oids' to the query or configure them in the provider."
            )
        oid_list = [o.strip() for o in target_oids_str.split(",") if o.strip()]

        try:
            metrics = self.fetch_metrics(oid_list)
        except TimeoutError as exc:
            self.logger.error("SNMP timeout during OID poll", exc_info=True)
            raise
        except Exception as exc:
            self.logger.error("Failed to fetch SNMP metrics", exc_info=True)
            raise Exception(f"SNMP query failed: {exc}") from exc

        return self._metrics_to_alerts(metrics)

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull-mode: return current OID values as alerts.
        Returns an empty list if no *host* or *oids* are configured
        (trap-only mode).
        """
        if not (self.authentication_config.host and self.authentication_config.oids):
            return []
        try:
            return self._query()
        except Exception:
            self.logger.exception("_get_alerts failed")
            return []

    def _metrics_to_alerts(self, metrics: dict[str, str]) -> list[AlertDto]:
        """Convert a {oid: value} dict (from SNMP GET) to a list of AlertDto."""
        now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        alerts = []
        for oid, value in metrics.items():
            fp = hashlib.md5(
                f"snmp-poll-{self.authentication_config.host}-{oid}".encode()
            ).hexdigest()
            alerts.append(
                AlertDto(
                    id=fp,
                    name=f"SNMP OID {oid}",
                    description=(
                        f"SNMP GET {oid} on "
                        f"{self.authentication_config.host}:{self.authentication_config.port}"
                        f" returned: {value}"
                    ),
                    status=AlertStatus.FIRING,
                    severity=AlertSeverity.INFO,
                    lastReceived=now,
                    environment="unknown",
                    source=["snmp"],
                    service=self.authentication_config.host,
                    payload={"oid": oid, "value": value, "mode": "poll"},
                    fingerprint=fp,
                )
            )
        return alerts

    # ------------------------------------------------------------------
    # Trap receiver (push / consumer)
    # ------------------------------------------------------------------

    def start_consume(self):
        """
        Start the SNMP trap receiver.

        This method blocks (runs the pysnmp transport dispatcher loop).
        Keep calls it in a background thread.
        """
        try:
            from pysnmp.entity import config as snmp_cfg
            from pysnmp.entity import engine as snmp_eng
            from pysnmp.entity.rfc3413 import ntfrcv
        except ImportError as exc:
            raise ImportError(
                "pysnmp is required for SNMP trap receiving. "
                "Install it with: pip install pysnmp"
            ) from exc

        # Try asyncio transport, fall back to native asyncore
        try:
            from pysnmp.carrier.asyncio.dgram import udp as udp_transport
            _use_asyncio = True
        except ImportError:
            from pysnmp.carrier.asyncore.dgram import udp as udp_transport  # type: ignore[no-redef]
            _use_asyncio = False

        snmp_engine = snmp_eng.SnmpEngine()

        # ── Transport ──────────────────────────────────────────────────
        snmp_cfg.addTransport(
            snmp_engine,
            udp_transport.DOMAIN_NAME + (1,),
            udp_transport.UdpAsyncioTransport().openServerMode(
                ("0.0.0.0", self.authentication_config.trap_port)
            )
            if _use_asyncio
            else udp_transport.UdpSocketTransport().openServerMode(
                ("0.0.0.0", self.authentication_config.trap_port)
            ),
        )

        # ── SNMPv1/v2c community ───────────────────────────────────────
        snmp_cfg.addV1System(
            snmp_engine,
            "keep-trap-receiver",
            self.authentication_config.community,
        )

        # ── Notification receiver callback ─────────────────────────────
        provider_ref = self  # capture for closure

        def trap_callback(
            snmp_engine,
            state_reference,
            context_engine_id,
            context_name,
            var_binds,
            cb_ctx,
        ):
            try:
                raw: dict[str, str] = {}
                for name, val in var_binds:
                    raw[name.prettyPrint()] = val.prettyPrint()

                provider_ref.logger.debug(
                    "SNMP trap received", extra={"var_binds": raw}
                )

                alert = SnmpProvider._format_alert(raw)
                if isinstance(alert, list):
                    for a in alert:
                        provider_ref._push_alert(a.dict())
                elif alert:
                    provider_ref._push_alert(alert.dict())

            except Exception:
                provider_ref.logger.exception("Error processing SNMP trap")

        ntfrcv.NotificationReceiver(snmp_engine, trap_callback)

        self.logger.info(
            "SNMP trap receiver started",
            extra={"port": self.authentication_config.trap_port},
        )

        # Keep the dispatcher alive until stop is requested
        snmp_engine.transportDispatcher.jobStarted(1)
        try:
            while not self._stop_event.is_set():
                snmp_engine.transportDispatcher.runDispatcher(timeout=1.0)
        except Exception:
            self.logger.exception("SNMP trap dispatcher error")
        finally:
            snmp_engine.transportDispatcher.closeDispatcher()
            self.logger.info("SNMP trap receiver stopped")

    # ------------------------------------------------------------------
    # Alert formatting (traps → AlertDto)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(
        event: dict | list[dict],
        provider_instance: "BaseProvider" = None,
    ) -> AlertDto | list[AlertDto]:
        """
        Convert a raw SNMP trap var-bind dict into an AlertDto.

        ``event`` is expected to be a ``{oid_name: value_str}`` dict
        produced by the trap callback.
        """
        if isinstance(event, list):
            return [SnmpProvider._format_alert(e, provider_instance) for e in event]

        now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

        # ── Extract well-known OIDs ────────────────────────────────────
        trap_oid = event.get(_SNMP_TRAP_OID, "")
        uptime = event.get(_SYS_UP_TIME_OID, "")

        # Build a human-readable name from the trap OID
        # (last arc of the OID or the mib-name if resolved)
        if trap_oid:
            name = f"SNMP Trap: {trap_oid}"
        else:
            name = "SNMP Trap"

        severity = SnmpProvider._oid_to_severity(trap_oid)
        description_parts = [f"trap-oid={trap_oid}"] if trap_oid else []
        if uptime:
            description_parts.append(f"sysUpTime={uptime}")

        # Remaining bindings as payload
        payload = dict(event)

        # Fingerprint — stable per (trap-oid) so duplicates are deduped
        fp_src = trap_oid or json.dumps(sorted(event.items()))
        fp = hashlib.md5(f"snmp-trap-{fp_src}".encode()).hexdigest()

        return AlertDto(
            id=fp,
            name=name,
            description="; ".join(description_parts) or name,
            status=AlertStatus.FIRING,
            severity=severity,
            lastReceived=now,
            environment="unknown",
            source=["snmp"],
            service="snmp-agent",
            pushed=True,
            payload=payload,
            fingerprint=fp,
        )

    # ------------------------------------------------------------------
    # Notify — not supported
    # ------------------------------------------------------------------

    def _notify(self, **kwargs):
        raise NotImplementedError(
            "SnmpProvider does not support outbound notifications. "
            "Use the trap receiver or OID polling instead."
        )


# ---------------------------------------------------------------------------
# Manual test entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG)

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    config = ProviderConfig(
        authentication={
            "host": os.environ.get("SNMP_HOST", "demo.pysnmp.com"),
            "port": int(os.environ.get("SNMP_PORT", "161")),
            "community": os.environ.get("SNMP_COMMUNITY", "public"),
            "oids": "1.3.6.1.2.1.1.1.0,1.3.6.1.2.1.1.5.0",
        }
    )
    provider = SnmpProvider(context_manager, "snmp-test", config)
    alerts = provider._get_alerts()
    for a in alerts:
        print(a)
