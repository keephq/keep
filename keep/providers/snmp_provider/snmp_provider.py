"""
SNMP Provider for monitoring network devices and receiving SNMP traps.
"""

import dataclasses
import logging
from typing import Optional
from enum import Enum
import uuid
import hashlib
import datetime
import asyncio

import pydantic
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData, UdpTransportTarget, ObjectType, ObjectIdentity,
    get_cmd, set_cmd, next_cmd, bulk_cmd, UsmUserData, SnmpEngine, ContextData
)
from pysnmp.hlapi.v3arch.asyncio.auth import (
    usmHMACMD5AuthProtocol, usmHMACSHAAuthProtocol,
    usmDESPrivProtocol, usmAesCfb128Protocol
)
from pysnmp.carrier.asyncio.dispatch import AsyncioDispatcher
from pysnmp.carrier.asyncio.dgram import udp, udp6
from pysnmp.proto import api
from pysnmp.proto.api import v2c as proto_v2c  # noqa: F401 - Used dynamically
from pysnmp.proto.api import v1 as proto_v1  # noqa: F401 - Used dynamically
from pyasn1.codec.ber import decoder

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


class SnmpVersion(str, Enum):
    V1 = "v1"
    V2C = "v2c"
    V3 = "v3"


class SnmpAuthProtocol(str, Enum):
    MD5 = "md5"
    SHA = "sha"


class SnmpPrivProtocol(str, Enum):
    DES = "des"
    AES = "aes"


class SnmpSecurityLevel(str, Enum):
    NO_AUTH_NO_PRIV = "noAuthNoPriv"
    AUTH_NO_PRIV = "authNoPriv"
    AUTH_PRIV = "authPriv"


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP authentication configuration.
    """
    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SNMP agent host",
            "hint": "IP address or hostname of the SNMP agent",
            "sensitive": False,
        }
    )
    version: SnmpVersion = dataclasses.field(
        metadata={
            "required": True,
            "description": "SNMP version",
            "hint": "SNMP protocol version (v1, v2c, v3)",
            "sensitive": False,
        }
    )
    port: int = dataclasses.field(
        default=161,
        metadata={
            "required": False,
            "description": "SNMP agent port (default: 161)",
            "hint": "Port number for SNMP communication",
            "sensitive": False,
        }
    )
    community_string: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Community string (required for v1/v2c)",
            "hint": "SNMP community string for authentication",
            "sensitive": True,
        }
    )
    # v3 specific fields
    username: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Username (required for v3)",
            "hint": "SNMPv3 username",
            "sensitive": False,
        }
    )
    auth_protocol: Optional[SnmpAuthProtocol] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Authentication protocol (v3)",
            "hint": "SNMPv3 authentication protocol (MD5, SHA)",
            "sensitive": False,
        }
    )
    auth_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Authentication key (v3)",
            "hint": "SNMPv3 authentication passphrase",
            "sensitive": True,
        }
    )
    priv_protocol: Optional[SnmpPrivProtocol] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Privacy protocol (v3)",
            "hint": "SNMPv3 privacy protocol (DES, AES)",
            "sensitive": False,
        }
    )
    priv_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Privacy key (v3)",
            "hint": "SNMPv3 privacy passphrase",
            "sensitive": True,
        }
    )
    security_level: Optional[SnmpSecurityLevel] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Security level (v3)",
            "hint": "SNMPv3 security level (noAuthNoPriv, authNoPriv, authPriv)",
            "sensitive": False,
        }
    )
    trap_port: Optional[int] = dataclasses.field(
        default=1162,
        metadata={
            "required": False,
            "description": "Port to listen for SNMP traps (default: 1162)",
            "hint": "UDP port for receiving SNMP traps. Use 1162 for unprivileged port access.",
            "sensitive": False,
        }
    )


class SnmpProvider(BaseProvider):
    """Provider for SNMP monitoring and trap receiving."""

    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert", "data"]
    PROVIDER_DISPLAY_NAME = "SNMP"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read",
            description="Required for reading SNMP data from agents",
            mandatory=True,
            alias="Read Access",
        ),
        ProviderScope(
            name="write",
            description="Required for setting SNMP values on agents",
            mandatory=False,
            alias="Write Access",
        ),
        ProviderScope(
            name="trap",
            description="Required for receiving SNMP traps",
            mandatory=False,
            alias="Trap Receiver",
        ),
    ]

    alert_severity_dict = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.consume = False
        self.trap_engine = None
        self.err = ""

    def dispose(self):
        """Dispose of the provider."""
        if self.trap_engine:
            self.stop_consume()

    def validate_config(self):
        """Validates required configuration for SNMP provider."""
        self.logger.debug("Validating configuration for SNMP provider")
        self.authentication_config = SnmpProviderAuthConfig(**self.config.authentication)

        # Validate version-specific requirements
        if self.authentication_config.version in [SnmpVersion.V1, SnmpVersion.V2C]:
            if not self.authentication_config.community_string:
                raise ValueError("Community string is required for SNMP v1/v2c")
        elif self.authentication_config.version == SnmpVersion.V3:
            if not self.authentication_config.username:
                raise ValueError("Username is required for SNMP v3")
            
            if self.authentication_config.security_level == SnmpSecurityLevel.AUTH_NO_PRIV:
                if not (self.authentication_config.auth_protocol and self.authentication_config.auth_key):
                    raise ValueError("Authentication protocol and key are required for authNoPriv security level")
            elif self.authentication_config.security_level == SnmpSecurityLevel.AUTH_PRIV:
                if not (self.authentication_config.auth_protocol and self.authentication_config.auth_key):
                    raise ValueError("Authentication protocol and key are required for authPriv security level")
                if not (self.authentication_config.priv_protocol and self.authentication_config.priv_key):
                    raise ValueError("Privacy protocol and key are required for authPriv security level")

    async def _get_session_args(self):
        """Get the appropriate SNMP session arguments based on version and authentication."""
        auth_data = None
        if self.authentication_config.version in [SnmpVersion.V1, SnmpVersion.V2C]:
            auth_data = CommunityData(
                self.authentication_config.community_string,
                mpModel=0 if self.authentication_config.version == SnmpVersion.V1 else 1
            )
        else:  # v3
            auth_protocol = None
            priv_protocol = None
            
            if self.authentication_config.auth_protocol == SnmpAuthProtocol.MD5:
                auth_protocol = usmHMACMD5AuthProtocol
            elif self.authentication_config.auth_protocol == SnmpAuthProtocol.SHA:
                auth_protocol = usmHMACSHAAuthProtocol

            if self.authentication_config.priv_protocol == SnmpPrivProtocol.DES:
                priv_protocol = usmDESPrivProtocol
            elif self.authentication_config.priv_protocol == SnmpPrivProtocol.AES:
                priv_protocol = usmAesCfb128Protocol

            if self.authentication_config.security_level == SnmpSecurityLevel.NO_AUTH_NO_PRIV:
                auth_data = UsmUserData(self.authentication_config.username)
            elif self.authentication_config.security_level == SnmpSecurityLevel.AUTH_NO_PRIV:
                auth_data = UsmUserData(
                    self.authentication_config.username,
                    authKey=self.authentication_config.auth_key,
                    authProtocol=auth_protocol
                )
            else:  # AUTH_PRIV
                auth_data = UsmUserData(
                    self.authentication_config.username,
                    authKey=self.authentication_config.auth_key,
                    privKey=self.authentication_config.priv_key,
                    authProtocol=auth_protocol,
                    privProtocol=priv_protocol
                )

        # Create and configure the transport target
        transport_target = await UdpTransportTarget.create((self.authentication_config.host, self.authentication_config.port))

        return {
            'auth_data': auth_data,
            'target': transport_target
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate provider scopes by testing basic connectivity."""
        import asyncio
        
        self.logger.info("Validating scopes for SNMP provider")
        scopes = {
            scope.name: False for scope in self.PROVIDER_SCOPES
        }

        async def _validate_scopes():
            # Test read access with sysDescr.0
            try:
                session_args = await self._get_session_args()
                engine = SnmpEngine()
                context_data = ContextData()
                
                response = await get_cmd(
                    engine,
                    session_args['auth_data'],
                    session_args['target'],
                    context_data,
                    ObjectType(ObjectIdentity('SNMPv2-MIB', 'sysDescr', 0))
                )
                errorIndication, errorStatus, errorIndex, varBinds = response
                
                if errorIndication:
                    scopes["read"] = str(errorIndication)
                elif errorStatus:
                    scopes["read"] = f'Error: {errorStatus.prettyPrint()} at {errorIndex}'
                else:
                    scopes["read"] = True
            except Exception as e:
                scopes["read"] = str(e)

            # Test write access if requested
            if "write" in [scope.name for scope in self.PROVIDER_SCOPES]:
                try:
                    # Try to set sysContact.0 to test value and immediately read it back
                    test_value = "keep_test"
                    session_args = await self._get_session_args()
                    engine = SnmpEngine()
                    context_data = ContextData()
                    
                    response = await set_cmd(
                        engine,
                        session_args['auth_data'],
                        session_args['target'],
                        context_data,
                        ObjectType(ObjectIdentity('SNMPv2-MIB', 'sysContact', 0), test_value)
                    )
                    errorIndication, errorStatus, errorIndex, varBinds = response
                    
                    if errorIndication:
                        scopes["write"] = str(errorIndication)
                    elif errorStatus:
                        scopes["write"] = f'Error: {errorStatus.prettyPrint()} at {errorIndex}'
                    else:
                        scopes["write"] = True
                except Exception as e:
                    scopes["write"] = str(e)

            # Start trap receiver if trap scope is requested
            if "trap" in [scope.name for scope in self.PROVIDER_SCOPES]:
                try:
                    # Start the trap receiver in the background
                    self.start_consume()
                    scopes["trap"] = True
                except Exception as e:
                    scopes["trap"] = str(e)

            return scopes

        # Run the async validation in a way that works with FastAPI
        try:
            # If we're already in an event loop, create a new one in a thread
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    raise RuntimeError("Event loop is closed")
                if loop.is_running():
                    # We're in an async context, just run the coroutine
                    return asyncio.run_coroutine_threadsafe(_validate_scopes(), loop).result()
            except RuntimeError:
                # No event loop exists, create a new one
                return asyncio.run(_validate_scopes())
        except Exception as e:
            self.logger.error(f"Error validating scopes: {str(e)}")
            # Return error status for all scopes
            return {name: str(e) for name in scopes.keys()}

    def _query(self, operation: str, oids: list[str], value=None):
        """Execute SNMP query operations (GET, GETNEXT, WALK, SET)."""
        import asyncio
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            async def _do_query():
                session_args = await self._get_session_args()
                results = []

                try:
                    for oid in oids:
                        obj_identity = ObjectIdentity(oid)
                        if operation == "get":
                            response = await get_cmd(
                                SnmpEngine(),
                                session_args['auth_data'],
                                session_args['target'],
                                ContextData(),
                                ObjectType(obj_identity)
                            )
                        elif operation == "getnext":
                            response = await next_cmd(
                                SnmpEngine(),
                                session_args['auth_data'],
                                session_args['target'],
                                ContextData(),
                                ObjectType(obj_identity)
                            )
                        elif operation == "walk":
                            response = await next_cmd(
                                SnmpEngine(),
                                session_args['auth_data'],
                                session_args['target'],
                                ContextData(),
                                ObjectType(obj_identity),
                                lexicographicMode=False
                            )
                        elif operation == "set":
                            if value is None:
                                raise ValueError("Value is required for SET operation")
                            response = await set_cmd(
                                SnmpEngine(),
                                session_args['auth_data'],
                                session_args['target'],
                                ContextData(),
                                ObjectType(obj_identity, value)
                            )
                        else:
                            raise ValueError(f"Unsupported operation: {operation}")

                        error_indication, error_status, error_index, var_binds = response
                        if error_indication:
                            raise RuntimeError(str(error_indication))
                        elif error_status:
                            raise RuntimeError(f'{error_status.prettyPrint()} at {error_index}')
                        
                        for var_bind in var_binds:
                            name, val = var_bind
                            results.append({
                                'oid': str(name),
                                'value': str(val)
                            })

                        # For GET and SET, we only want the first result
                        if operation in ["get", "set"]:
                            break

                except Exception as e:
                    self.logger.error(f"Error in SNMP {operation} operation", extra={"error": str(e)})
                    raise

                return results

            return loop.run_until_complete(_do_query())
        finally:
            loop.close()

    def _notify(self, oids: list[str], value, **kwargs):
        """Execute SNMP SET operation."""
        import asyncio
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self._query("set", oids, value))
            finally:
                loop.close()
        except Exception as e:
            self.logger.error("Error in SNMP SET operation", extra={"error": str(e)})
            raise

    @staticmethod
    def _format_alert(trap_data: dict) -> AlertDto:
        """Format SNMP trap data into an AlertDto."""
        # Extract basic info from trap
        enterprise_oid = trap_data.get('enterprise_oid', '')
        trap_type = trap_data.get('trap_type', '')
        agent_addr = trap_data.get('agent_addr', '')
        var_binds = trap_data.get('var_binds', [])

        # Try to determine severity from trap type or varbinds
        severity_str = 'info'  # Default severity string
        for varbind in var_binds:
            if 'severity' in varbind['oid'].lower():
                val = varbind['value'].lower()
                if 'critical' in val:
                    severity_str = 'critical'
                elif 'error' in val or 'major' in val:
                    severity_str = 'high'
                elif 'warning' in val or 'minor' in val:
                    severity_str = 'warning'
                break  # Found severity, stop searching

        # Map the string to the enum value
        severity = SnmpProvider.alert_severity_dict.get(severity_str, AlertSeverity.INFO)

        # Build alert message from varbinds
        message_parts = []
        for varbind in var_binds:
            message_parts.append(f"{varbind['oid']}: {varbind['value']}")
        message = "\n".join(message_parts)

        # Create alert with proper enum values
        return AlertDto(
            id=str(uuid.uuid4()),
            name=f"SNMP Trap from {agent_addr}",
            description=f"Enterprise: {enterprise_oid}\nTrap Type: {trap_type}\n{message}",
            severity=severity,  # Using the enum value directly
            status=AlertStatus.FIRING,
            source=[agent_addr],  # Pass source as a list
            lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(), # Use timezone aware datetime
            fingerprint=hashlib.sha256(f"{enterprise_oid}:{trap_type}:{agent_addr}:{message}".encode()).hexdigest()
        )

    def start_consume(self):
        """Start the SNMP trap receiver."""
        if "trap" not in [scope.name for scope in self.PROVIDER_SCOPES]:
            self.logger.warning("Trap scope not enabled, not starting trap receiver")
            return

        if self.trap_engine:
            self.logger.info("Trap receiver already running")
            return

        self.consume = True
        self.logger.info("Starting SNMP trap receiver")

        try:
            # Configure trap receiver
            transport_dispatcher = AsyncioDispatcher()
            
            # Create a new event loop for the dispatcher
            loop = asyncio.new_event_loop()

            # Register the async trap handler
            transport_dispatcher.register_recv_callback(
                lambda dispatcher, domain, addr, msg: 
                    asyncio.run_coroutine_threadsafe(
                        self._handle_trap(dispatcher, domain, addr, msg),
                        loop
                    ).result()
            )

            # Get trap port, defaulting to 1162 if not specified
            trap_port = self.authentication_config.trap_port or 1162

            try:
                # UDP/IPv4
                transport_dispatcher.register_transport(
                    udp.domainName,
                    udp.UdpTransport().openServerMode(('0.0.0.0', trap_port))
                )

                # UDP/IPv6
                transport_dispatcher.register_transport(
                    udp6.domainName,
                    udp6.Udp6Transport().openServerMode(('::0', trap_port))
                )
            except PermissionError as e:
                if trap_port < 1024:
                    self.logger.error(f"Permission denied to bind to privileged port {trap_port}. Try using port 1162 or higher.", extra={"error": str(e)})
                raise
            except OSError as e:
                if "Address already in use" in str(e):
                    self.logger.error(f"Port {trap_port} is already in use. Try a different port.", extra={"error": str(e)})
                elif "Cannot assign requested address" in str(e):
                    self.logger.error(f"Cannot bind to port {trap_port}. If running in Docker, ensure the port is properly exposed.", extra={"error": str(e)})
                raise

            self.trap_engine = transport_dispatcher
            transport_dispatcher.job_started(1)  # this job will never finish

            # Run the trap receiver in a separate thread
            import threading
            def run_dispatcher():
                try:
                    # Set the event loop for this thread
                    asyncio.set_event_loop(loop)
                    # Start the loop before running the dispatcher
                    loop.run_forever()
                except Exception as e:
                    if self.consume:  # Only log if we haven't stopped intentionally
                        self.logger.error("Error in trap receiver", extra={"error": str(e)})
                        raise
                finally:
                    loop.close()

            thread = threading.Thread(target=run_dispatcher, daemon=True)
            thread.start()

            # Run the dispatcher in the event loop
            asyncio.run_coroutine_threadsafe(
                self._run_dispatcher(transport_dispatcher),
                loop
            )

            self.logger.info(f"SNMP trap receiver started on port {trap_port} (container internal)")
            self.logger.info("Note: If running in Docker, ensure this port is properly exposed to the host machine")

        except Exception as e:
            self.logger.error("Failed to start trap receiver", extra={"error": str(e)})
            self.consume = False
            if self.trap_engine:
                self.trap_engine.close_dispatcher()
                self.trap_engine = None
            raise

    async def _run_dispatcher(self, dispatcher):
        """Run the dispatcher in the event loop."""
        try:
            dispatcher.run_dispatcher()
        except Exception as e:
            self.logger.error("Error running dispatcher", extra={"error": str(e)})

    def stop_consume(self):
        """Stop the SNMP trap receiver."""
        self.consume = False
        if self.trap_engine:
            self.trap_engine.job_finished(1)
            self.trap_engine.close_dispatcher()
            self.trap_engine = None
        self.logger.info("SNMP trap receiver stopped")

    async def _handle_trap(self, transport_dispatcher, transport_domain, transport_address, whole_msg):
        """Handle incoming SNMP traps."""
        try:
            if not self.consume:
                return

            # Decode message version and community/auth
            try:
                if self.authentication_config.version in [SnmpVersion.V1, SnmpVersion.V2C]:
                    msg_version = 0 if self.authentication_config.version == SnmpVersion.V1 else 1
                    msg_auth = CommunityData(self.authentication_config.community_string, mpModel=msg_version)
                else:  # v3
                    msg_version = 3
                    msg_auth = (await self._get_session_args())['auth_data']

                while whole_msg:
                    msg_version = int(api.decodeMessageVersion(whole_msg))
                    if msg_version in api.protoModules:
                        proto_module = api.protoModules[msg_version]
                    else:
                        self.logger.error(f'Unsupported SNMP version {msg_version}')
                        return
                    
                    req_msg, whole_msg = decoder.decode(
                        whole_msg, asn1Spec=proto_module.Message(),
                    )

                    # Extract trap info based on version
                    if msg_version == 0:  # v1
                        pdu = req_msg.getComponentByName('data').getComponentByName('pdus').getComponentByType(proto_module.TrapPDU())
                        enterprise = pdu.getComponentByName('enterprise')
                        agent_addr = pdu.getComponentByName('agent-addr')
                        trap_type = pdu.getComponentByName('generic-trap')
                        specific_type = pdu.getComponentByName('specific-trap')
                        var_binds = pdu.getComponentByName('variable-bindings')
                    else:  # v2c/v3
                        pdu = req_msg.getComponentByName('data').getComponentByName('pdus').getComponentByType(proto_module.SNMPv2TrapPDU())
                        var_binds = pdu.getComponentByName('variable-bindings')
                        enterprise = None
                        agent_addr = transport_address[0]
                        trap_type = None
                        specific_type = None

                    # Format trap data
                    trap_data = {
                        'enterprise_oid': str(enterprise) if enterprise else '',
                        'agent_addr': str(agent_addr),
                        'trap_type': str(trap_type) if trap_type is not None else '',
                        'specific_type': str(specific_type) if specific_type is not None else '',
                        'var_binds': []
                    }

                    # Extract variable bindings
                    for var_bind in var_binds:
                        name, val = var_bind
                        trap_data['var_binds'].append({
                            'oid': str(name),
                            'value': str(val)
                        })

                    # Convert to alert and push
                    alert = self._format_alert(trap_data)
                    self._push_alert(alert)

            except Exception as e:
                self.logger.error("Error processing trap", extra={"error": str(e)})

        except Exception as e:
            self.logger.error("Error in trap handler", extra={"error": str(e)})

        return whole_msg 

if __name__ == "__main__":
    import logging
    
    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    # Get configuration from environment variables
    host = os.environ.get("SNMP_HOST")
    community = os.environ.get("SNMP_COMMUNITY")
    version = os.environ.get("SNMP_VERSION", "v2c")

    if not host:
        raise Exception("SNMP_HOST environment variable is required")
    if not community and version in ["v1", "v2c"]:
        raise Exception("SNMP_COMMUNITY environment variable is required for v1/v2c")

    # Create provider configuration
    config = ProviderConfig(
        description="SNMP Provider",
        authentication={
            "host": host,
            "version": version,
            "community_string": community,
            "trap_port": 162,
        },
    )

    # Initialize provider
    provider = SnmpProvider(
        context_manager=context_manager,
        provider_id="snmp_test",
        config=config,
    )

    # Test basic SNMP GET operation
    try:
        result = provider._query(
            operation="get",
            oids=["1.3.6.1.2.1.1.1.0"]  # sysDescr.0
        )
        print("SNMP GET Result:", result)
    except Exception as e:
        print("SNMP GET Error:", str(e))

    # Test trap receiver if trap scope is enabled
    if "trap" in provider.config.scopes:
        print("Starting trap receiver...")
        provider.start_consume() 