"""
SNMP Provider is a class that allows ingesting SNMP traps as Keep alerts.
"""

import dataclasses
import logging
import threading

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP authentication configuration.
    """

    host: str = dataclasses.field(
        default="0.0.0.0",
        metadata={
            "required": False,
            "description": "The host/IP to listen on for SNMP traps",
            "hint": "0.0.0.0",
        },
    )
    port: int = dataclasses.field(
        default=162,
        metadata={
            "required": False,
            "description": "The UDP port to listen on for SNMP traps",
            "hint": "162 (standard SNMP trap port)",
        },
    )
    community: str = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": "SNMP v1/v2c community string",
            "hint": "public",
            "sensitive": True,
        },
    )
    version: str = dataclasses.field(
        default="2c",
        metadata={
            "required": False,
            "description": "SNMP version to use: 1, 2c, or 3",
            "hint": "2c",
        },
    )
    # SNMPv3 specific auth fields
    snmp_v3_user: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 USM username",
            "hint": "snmpuser",
        },
    )
    snmp_v3_auth_key: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 authentication key (required for authNoPriv/authPriv)",
            "hint": "AuthKey12345",
            "sensitive": True,
        },
    )
    snmp_v3_auth_protocol: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 auth protocol: MD5 or SHA (default: SHA)",
            "hint": "SHA",
        },
    )
    snmp_v3_priv_key: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 privacy key (required for authPriv)",
            "hint": "PrivKey12345",
            "sensitive": True,
        },
    )
    snmp_v3_priv_protocol: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 privacy protocol: DES or AES (default: AES)",
            "hint": "AES",
        },
    )


class SnmpProvider(BaseProvider):
    """
    SNMP provider class that listens for SNMP traps and pushes them as Keep alerts.
    """

    PROVIDER_CATEGORY = ["Monitoring", "Networking"]
    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_SCOPES = [
        ProviderScope(
            name="receive_traps",
            description="The ability to receive SNMP traps",
            mandatory=True,
            alias="Receive Traps",
        )
    ]
    PROVIDER_TAGS = ["network", "snmp"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.consume = False
        self._snmp_engine = None
        self._dispatcher_thread = None
        self.err = ""

    def validate_config(self):
        """
        Validates required configuration for SNMP provider.
        """
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        """
        Validate that the SNMP provider can listen for traps.
        """
        scopes = {"receive_traps": True}
        try:
            version = self.authentication_config.version
            if version not in ("1", "2c", "3"):
                self.err = f"Invalid SNMP version: {version}. Must be 1, 2c, or 3."
                scopes["receive_traps"] = self.err
                return scopes

            if version == "3":
                if not self.authentication_config.snmp_v3_user:
                    self.err = "SNMPv3 requires snmp_v3_user to be set"
                    scopes["receive_traps"] = self.err
                    return scopes

            port = self.authentication_config.port
            if not (1 <= port <= 65535):
                self.err = f"Invalid port number: {port}"
                scopes["receive_traps"] = self.err
                return scopes

        except Exception as e:
            self.err = str(e)
            self.logger.warning(f"Error validating SNMP config: {e}")
            scopes["receive_traps"] = self.err

        return scopes

    def dispose(self):
        """
        Dispose the provider - stop the listener.
        """
        self.stop_consume()

    def status(self):
        """
        Get the status of the SNMP provider.
        """
        if self._snmp_engine is None and self._dispatcher_thread is None:
            status = "not-initialized"
        elif self.consume:
            status = "listening"
        else:
            status = "stopped"

        return {
            "status": status,
            "error": self.err,
        }

    def _build_snmp_engine(self):
        """
        Build and configure the pysnmp SNMP engine for receiving traps.
        Uses the pysnmp-lextudio v6 asyncio API.
        """
        from pysnmp.entity import engine, config
        from pysnmp.carrier.asyncio.dgram import udp
        from pysnmp.entity.rfc3413 import ntfrcv

        snmp_engine = engine.SnmpEngine()
        version = self.authentication_config.version

        # Create UDP transport (server mode for receiving traps)
        transport = udp.UdpTransport()
        transport.open_server_mode(
            (self.authentication_config.host, self.authentication_config.port)
        )

        # Register transport with the engine
        config.add_transport(snmp_engine, udp.DOMAIN_NAME, transport)

        if version in ("1", "2c"):
            # SNMPv1/v2c: configure community
            mp_model = 0 if version == "1" else 1
            config.add_v1_system(
                snmp_engine,
                snmpEngineID=None,
                communityName=self.authentication_config.community,
            )
            config.add_target_parameters(
                snmp_engine,
                "npiParams",
                self.authentication_config.community,
                mp_model,
            )
        elif version == "3":
            # SNMPv3: configure USM user
            auth_protocol = config.usmHMACSHAAuthProtocol
            if self.authentication_config.snmp_v3_auth_protocol:
                if self.authentication_config.snmp_v3_auth_protocol.upper() == "MD5":
                    auth_protocol = config.usmHMACMD5AuthProtocol

            priv_protocol = config.usmAesCfb128Protocol
            if self.authentication_config.snmp_v3_priv_protocol:
                if self.authentication_config.snmp_v3_priv_protocol.upper() == "DES":
                    priv_protocol = config.usmDESPrivProtocol

            if self.authentication_config.snmp_v3_priv_key:
                # authPriv
                config.add_v3_user(
                    snmp_engine,
                    self.authentication_config.snmp_v3_user,
                    auth_protocol,
                    self.authentication_config.snmp_v3_auth_key,
                    priv_protocol,
                    self.authentication_config.snmp_v3_priv_key,
                )
            elif self.authentication_config.snmp_v3_auth_key:
                # authNoPriv
                config.add_v3_user(
                    snmp_engine,
                    self.authentication_config.snmp_v3_user,
                    auth_protocol,
                    self.authentication_config.snmp_v3_auth_key,
                )
            else:
                # noAuthNoPriv
                config.add_v3_user(
                    snmp_engine,
                    self.authentication_config.snmp_v3_user,
                )

        return snmp_engine, ntfrcv

    def _trap_callback(
        self, snmp_engine, state_reference, context_engine_id, context_name, var_binds, cb_ctx
    ):
        """
        Callback invoked by pysnmp v6 when a trap is received.
        Converts var-binds to a Keep alert dict and pushes it.
        """
        # Extract transport info from the SNMP engine observer
        transport_domain = b""
        transport_address = ("unknown", 0)
        try:
            exec_context = snmp_engine.observer.getExecutionContext(
                "rfc3412.receiveMessage"
            )
            transport_domain = exec_context.get("transportDomain", b"")
            transport_address = exec_context.get(
                "transportAddress", ("unknown", 0)
            )
        except Exception:
            self.logger.debug("Could not extract transport context from SNMP engine")

        alert_data = self._varbinds_to_alert(var_binds, transport_address)
        try:
            self._push_alert(alert_data)
            self.logger.info(
                f"SNMP trap pushed as alert: {alert_data.get('name', 'unknown')}"
            )
        except Exception:
            self.logger.warning("Error pushing SNMP trap alert to API", exc_info=True)

    @staticmethod
    def _varbinds_to_alert(var_binds, transport_info):
        """
        Convert pysnmp v6 var-binds into a Keep alert dict.

        In pysnmp v6, var_binds is a list of (oid, value) tuples
        passed directly to the NotificationReceiver callback.
        """
        import datetime
        import uuid

        alert = {
            "id": str(uuid.uuid4()),
            "lastReceived": datetime.datetime.now(
                tz=datetime.timezone.utc
            ).isoformat(),
            "source": ["snmp"],
            "environment": "production",
            "service": "network",
        }

        # Extract agent address from transport info
        agent_addr = "unknown"
        if transport_info and len(transport_info) >= 1:
            agent_addr = str(transport_info[0]) if transport_info[0] else "unknown"
        alert["description"] = f"SNMP trap received from {agent_addr}"

        var_bind_dict = {}
        trap_oid = ""
        trap_name = "SNMPTrap"

        # pysnmp v6: var_binds is a list of (ObjectType, value) tuples
        try:
            for var_bind in var_binds:
                if hasattr(var_bind, "__getitem__") and len(var_bind) >= 2:
                    oid_str = str(var_bind[0])
                    val = var_bind[1]

                    # Try to get a readable value
                    if hasattr(val, "prettyPrint"):
                        val_str = val.prettyPrint()
                    else:
                        val_str = str(val)

                    var_bind_dict[oid_str] = val_str

                    # Check if this is the snmpTrapOID (standard trap OID)
                    if oid_str == "1.3.6.1.6.3.1.1.4.1.0":
                        trap_oid = val_str
                        common_traps = {
                            "1.3.6.1.6.3.1.1.5.1": "coldStart",
                            "1.3.6.1.6.3.1.1.5.2": "warmStart",
                            "1.3.6.1.6.3.1.1.5.3": "linkDown",
                            "1.3.6.1.6.3.1.1.5.4": "linkUp",
                            "1.3.6.1.6.3.1.1.5.5": "authenticationFailure",
                        }
                        trap_name = common_traps.get(
                            trap_oid, trap_oid.split(".")[-1] if trap_oid else "SNMPTrap"
                        )
                elif hasattr(var_bind, "__iter__"):
                    # Try iterating as a pair
                    try:
                        pair = list(var_bind)
                        if len(pair) >= 2:
                            oid_str = str(pair[0])
                            val_str = str(pair[1])
                            if hasattr(pair[1], "prettyPrint"):
                                val_str = pair[1].prettyPrint()
                            var_bind_dict[oid_str] = val_str
                    except Exception:
                        pass
        except Exception:
            # If we can't iterate, just use what we have
            self.logger.debug(f"Could not parse var_binds: {type(var_binds)}")

        # Build alert name and message
        if trap_name and trap_name != "SNMPTrap":
            alert["name"] = f"SNMP {trap_name} from {agent_addr}"
            alert["message"] = (
                f"SNMP trap {trap_name} (OID: {trap_oid}) received from {agent_addr}"
            )
        else:
            alert["name"] = f"SNMP Trap from {agent_addr}"
            alert["message"] = f"SNMP trap received from {agent_addr}"

        # Determine severity
        severity_map = {
            "linkDown": "high",
            "authenticationFailure": "warning",
            "coldStart": "info",
            "warmStart": "info",
            "linkUp": "info",
        }
        alert["severity"] = severity_map.get(trap_name, "info")

        # Include all var-binds as extra data
        alert["snmp_trap"] = {
            "agent_addr": agent_addr,
            "trap_oid": trap_oid or "unknown",
            "trap_name": trap_name,
            "var_binds": var_bind_dict,
        }

        return alert

    def start_consume(self):
        """
        Start listening for SNMP traps in a background thread.
        Uses the pysnmp v6 asyncio API internally.
        """
        self.consume = True
        self.logger.info(
            f"Starting SNMP trap listener on {self.authentication_config.host}:{self.authentication_config.port}"
        )

        def _run_dispatcher():
            """Run the SNMP engine dispatcher in a background thread."""
            import asyncio

            try:
                snmp_engine, ntfrcv = self._build_snmp_engine()

                # Register the trap receiver callback
                ntfrcv.NotificationReceiver(
                    snmp_engine,
                    self._trap_callback,
                )

                self._snmp_engine = snmp_engine
                self.logger.info("SNMP trap listener started successfully")

                # Create a new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                # Run the dispatcher (blocking call)
                snmp_engine.open_dispatcher()
                loop.run_forever()

            except Exception:
                self.logger.exception("Error in SNMP trap listener")
                self.err = "Failed to start SNMP trap listener"
            finally:
                self.logger.info("SNMP trap listener stopped")

        self._dispatcher_thread = threading.Thread(
            target=_run_dispatcher, daemon=True
        )
        self._dispatcher_thread.start()

    def stop_consume(self):
        """
        Stop listening for SNMP traps.
        """
        self.consume = False
        if self._snmp_engine:
            try:
                self._snmp_engine.close_dispatcher()
            except Exception:
                self.logger.debug("Error stopping SNMP dispatcher", exc_info=True)
            self._snmp_engine = None
        if self._dispatcher_thread:
            self._dispatcher_thread = None


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    os.environ["KEEP_API_URL"] = "http://localhost:8080"

    from keep.api.core.dependencies import SINGLE_TENANT_UUID
    from keep.providers.providers_factory import ProvidersFactory

    context_manager = ContextManager(tenant_id=SINGLE_TENANT_UUID)
    config = {
        "authentication": {
            "host": "0.0.0.0",
            "port": 1162,
            "community": "public",
            "version": "2c",
        }
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="snmp-keephq",
        provider_type="snmp",
        provider_config=config,
    )
    provider.start_consume()