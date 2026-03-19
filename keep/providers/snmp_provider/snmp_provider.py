"""
SNMP provider: listen for SNMPv1/v2c traps and INFORMs and push them into Keep as alerts.

See https://github.com/keephq/keep/issues/2112
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import logging
import socket
import uuid
from datetime import datetime, timezone

import pydantic
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import config
from pysnmp.entity.engine import SnmpEngine
from pysnmp.entity.rfc3413 import ntfrcv

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

# SNMPv2-MIB::snmpTrapOID.0 (value is the trap's enterprise / notification OID)
SNMP_TRAP_OID_NUMERIC = "1.3.6.1.6.3.1.1.4.1.0"


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """SNMP trap listener (SNMPv1 / SNMPv2c community security)."""

    host: str = dataclasses.field(
        default="0.0.0.0",
        metadata={
            "required": True,
            "description": "Listen address",
            "hint": "0.0.0.0 for all interfaces",
        },
    )
    port: int = dataclasses.field(
        default=162,
        metadata={
            "required": True,
            "description": "UDP port for SNMP traps",
            "hint": "Port 162 often requires elevated privileges; use e.g. 9162 for testing",
        },
    )
    community: str = dataclasses.field(
        default="public",
        metadata={
            "required": True,
            "description": "SNMP community string (v1/v2c)",
            "hint": "Must match the community configured on your trap sources",
        },
    )


class SnmpProvider(BaseProvider):
    """
    Ingest SNMPv1 and SNMPv2c traps (and INFORMs) as Keep alerts.
    """

    PROVIDER_CATEGORY = ["Observability"]
    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert", "network"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="listen_udp",
            description="Bind to the configured UDP address and receive SNMP notifications.",
            mandatory=True,
            alias="Listen for traps",
        )
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.consume = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._snmp_engine: SnmpEngine | None = None
        self._receiver: ntfrcv.NotificationReceiver | None = None
        self.err = ""

    def validate_config(self):
        self.authentication_config = SnmpProviderAuthConfig(**self.config.authentication)

    def validate_scopes(self) -> dict[str, bool | str]:
        self.logger.info("Validating SNMP listener (UDP bind check)")
        scopes: dict[str, bool | str] = {"listen_udp": False}
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(
                (self.authentication_config.host, int(self.authentication_config.port))
            )
            scopes["listen_udp"] = True
        except OSError as e:
            self.err = str(e)
            self.logger.warning("SNMP UDP bind check failed: %s", e)
            scopes["listen_udp"] = self.err
        finally:
            sock.close()
        return scopes

    def dispose(self):
        pass

    def status(self) -> dict:
        return {
            "status": "running" if self.consume else "stopped",
            "error": self.err,
        }

    @staticmethod
    def _trap_callback(
        snmpEngine,
        stateReference,
        contextEngineId,
        contextName,
        varBinds,
        cbCtx,
    ):
        if cbCtx is None:
            return
        try:
            cbCtx._handle_trap(varBinds)
        except Exception:
            cbCtx.logger.exception("Failed to handle SNMP trap")

    def _handle_trap(self, varBinds):
        alert = SnmpProvider.format_trap_alert(varBinds)
        self.logger.info(
            "SNMP trap received, pushing alert",
            extra={"name": alert.get("name"), "fingerprint": alert.get("fingerprint")},
        )
        self._push_alert(alert)

    @staticmethod
    def format_trap_alert(varBinds) -> dict:
        lines: list[str] = []
        trap_oid: str | None = None
        for oid, val in varBinds:
            o = oid.prettyPrint()
            v = val.prettyPrint() if val is not None else ""
            lines.append(f"{o} = {v}")
            if (
                o == SNMP_TRAP_OID_NUMERIC
                or SNMP_TRAP_OID_NUMERIC in o
                or o.endswith("snmpTrapOID.0")
            ):
                trap_oid = v

        body = "\n".join(lines)
        if not trap_oid and lines:
            trap_oid = lines[0].split("=", 1)[0].strip()

        name = trap_oid or "snmp-trap"
        if "." in name:
            short = name.split(".")[-1]
            if short and short[0].isdigit():
                name = f"snmp-trap-{short}"
            else:
                name = short or name

        fp_src = f"{trap_oid}|{body}"
        fingerprint = hashlib.sha256(fp_src.encode("utf-8", errors="replace")).hexdigest()[
            :32
        ]
        now = datetime.now(tz=timezone.utc).isoformat()

        return {
            "id": str(uuid.uuid4()),
            "name": name[:500],
            "status": AlertStatus.FIRING,
            "severity": AlertSeverity.WARNING,
            "lastReceived": now,
            "environment": "snmp",
            "service": "snmp",
            "source": ["snmp"],
            "message": body[:4000] if body else "SNMP trap (no varbinds)",
            "description": body[:16000] if body else "SNMP trap (no varbinds)",
            "fingerprint": fingerprint,
            "labels": {"trap_oid": trap_oid or ""},
        }

    def _schedule_stop_watcher(self):
        if self._loop is None:
            return

        async def watcher():
            while self.consume:
                await asyncio.sleep(0.25)
            await self._shutdown_loop_resources()

        self._loop.call_soon(lambda: self._loop.create_task(watcher()))

    async def _shutdown_loop_resources(self):
        try:
            if self._receiver and self._snmp_engine:
                self._receiver.close(self._snmp_engine)
        except Exception:
            self.logger.exception("Error closing SNMP NotificationReceiver")
        try:
            if self._snmp_engine:
                self._snmp_engine.close_dispatcher()
        except Exception:
            self.logger.exception("Error closing SNMP dispatcher")
        if self._loop and self._loop.is_running():
            self._loop.stop()

    def _shutdown_threadsafe(self):
        self.consume = False
        loop = self._loop
        if loop is None or loop.is_closed():
            return

        def on_loop():
            asyncio.create_task(self._shutdown_loop_resources())

        try:
            loop.call_soon_threadsafe(on_loop)
        except RuntimeError:
            self.logger.warning("Could not schedule SNMP shutdown on event loop")

    def start_consume(self):
        self.consume = True
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._snmp_engine = None
        self._receiver = None
        try:
            self._snmp_engine = SnmpEngine()
            transport = udp.UdpTransport(loop=self._loop).open_server_mode(
                (
                    self.authentication_config.host,
                    int(self.authentication_config.port),
                )
            )
            config.add_transport(self._snmp_engine, udp.SNMP_UDP_DOMAIN, transport)
            config.add_v1_system(
                self._snmp_engine,
                "keep-snmp",
                self.authentication_config.community,
            )
            self._receiver = ntfrcv.NotificationReceiver(
                self._snmp_engine,
                SnmpProvider._trap_callback,
                cbCtx=self,
            )
            self._schedule_stop_watcher()
            self._snmp_engine.open_dispatcher()
        except Exception:
            self.logger.exception("SNMP trap listener failed to start")
            if self._snmp_engine:
                try:
                    self._snmp_engine.close_dispatcher()
                except Exception:
                    pass
        finally:
            self.consume = False
            try:
                if self._loop and not self._loop.is_closed():
                    self._loop.close()
            except Exception:
                pass
            self._loop = None
            self._snmp_engine = None
            self._receiver = None
        self.logger.info("SNMP consuming stopped")

    def stop_consume(self):
        self._shutdown_threadsafe()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from keep.api.core.dependencies import SINGLE_TENANT_UUID

    cm = ContextManager(tenant_id=SINGLE_TENANT_UUID)
    cfg = {
        "authentication": {
            "host": "127.0.0.1",
            "port": 9162,
            "community": "public",
        }
    }
    from keep.providers.providers_factory import ProvidersFactory

    p = ProvidersFactory.get_provider(
        cm,
        provider_id="snmp-dev",
        provider_type="snmp",
        provider_config=cfg,
    )
    p.start_consume()
