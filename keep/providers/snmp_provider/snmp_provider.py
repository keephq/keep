"""
SNMP Provider is a class that listens for SNMP traps and ingests them as alerts.

It opens a UDP socket on a configurable port (default 162) and uses pysnmp to
decode incoming SNMPv1 / SNMPv2c traps. Each trap is mapped to an ``AlertDto``
and pushed via ``BaseProvider._push_alert``.

This is a *push* / *consumer* style provider in the same family as the Kafka
provider: ``start_consume`` blocks while traps are received and ``stop_consume``
flips the flag to stop the listener thread.
"""

import dataclasses
import logging
from typing import Optional

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """SNMP authentication / listener configuration."""

    listen_host: str = dataclasses.field(
        default="0.0.0.0",
        metadata={
            "required": False,
            "description": "Interface to bind the SNMP trap listener on",
            "hint": "0.0.0.0 to listen on all interfaces",
        },
    )
    listen_port: int = dataclasses.field(
        default=162,
        metadata={
            "required": False,
            "description": "UDP port to listen for SNMP traps on",
            "hint": "Default SNMP trap port is 162; ports < 1024 require elevated privileges",
        },
    )
    community_string: str = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": "SNMPv1/v2c community string used to authenticate incoming traps",
            "hint": "Defaults to 'public' which matches most network device defaults",
            "sensitive": True,
        },
    )
    snmp_version: str = dataclasses.field(
        default="v2c",
        metadata={
            "required": False,
            "description": "SNMP protocol version to accept (v1 or v2c)",
            "hint": "v2c is the default; v3 is not yet supported",
        },
    )


class SnmpProvider(BaseProvider):
    """SNMP trap listener provider.

    Listens for SNMPv1 / SNMPv2c traps on the configured UDP port and converts
    them into Keep ``AlertDto`` records.
    """

    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="receive_traps",
            description="The provider is able to bind to the configured UDP port and accept SNMP traps.",
            mandatory=True,
            alias="Receive SNMP Traps",
        )
    ]

    # Map well-known trap OID suffixes to Keep severities. The full OID is
    # checked first; if no match, we fall back to a substring match so that
    # devices that prefix vendor OIDs still produce reasonable severities.
    _SEVERITY_OID_HINTS = {
        "critical": "critical",
        "alert": "critical",
        "emergency": "critical",
        "error": "high",
        "high": "high",
        "warning": "warning",
        "warn": "warning",
        "info": "info",
        "notice": "info",
        "debug": "low",
        "low": "low",
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.consume = False
        self._dispatcher = None
        self._err = ""

    def validate_config(self):
        """Validate the provider configuration."""
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )
        version = (self.authentication_config.snmp_version or "").lower()
        if version not in ("v1", "v2c"):
            raise ValueError(
                f"Unsupported SNMP version '{self.authentication_config.snmp_version}'. "
                "Supported versions: v1, v2c."
            )
        if not (0 < int(self.authentication_config.listen_port) < 65536):
            raise ValueError(
                f"listen_port must be in 1..65535, got {self.authentication_config.listen_port}"
            )

    def validate_scopes(self):
        """Verify we can actually bind to the configured UDP port."""
        scopes = {"receive_traps": False}
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(
                (
                    self.authentication_config.listen_host,
                    int(self.authentication_config.listen_port),
                )
            )
            scopes["receive_traps"] = True
        except OSError as exc:
            self._err = (
                f"Could not bind UDP {self.authentication_config.listen_host}:"
                f"{self.authentication_config.listen_port}: {exc}"
            )
            self.logger.warning(self._err)
            scopes["receive_traps"] = self._err
        finally:
            sock.close()
        return scopes

    def dispose(self):
        """Stop the trap listener if running."""
        self.stop_consume()

    def status(self):
        """Return a small status payload for the consumer UI."""
        if not self._dispatcher:
            running = "not-initialized"
        else:
            running = "running" if self.consume else "stopped"
        return {"status": running, "error": self._err}

    # ------------------------------------------------------------------ traps

    def _severity_from_trap(self, trap_oid: str, var_binds: dict) -> str:
        """Best-effort mapping from a trap OID / its variables to a Keep severity."""
        haystack = " ".join(
            [trap_oid or "", *[str(v) for v in var_binds.values()]]
        ).lower()
        for needle, severity in self._SEVERITY_OID_HINTS.items():
            if needle in haystack:
                return severity
        return "info"

    def _trap_to_alert(
        self,
        trap_oid: str,
        var_binds: dict,
        source_address: Optional[str] = None,
    ) -> dict:
        """Map a decoded SNMP trap to an ``AlertDto``-shaped dict.

        ``var_binds`` is a mapping of OID strings to their decoded values.
        ``trap_oid`` is the SNMPv2 trap OID (``1.3.6.1.6.3.1.1.4.1.0``).
        """
        severity = self._severity_from_trap(trap_oid, var_binds)
        # Compose a human readable description out of the variable bindings so
        # operators get something useful in the UI even without trap MIBs.
        description_lines = [f"{oid} = {value}" for oid, value in var_binds.items()]
        description = "\n".join(description_lines) or "SNMP trap received"
        name = trap_oid or "snmp-trap"

        alert = {
            "name": name,
            "message": f"SNMP trap {trap_oid} received",
            "description": description,
            "severity": severity,
            "status": "firing",
            "source": ["snmp"],
            "labels": {
                "trap_oid": trap_oid,
                "snmp_version": self.authentication_config.snmp_version,
            },
            "fingerprint": trap_oid or None,
        }
        if source_address:
            alert["labels"]["source_address"] = source_address
        # Also surface every var bind as a top-level label for filtering.
        for oid, value in var_binds.items():
            alert["labels"][oid] = str(value)
        return alert

    def _on_trap(self, snmp_engine, state_reference, context_engine_id, context_name,
                 var_binds, cb_ctx):  # pragma: no cover - exercised via integration
        """pysnmp callback invoked for each received trap."""
        try:
            from pysnmp.proto.api import v2c as v2c_api

            decoded = {}
            trap_oid = ""
            for oid, value in var_binds:
                oid_str = oid.prettyPrint()
                value_str = value.prettyPrint()
                decoded[oid_str] = value_str
                # The SNMPv2 trap OID lives in ``snmpTrapOID.0``.
                if oid_str == str(v2c_api.apiTrapPDU.snmpTrapOID):
                    trap_oid = value_str
            transport = snmp_engine.observer.getExecutionContext(
                "rfc3412.receiveMessage:request"
            ) if hasattr(snmp_engine, "observer") else {}
            source_address = None
            if isinstance(transport, dict):
                addr = transport.get("transportAddress")
                if addr is not None:
                    source_address = str(addr)

            alert = self._trap_to_alert(trap_oid, decoded, source_address)
            self.logger.info(
                "Received SNMP trap",
                extra={"trap_oid": trap_oid, "var_binds": decoded},
            )
            try:
                self._push_alert(alert)
            except Exception:
                self.logger.exception("Error pushing SNMP-trap alert to API")
        except Exception:
            self.logger.exception("Error processing SNMP trap")

    def start_consume(self):
        """Block in the SNMP trap dispatcher until ``stop_consume`` is called."""
        # Imported lazily so test environments without pysnmp installed can
        # still import the module (e.g. for unit-testing the mapping helpers).
        from pysnmp.carrier.asyncore.dispatch import AsyncoreDispatcher
        from pysnmp.carrier.asyncore.dgram import udp
        from pysnmp.entity import config as snmp_config
        from pysnmp.entity import engine
        from pysnmp.entity.rfc3413 import ntfrcv

        self.consume = True
        self._err = ""

        snmp_engine = engine.SnmpEngine()
        # Bind to the requested host/port.
        try:
            snmp_config.addTransport(
                snmp_engine,
                udp.domainName + (1,),
                udp.UdpTransport().openServerMode(
                    (
                        self.authentication_config.listen_host,
                        int(self.authentication_config.listen_port),
                    )
                ),
            )
        except Exception as exc:
            self._err = (
                f"Failed to bind SNMP trap listener on "
                f"{self.authentication_config.listen_host}:"
                f"{self.authentication_config.listen_port}: {exc}"
            )
            self.logger.exception(self._err)
            self.consume = False
            return

        # SNMPv1 + SNMPv2c communities. We register both so a single listener
        # can accept either; the configured ``snmp_version`` is used purely
        # for labeling in the alert payload.
        snmp_config.addV1System(
            snmp_engine,
            "keep-area",
            self.authentication_config.community_string,
        )

        ntfrcv.NotificationReceiver(snmp_engine, self._on_trap)

        self.logger.info(
            "SNMP trap listener started",
            extra={
                "host": self.authentication_config.listen_host,
                "port": self.authentication_config.listen_port,
                "version": self.authentication_config.snmp_version,
            },
        )

        self._dispatcher = snmp_engine.transportDispatcher
        # ``jobStarted`` keeps the dispatcher loop running until we explicitly
        # close it; ``stop_consume`` calls ``closeDispatcher`` to break out.
        self._dispatcher.jobStarted(1)
        try:
            self._dispatcher.runDispatcher()
        except Exception:
            self.logger.exception("SNMP dispatcher exited unexpectedly")
        finally:
            try:
                self._dispatcher.closeDispatcher()
            except Exception:
                pass
            self._dispatcher = None
            self.consume = False
            self.logger.info("SNMP trap listener stopped")

    def stop_consume(self):
        """Signal the dispatcher loop to exit."""
        self.consume = False
        if self._dispatcher is not None:
            try:
                self._dispatcher.closeDispatcher()
            except Exception:
                self.logger.exception("Error closing SNMP dispatcher")


if __name__ == "__main__":  # pragma: no cover - manual smoke test entry point
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])
    import os

    os.environ.setdefault("KEEP_API_URL", "http://localhost:8080")
    from keep.api.core.dependencies import SINGLE_TENANT_UUID

    context_manager = ContextManager(tenant_id=SINGLE_TENANT_UUID)
    config = {
        "authentication": {
            "listen_host": "0.0.0.0",
            "listen_port": 1162,  # non-privileged port for local testing
            "community_string": "public",
            "snmp_version": "v2c",
        }
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="snmp-keephq",
        provider_type="snmp",
        provider_config=config,
    )
    provider.start_consume()
