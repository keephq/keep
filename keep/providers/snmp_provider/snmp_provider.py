"""
SNMP Provider for Keep - supports SNMP v1/v2c/v3 polling and trap receiving.

Polling uses pysnmp-lextudio v6 high-level async API (pysnmp.hlapi.asyncio).
Trap reception uses pysnmp-lextudio v6 low-level entity API.
"""

import asyncio
import dataclasses
import datetime
import logging
import threading
import uuid

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP authentication configuration.
    Supports SNMP v1, v2c, and v3 authentication parameters,
    as well as trap listener configuration.
    """

    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SNMP agent host IP or hostname",
            "hint": "e.g. 192.168.1.1",
            "sensitive": False,
        },
    )

    port: int = dataclasses.field(
        default=161,
        metadata={
            "required": False,
            "description": "SNMP agent port (default: 161 for polling, 162 for trap listening)",
            "hint": "161",
            "sensitive": False,
        },
    )

    community: str = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": "SNMP community string (for v1/v2c)",
            "hint": "public",
            "sensitive": True,
        },
    )

    snmp_version: int = dataclasses.field(
        default=2,
        metadata={
            "required": False,
            "description": "SNMP version: 1, 2, or 3",
            "hint": "2",
            "sensitive": False,
        },
    )

    oids: str = dataclasses.field(
        default="1.3.6.1.2.1.1.3.0",
        metadata={
            "required": False,
            "description": "Comma-separated list of OIDs to poll",
            "hint": "1.3.6.1.2.1.1.3.0,1.3.6.1.2.1.1.1.0",
            "sensitive": False,
        },
    )

    security_username: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMP v3 security username",
            "hint": "usr-md5-des",
            "sensitive": False,
        },
    )

    auth_protocol: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMP v3 auth protocol: MD5, SHA, SHA224, SHA256, SHA384, SHA512, or NONE",
            "hint": "MD5",
            "sensitive": False,
        },
    )

    auth_key: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMP v3 authentication key/passphrase",
            "hint": "authkey123",
            "sensitive": True,
        },
    )

    priv_protocol: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMP v3 privacy protocol: DES, 3DES, AES128, AES192, AES256, or NONE",
            "hint": "DES",
            "sensitive": False,
        },
    )

    priv_key: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMP v3 privacy key/passphrase",
            "hint": "privkey123",
            "sensitive": True,
        },
    )

    trap_enabled: bool = dataclasses.field(
        default=False,
        metadata={
            "required": False,
            "description": "Enable SNMP trap listener",
            "hint": "false",
            "sensitive": False,
        },
    )

    trap_port: int = dataclasses.field(
        default=162,
        metadata={
            "required": False,
            "description": "Port to listen for SNMP traps (default: 162)",
            "hint": "162",
            "sensitive": False,
        },
    )

    trap_host: str = dataclasses.field(
        default="0.0.0.0",
        metadata={
            "required": False,
            "description": "Host/IP to bind trap listener (default: 0.0.0.0)",
            "hint": "0.0.0.0",
            "sensitive": False,
        },
    )

    polling_interval: int = dataclasses.field(
        default=60,
        metadata={
            "required": False,
            "description": "Polling interval in seconds (default: 60)",
            "hint": "60",
            "sensitive": False,
        },
    )


# Well-known SNMP trap OID mappings
SNMP_TRAP_SEVERITY_MAP = {
    "1.3.6.1.6.3.1.1.5.1": AlertSeverity.INFO,       # linkDown
    "1.3.6.1.6.3.1.1.5.2": AlertSeverity.INFO,       # coldStart
    "1.3.6.1.6.3.1.1.5.3": AlertSeverity.WARNING,    # warmStart
    "1.3.6.1.6.3.1.1.5.4": AlertSeverity.CRITICAL,   # authenticationFailure
    "1.3.6.1.6.3.1.1.5.5": AlertSeverity.INFO,       # egpNeighborLoss
    "1.3.6.1.6.3.1.1.5.6": AlertSeverity.INFO,       # enterpriseSpecific
}

SNMP_TRAP_NAMES = {
    "1.3.6.1.6.3.1.1.5.1": "linkDown",
    "1.3.6.1.6.3.1.1.5.2": "coldStart",
    "1.3.6.1.6.3.1.1.5.3": "warmStart",
    "1.3.6.1.6.3.1.1.5.4": "authenticationFailure",
    "1.3.6.1.6.3.1.1.5.5": "egpNeighborLoss",
    "1.3.6.1.6.3.1.1.5.6": "enterpriseSpecific",
}


def _get_auth_protocol(protocol_name: str):
    """Map auth protocol name to pysnmp constant."""
    from pysnmp.hlapi.asyncio import (
        usmHMACMD5AuthProtocol,
        usmHMACSHAAuthProtocol,
        usmHMAC128SHA224AuthProtocol,
        usmHMAC192SHA256AuthProtocol,
        usmHMAC256SHA384AuthProtocol,
        usmHMAC384SHA512AuthProtocol,
        usmNoAuthProtocol,
    )

    mapping = {
        "MD5": usmHMACMD5AuthProtocol,
        "SHA": usmHMACSHAAuthProtocol,
        "SHA224": usmHMAC128SHA224AuthProtocol,
        "SHA256": usmHMAC192SHA256AuthProtocol,
        "SHA384": usmHMAC256SHA384AuthProtocol,
        "SHA512": usmHMAC384SHA512AuthProtocol,
        "NONE": usmNoAuthProtocol,
    }
    return mapping.get((protocol_name or "NONE").upper())


def _get_priv_protocol(protocol_name: str):
    """Map privacy protocol name to pysnmp constant."""
    from pysnmp.hlapi.asyncio import (
        usmDESPrivProtocol,
        usm3DESEDEPrivProtocol,
        usmAesCfb128Protocol,
        usmAesCfb192Protocol,
        usmAesCfb256Protocol,
        usmNoPrivProtocol,
    )

    mapping = {
        "DES": usmDESPrivProtocol,
        "3DES": usm3DESEDEPrivProtocol,
        "AES128": usmAesCfb128Protocol,
        "AES192": usmAesCfb192Protocol,
        "AES256": usmAesCfb256Protocol,
        "NONE": usmNoPrivProtocol,
    }
    return mapping.get((protocol_name or "NONE").upper())


class SnmpProvider(BaseProvider):
    """SNMP provider for Keep - supports v1/v2c/v3 polling and trap receiving."""

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="snmp_poll",
            description="SNMP polling is working",
            mandatory=True,
            alias="SNMP Poll",
        ),
        ProviderScope(
            name="snmp_trap_listen",
            description="SNMP trap listener is working",
            mandatory=False,
            alias="SNMP Trap Listen",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.consume = False
        self._trap_thread = None

    def dispose(self):
        """Clean up resources."""
        self.stop_consume()

    def validate_config(self):
        """Validate the SNMP provider configuration."""
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )
        if self.authentication_config.snmp_version not in (1, 2, 3):
            raise ValueError(
                f"Invalid SNMP version: {self.authentication_config.snmp_version}. "
                "Must be 1, 2, or 3."
            )
        if (
            self.authentication_config.snmp_version == 3
            and not self.authentication_config.security_username
        ):
            raise ValueError("SNMP v3 requires security_username")

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate the SNMP provider scopes."""
        scopes = {
            "snmp_poll": False,
            "snmp_trap_listen": False,
        }

        # Test SNMP polling
        try:
            results = self._snmp_poll()
            if results is not None:
                scopes["snmp_poll"] = True
                self.logger.info("SNMP polling scope validated successfully")
            else:
                scopes["snmp_poll"] = "SNMP polling returned no data"
        except Exception as e:
            self.logger.warning(f"SNMP polling scope validation failed: {e}")
            scopes["snmp_poll"] = f"SNMP poll failed: {e}"

        # Trap listening scope — just check if we can bind the port
        if self.authentication_config.trap_enabled:
            try:
                self._check_trap_port_available()
                scopes["snmp_trap_listen"] = True
                self.logger.info("SNMP trap listener scope validated successfully")
            except Exception as e:
                self.logger.warning(f"SNMP trap listener scope validation failed: {e}")
                scopes["snmp_trap_listen"] = f"SNMP trap listen failed: {e}"
        else:
            scopes["snmp_trap_listen"] = "Trap listener not enabled"

        return scopes

    def _check_trap_port_available(self):
        """Check if the trap port is available for binding."""
        import socket

        trap_port = self.authentication_config.trap_port
        trap_host = self.authentication_config.trap_host
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((trap_host, trap_port))
        except OSError as e:
            raise Exception(f"Cannot bind trap port {trap_host}:{trap_port}: {e}")

    async def _snmp_poll_async(self) -> list[dict]:
        """
        Async SNMP GET polling on configured OIDs using pysnmp-lextudio v6 hlapi.
        Returns a list of dicts with OID, value, type, and error info.
        """
        from pysnmp.hlapi.asyncio import (
            getCmd,
            SnmpEngine,
            CommunityData,
            UdpTransportTarget,
            ContextData,
            ObjectType,
            ObjectIdentity,
            UsmUserData,
        )

        host = self.authentication_config.host
        port = self.authentication_config.port
        community = self.authentication_config.community
        version = self.authentication_config.snmp_version

        # Parse OIDs
        oid_list = [
            oid.strip()
            for oid in self.authentication_config.oids.split(",")
            if oid.strip()
        ]
        if not oid_list:
            self.logger.warning("No OIDs configured for polling")
            return []

        results = []

        for oid in oid_list:
            try:
                snmp_engine = SnmpEngine()

                # Build auth data based on SNMP version
                if version in (1, 2):
                    # mpModel: 0 = SNMPv1, 1 = SNMPv2c
                    mp_model = 0 if version == 1 else 1
                    auth_data = CommunityData(community, mpModel=mp_model)
                else:
                    # SNMP v3
                    auth_proto = _get_auth_protocol(
                        self.authentication_config.auth_protocol
                    )
                    priv_proto = _get_priv_protocol(
                        self.authentication_config.priv_protocol
                    )
                    auth_data = UsmUserData(
                        self.authentication_config.security_username,
                        self.authentication_config.auth_key or "",
                        self.authentication_config.priv_key or "",
                        authProtocol=auth_proto,
                        privProtocol=priv_proto,
                    )

                transport = UdpTransportTarget(
                    (host, port), timeout=5.0, retries=2
                )
                object_type = ObjectType(ObjectIdentity(oid))

                error_indication, error_status, error_index, var_binds = await getCmd(
                    snmp_engine,
                    auth_data,
                    transport,
                    ContextData(),
                    object_type,
                )

                if error_indication:
                    self.logger.warning(
                        f"SNMP GET error for OID {oid}: {error_indication}"
                    )
                    results.append(
                        {
                            "oid": oid,
                            "value": None,
                            "error": str(error_indication),
                            "type": "error",
                        }
                    )
                elif error_status:
                    self.logger.warning(
                        f"SNMP GET error for OID {oid}: {error_status} at {error_index}"
                    )
                    results.append(
                        {
                            "oid": oid,
                            "value": None,
                            "error": f"{error_status} at {error_index}",
                            "type": "error",
                        }
                    )
                else:
                    for var_bind in var_binds:
                        oid_result = str(var_bind[0])
                        value_result = str(var_bind[1])
                        results.append(
                            {
                                "oid": oid_result,
                                "value": value_result,
                                "error": None,
                                "type": type(var_bind[1]).__name__,
                            }
                        )

            except Exception as e:
                self.logger.error(f"SNMP GET failed for OID {oid}: {e}")
                results.append(
                    {
                        "oid": oid,
                        "value": None,
                        "error": str(e),
                        "type": "error",
                    }
                )

        return results

    def _snmp_poll(self) -> list[dict]:
        """Synchronous wrapper for async SNMP polling."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # If already in an async context, run in a separate thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self._snmp_poll_async())
                return future.result(timeout=30)
        else:
            return asyncio.run(self._snmp_poll_async())

    def _query(self, **kwargs: dict) -> list[AlertDto]:
        """
        Query SNMP-enabled devices and return alerts.
        Called by Keep for polling-based alert retrieval.

        Optional kwargs:
            - oids: override configured OIDs
            - host: override configured host
        """
        oids_override = kwargs.get("oids")
        host_override = kwargs.get("host")

        original_oids = self.authentication_config.oids
        original_host = self.authentication_config.host

        if oids_override:
            self.authentication_config.oids = oids_override
        if host_override:
            self.authentication_config.host = host_override

        try:
            poll_results = self._snmp_poll()
        finally:
            self.authentication_config.oids = original_oids
            self.authentication_config.host = original_host

        alerts = []
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for result in poll_results:
            alert = AlertDto(
                id=str(uuid.uuid4()),
                name=f"SNMP Poll - {result['oid']}",
                description=(
                    f"SNMP GET error for OID {result['oid']}: {result['error']}"
                    if result.get("error")
                    else (
                        f"SNMP GET result for OID {result['oid']}: "
                        f"{result['value']} (type: {result.get('type', 'unknown')})"
                    )
                ),
                status=(
                    AlertStatus.FIRING
                    if result.get("error")
                    else AlertStatus.RESOLVED
                ),
                severity=(
                    AlertSeverity.WARNING
                    if result.get("error")
                    else AlertSeverity.INFO
                ),
                lastReceived=now,
                source=["snmp"],
                labels={
                    "oid": result["oid"],
                    "host": self.authentication_config.host,
                    "snmp_version": str(self.authentication_config.snmp_version),
                    "snmp_type": result.get("type", "unknown"),
                    "value": result.get("value") or "",
                    "error": result.get("error") or "",
                },
            )
            alerts.append(alert)

        return alerts

    def _get_alerts(self) -> list[AlertDto]:
        """Get alerts from SNMP polling."""
        return self._query()

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a raw SNMP trap event into a Keep AlertDto.
        Used when SNMP traps are pushed to Keep via webhook or the trap listener.

        Expected event format:
        {
            "trap_oid": "1.3.6.1.6.3.1.1.5.1",
            "source": "192.168.1.1",
            "var_binds": {
                "1.3.6.1.2.1.1.3.0": "12345",
                "1.3.6.1.6.3.1.1.4.1.0": "1.3.6.1.6.3.1.1.5.1"
            },
            "timestamp": "2024-01-01T00:00:00Z",
            "community": "public",
            "snmp_version": 2
        }
        """
        trap_oid = event.get("trap_oid", "unknown")
        source = event.get("source", "unknown")
        var_binds = event.get("var_binds", {})
        timestamp = event.get(
            "timestamp",
            datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        community = event.get("community", "")
        snmp_version = event.get("snmp_version", 2)

        # Determine trap name and severity from well-known OIDs
        trap_name = SNMP_TRAP_NAMES.get(trap_oid, f"SNMP Trap - {trap_oid}")
        severity = SNMP_TRAP_SEVERITY_MAP.get(trap_oid, AlertSeverity.INFO)

        # Build description from var_binds
        var_bind_parts = [f"{oid} = {val}" for oid, val in var_binds.items()]
        description = f"SNMP Trap ({trap_name}) from {source}:\n" + "\n".join(
            var_bind_parts
        )

        alert = AlertDto(
            id=str(uuid.uuid4()),
            name=trap_name,
            description=description,
            status=AlertStatus.FIRING,
            severity=severity,
            lastReceived=timestamp,
            source=["snmp"],
            message=description,
            labels={
                "trap_oid": trap_oid,
                "source": source,
                "community": community,
                "snmp_version": str(snmp_version),
            },
        )

        return alert

    def status(self) -> dict:
        """Return the status of the SNMP provider."""
        trap_status = "not-enabled"
        if self.authentication_config.trap_enabled:
            if self._trap_thread and self._trap_thread.is_alive():
                trap_status = "listening"
            else:
                trap_status = "stopped"

        return {
            "status": "active",
            "trap_listener": trap_status,
            "host": self.authentication_config.host,
            "port": self.authentication_config.port,
            "snmp_version": self.authentication_config.snmp_version,
            "error": "",
        }

    def start_consume(self):
        """
        Start the SNMP trap listener in a background thread.
        Received traps are pushed as alerts via _push_alert().
        """
        if not self.authentication_config.trap_enabled:
            self.logger.warning(
                "SNMP trap listener is not enabled. "
                "Set trap_enabled=true in configuration to enable."
            )
            return

        self.consume = True
        self._trap_thread = threading.Thread(
            target=self._run_trap_listener, daemon=True
        )
        self._trap_thread.start()
        self.logger.info(
            f"SNMP trap listener starting on "
            f"{self.authentication_config.trap_host}:{self.authentication_config.trap_port}"
        )

    def stop_consume(self):
        """Stop the SNMP trap listener."""
        self.consume = False
        self.logger.info("SNMP trap listener stopped")

    def _run_trap_listener(self):
        """
        Run the SNMP trap listener using pysnmp-lextudio v6 low-level entity API.
        This runs in a daemon thread. It creates its own asyncio event loop
        and starts the pysnmp dispatcher to receive traps.
        """
        from pysnmp.entity import engine, config
        from pysnmp.entity.rfc3413 import ntfrcv
        from pysnmp.carrier.asyncio.dgram import udp

        trap_host = self.authentication_config.trap_host
        trap_port = self.authentication_config.trap_port
        version = self.authentication_config.snmp_version
        community = self.authentication_config.community

        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        snmp_engine = engine.SnmpEngine()

        # Configure community for v1/v2c trap reception
        if version in (1, 2):
            config.addV1System(snmp_engine, community, community)
        else:
            # SNMP v3 — configure USM user
            auth_proto = _get_auth_protocol(self.authentication_config.auth_protocol)
            priv_proto = _get_priv_protocol(self.authentication_config.priv_protocol)
            config.addV3User(
                snmp_engine,
                self.authentication_config.security_username,
                auth_proto,
                self.authentication_config.auth_key or "",
                priv_proto,
                self.authentication_config.priv_key or "",
            )

        # Create and configure UDP transport for trap reception.
        # openServerMode() is synchronous — it schedules the endpoint on the loop
        # and returns self.
        transport = udp.UdpAsyncioTransport(loop=loop)
        transport.openServerMode((trap_host, trap_port))
        config.addTransport(snmp_engine, udp.domainName, transport)

        # Define callback for received traps.
        # The ntfrcv.NotificationReceiver first attempts the legacy 5-arg
        # callback signature:
        #   cbFun(snmpEngine, contextEngineId, contextName, varBinds, cbCtx)
        # If that raises TypeError, it retries with the 6-arg signature:
        #   cbFun(snmpEngine, stateReference, contextEngineId, contextName,
        #         varBinds, cbCtx)
        # We implement the 5-arg version for maximum compatibility.
        def trap_callback(snmp_engine_cb, context_engine_id, context_name, var_binds, cb_ctx):
            """Callback invoked when an SNMP trap is received."""
            try:
                # Determine source address from transport info
                source_addr = "unknown"

                # Parse var_binds into a dict and extract snmpTrapOID
                var_binds_dict = {}
                trap_oid = "unknown"
                for oid, val in var_binds:
                    oid_str = str(oid)
                    val_str = str(val)
                    var_binds_dict[oid_str] = val_str
                    # snmpTrapOID is always at 1.3.6.1.6.3.1.1.4.1.0
                    if oid_str == "1.3.6.1.6.3.1.1.4.1.0":
                        trap_oid = val_str

                # Build the trap event dict and push as alert
                trap_event = {
                    "trap_oid": trap_oid,
                    "source": source_addr,
                    "var_binds": var_binds_dict,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "community": community,
                    "snmp_version": version,
                }

                self._push_alert(trap_event)
                self.logger.info(
                    f"SNMP trap received: {trap_oid} (var_binds: {len(var_binds_dict)})"
                )

            except Exception as e:
                self.logger.error(f"Error processing SNMP trap: {e}")

        # Register the notification receiver
        ntfrcv.NotificationReceiver(snmp_engine, trap_callback)

        # Run the dispatcher — openDispatcher() calls transportDispatcher.runDispatcher()
        # which runs loop.run_forever(), blocking this thread until the loop is stopped.
        self.logger.info(
            f"SNMP trap listener active on {trap_host}:{trap_port}"
        )
        try:
            snmp_engine.openDispatcher()
        except Exception as e:
            if self.consume:
                self.logger.error(f"SNMP trap listener error: {e}")
            else:
                self.logger.info("SNMP trap listener shut down cleanly")
        finally:
            loop.close()


if __name__ == "__main__":
    import os
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    host = os.environ.get("SNMP_HOST", "demo.snmplabs.com")
    community = os.environ.get("SNMP_COMMUNITY", "public")
    version = int(os.environ.get("SNMP_VERSION", "2"))

    config = ProviderConfig(
        description="SNMP Provider",
        authentication={
            "host": host,
            "community": community,
            "snmp_version": version,
            "oids": "1.3.6.1.2.1.1.1.0,1.3.6.1.2.1.1.3.0",
            "trap_enabled": False,
        },
    )

    provider = SnmpProvider(
        context_manager,
        provider_id="snmp",
        config=config,
    )

    # Test polling
    alerts = provider._get_alerts()
    for alert in alerts:
        print(f"Alert: {alert.name} - {alert.description}")

    # Test format_alert
    test_trap = {
        "trap_oid": "1.3.6.1.6.3.1.1.5.1",
        "source": "192.168.1.1",
        "var_binds": {
            "1.3.6.1.2.1.1.3.0": "12345",
            "1.3.6.1.6.3.1.1.4.1.0": "1.3.6.1.6.3.1.1.5.1",
        },
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "community": "public",
        "snmp_version": 2,
    }
    formatted = SnmpProvider._format_alert(test_trap)
    print(f"Formatted trap: {formatted.name} - {formatted.description}")
