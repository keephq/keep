"""
SNMP Provider is a class that provides functionality to receive SNMP traps and convert them to Keep alerts.
"""

import asyncio
import dataclasses
import os
import typing
from pathlib import Path
from pysnmp.hlapi.v3arch.asyncio.auth import CommunityData, UsmUserData
from pysnmp.hlapi.v3arch.asyncio.transport import UdpTransportTarget
from pysnmp.hlapi.v3arch.asyncio.context import ContextData
from pysnmp.hlapi.v3arch.asyncio.cmdgen import (
    SnmpEngine,
    ObjectType,
    get_cmd,
    set_cmd,
    next_cmd,
    bulk_cmd
)
from pysnmp.smi.rfc1902 import ObjectIdentity
from pysnmp.proto.rfc1902 import Integer, OctetString, IpAddress, Counter32, Counter64, Gauge32, Unsigned32, TimeTicks, Bits, Opaque
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import engine, config
from pysnmp.smi import builder, view, compiler
from pysnmp.proto.rfc1902 import ObjectIdentifier
from pysnmp.entity.rfc3413 import ntfrcv

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.validation.fields import UrlPort
from keep.exceptions.provider_exception import ProviderException


@pydantic.dataclasses.dataclass(config=dict(validate_assignment=True))
class SnmpProviderAuthConfig:
    """SNMP authentication configuration."""
    
    listen_port: UrlPort = dataclasses.field(
        metadata={
            "required": True,
            "description": "Port to listen for SNMP traps",
            "config_main_group": "authentication",
            "validation": "port",
        },
        default=162,
    )

    community_string: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SNMP community string for authentication (required for v1/v2c)",
            "sensitive": True,
            "config_main_group": "authentication",
        },
        default="public"
    )

    snmp_version: typing.Literal["v1", "v2c", "v3"] = dataclasses.field(
        default="v2c",
        metadata={
            "required": True,
            "description": "SNMP protocol version",
            "type": "select", 
            "options": ["v1", "v2c", "v3"],
            "config_main_group": "authentication",
        },
    )

    # SNMPv3 specific configuration
    username: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 username (required for v3)",
            "config_main_group": "authentication",
        },
        default="",
    )

    auth_protocol: typing.Literal["MD5", "SHA"] = dataclasses.field(
        default="SHA",
        metadata={
            "required": False,
            "description": "SNMPv3 authentication protocol (required for v3)",
            "type": "select",
            "options": ["MD5", "SHA"],
            "config_main_group": "authentication",
        },
    )

    auth_key: str = dataclasses.field(
        metadata={
            "required": False,
            "sensitive": True,
            "description": "SNMPv3 authentication key (required for v3)",
            "config_main_group": "authentication",
        },
        default="",
    )

    priv_protocol: typing.Literal["DES", "AES"] = dataclasses.field(
        default="AES",
        metadata={
            "required": False,
            "description": "SNMPv3 privacy protocol (required for v3)",
            "type": "select",
            "options": ["DES", "AES"],
            "config_main_group": "authentication",
        },
    )

    priv_key: str = dataclasses.field(
        metadata={
            "required": False,
            "sensitive": True,
            "description": "SNMPv3 privacy key (required for v3)",
            "config_main_group": "authentication",
        },
        default="",
    )

    # MIB configuration
    mib_dirs: list[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "List of directories containing custom MIB files",
            "config_main_group": "authentication",
        },
        default_factory=list,
    )

    def __post_init__(self):
        """Validate SNMPv3 fields after initialization."""
        if self.snmp_version == 'v3':
            required_fields = {
                'username': 'Username',
                'auth_key': 'Authentication key',
                'priv_key': 'Privacy key'
            }
            
            missing_fields = []
            for field, display_name in required_fields.items():
                if not getattr(self, field):
                    missing_fields.append(display_name)
            
            if missing_fields:
                raise ProviderException(f"The following fields are required for SNMPv3: {', '.join(missing_fields)}")


class SnmpProvider(BaseProvider):
    """
    SNMP provider class for receiving SNMP traps.
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]
    
    PROVIDER_SCOPES = [
        ProviderScope(
            name="receive_traps",
            description="Ability to receive SNMP traps",
            mandatory=True,
            alias="Receive SNMP Traps",
        )
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.snmp_engine = None
        self.trap_receiver = None
        self.mib_view_controller = None

    async def dispose(self):
        """
        Clean up SNMP engine and trap receiver.
        """
        if self.snmp_engine:
            try:
                dispatcher = self.snmp_engine.transport_dispatcher
                if hasattr(dispatcher, 'loopingcall'):
                    try:
                        if not dispatcher.loopingcall.done():
                            dispatcher.loopingcall.cancel()
                            # Wait for the future to complete after cancellation
                            try:
                                await asyncio.shield(dispatcher.loopingcall)
                            except asyncio.CancelledError:
                                pass
                    except Exception as e:
                        self.logger.debug(f"Error canceling dispatcher timeout: {e}")
                
                if hasattr(dispatcher, '_transports'):
                    for transport in dispatcher._transports.values():
                        if hasattr(transport, 'close'):
                            transport.close()
                dispatcher.close_dispatcher()
                self.snmp_engine = None
            except Exception as e:
                self.logger.error(f"Error disposing SNMP engine: {str(e)}")

        if self.trap_receiver:
            try:
                await self.trap_receiver.close()
                self.trap_receiver = None
            except Exception as e:
                self.logger.error(f"Error disposing trap receiver: {str(e)}")

    def validate_config(self):
        """
        Validate the SNMP provider configuration.
        """
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

        # Validate MIB directories
        for mib_dir in self.authentication_config.mib_dirs:
            if not os.path.isdir(mib_dir):
                raise ProviderException(f"MIB directory does not exist: {mib_dir}")

    def validate_scopes(self) -> dict[str, bool]:
        """
        Validate that the scopes provided are correct.
        Returns a dictionary mapping scope names to boolean values indicating if they are valid.
        Any validation errors will be logged at debug level.
        """
        try:
            # Try to create an SNMP engine with the provided config
            snmp_engine = engine.SnmpEngine()
            
            # Configure transport
            config.add_transport(
                snmp_engine,
                udp.DOMAIN_NAME,
                udp.UdpTransport().open_server_mode(('0.0.0.0', self.authentication_config.listen_port))
            )
            
            if self.authentication_config.snmp_version == "v3":
                # Configure SNMPv3
                config.add_v3_user(
                    snmp_engine,
                    self.authentication_config.username,
                    config.usmHMACMD5AuthProtocol if self.authentication_config.auth_protocol == "MD5" else config.usmHMACSHAAuthProtocol,
                    self.authentication_config.auth_key,
                    config.usmDESPrivProtocol if self.authentication_config.priv_protocol == "DES" else config.usmAesCfb128Protocol,
                    self.authentication_config.priv_key
                )
            else:
                # Configure v1/v2c community string
                config.add_v1_system(
                    snmp_engine,
                    'my-area',
                    self.authentication_config.community_string
                )
            
            snmp_engine.transport_dispatcher.close_dispatcher()
            return {"receive_traps": True}
        except Exception as e:
            self.logger.debug(f"SNMP trap receiver validation failed: {str(e)}")
            return {"receive_traps": False}

    def _setup_mib_compiler(self):
        """
        Set up MIB compiler with custom MIB directories.
        """
        try:
            mib_builder = builder.MibBuilder()
            
            # Add custom MIB directories
            for mib_dir in self.authentication_config.mib_dirs:
                self.logger.info(f"Adding MIB directory: {mib_dir}")
                mib_path = Path(mib_dir)
                if mib_path.exists() and mib_path.is_dir():
                    mib_builder.add_mib_sources(builder.DirMibSource(str(mib_path)))
                else:
                    self.logger.warning(f"MIB directory not found: {mib_dir}")

            # Add MIB compiler
            compiler.add_mib_compiler(mib_builder)
            self.mib_view_controller = view.MibViewController(mib_builder)
            self.logger.info("MIB compiler setup completed successfully")
            
        except Exception as e:
            self.logger.error(f"Error setting up MIB compiler: {str(e)}")
            raise ProviderException(f"Failed to set up MIB compiler: {str(e)}")

    def _format_alert(self, event: dict) -> AlertDto:
        """
        Format SNMP trap data into an AlertDto.
        """
        # Map SNMP trap severity to AlertSeverity
        severity_map = {
            'emergency': AlertSeverity.CRITICAL,
            'alert': AlertSeverity.CRITICAL,
            'critical': AlertSeverity.CRITICAL,
            'error': AlertSeverity.HIGH,  # Map error to HIGH since ERROR is not a valid severity
            'warning': AlertSeverity.WARNING,
            'notice': AlertSeverity.INFO,
            'info': AlertSeverity.INFO,
            'debug': AlertSeverity.INFO
        }

        # Try to extract severity from trap data
        trap_severity = event.get('severity', '').lower()
        severity = severity_map.get(trap_severity, AlertSeverity.INFO)

        # Format description with variables
        description = event.get('description', '')
        if event.get('variables'):
            description += "\n\nTrap Variables:\n"
            for var_name, var_value in event['variables'].items():
                description += f"{var_name}: {var_value}\n"

        return AlertDto(
            name=event.get('trap_type', 'SNMP Trap'),
            message=event.get('message', ''),
            description=description,
            severity=severity,
            status=AlertStatus.FIRING,
            source=['snmp'],
            source_type='snmp',
            original_event=event,
        )

    def _parse_trap_oid(self, trap_oid: ObjectIdentifier) -> str:
        """
        Parse trap OID to get a human-readable name.
        """
        try:
            if self.mib_view_controller:
                mib_name = self.mib_view_controller.get_node_name(trap_oid)
                return '.'.join(str(x) for x in mib_name)
        except Exception as e:
            self.logger.warning(f"Failed to parse trap OID {trap_oid}: {str(e)}")
        
        return str(trap_oid)

    def start_trap_receiver(self):
        """
        Start the SNMP trap receiver.
        """
        self.logger.info("Starting SNMP trap receiver")
        self.snmp_engine = engine.SnmpEngine()
        
        try:
            # Configure transport
            config.add_transport(
                self.snmp_engine,
                udp.DOMAIN_NAME,
                udp.UdpTransport().open_server_mode(('0.0.0.0', self.authentication_config.listen_port))
            )
            self.logger.debug(f"SNMP transport configured on port {self.authentication_config.listen_port}")
            
            # Configure authentication based on version
            if self.authentication_config.snmp_version == "v3":
                config.add_v3_user(
                    self.snmp_engine,
                    self.authentication_config.username,
                    config.usmHMACMD5AuthProtocol if self.authentication_config.auth_protocol == "MD5" else config.usmHMACSHAAuthProtocol,
                    self.authentication_config.auth_key,
                    config.usmDESPrivProtocol if self.authentication_config.priv_protocol == "DES" else config.usmAesCfb128Protocol,
                    self.authentication_config.priv_key
                )
                self.logger.debug("SNMPv3 user configured")
            else:
                config.add_v1_system(
                    self.snmp_engine,
                    'my-area',
                    self.authentication_config.community_string
                )
                self.logger.debug(f"SNMPv{self.authentication_config.snmp_version} community configured")
            
            # Set up MIB compiler
            self._setup_mib_compiler()
            
            def trap_callback(snmp_engine, state_reference, context_engine_id, context_name,
                            var_binds, cb_ctx):
                """
                Callback function to handle received SNMP traps.
                
                This function processes incoming SNMP traps and converts them to alerts.
                It carefully extracts and validates trap information, ensuring all critical
                fields are properly populated.
                """
                try:
                    self.logger.info("Received SNMP trap")
                    
                    # Initialize trap data with required fields
                    trap_data = {
                        'trap_type': 'SNMP Trap',
                        'message': [],  # List to collect message parts
                        'description': [],  # List to collect description parts
                        'severity': AlertSeverity.INFO,
                        'variables': {},
                        'context': {
                            'engine_id': context_engine_id.prettyPrint() if context_engine_id else None,
                            'context_name': context_name.prettyPrint() if context_name else None
                        }
                    }
                    
                    # First pass: Collect all variables and their values
                    for name, val in var_binds:
                        try:
                            var_name = self._parse_trap_oid(name) if isinstance(name, ObjectIdentifier) else str(name)
                            var_value = val.prettyPrint()
                            trap_data['variables'][var_name] = var_value
                            
                            # Store the raw name-value pair for pattern matching
                            name_lower = var_name.lower()
                            
                            # Identify trap metadata from variable names using comprehensive pattern matching
                            if any(type_pattern in name_lower for type_pattern in ['traptype', 'trap.type', 'event.type']):
                                trap_data['trap_type'] = var_value
                            elif any(sev_pattern in name_lower for sev_pattern in ['severity', 'priority', 'level']):
                                trap_data['severity'] = var_value
                            elif any(msg_pattern in name_lower for msg_pattern in ['message', 'msg', 'text']):
                                trap_data['message'].append(var_value)
                            elif any(desc_pattern in name_lower for desc_pattern in ['description', 'desc', 'details']):
                                trap_data['description'].append(var_value)
                                
                        except Exception as e:
                            self.logger.error(f"Error processing trap variable {name}: {str(e)}")
                            # Fallback: store raw values if processing fails
                            trap_data['variables'][str(name)] = str(val)
                    
                    # Second pass: Post-process collected data
                    
                    # Join collected messages and descriptions
                    trap_data['message'] = ' '.join(filter(None, trap_data['message'])) or 'SNMP Trap Received'
                    trap_data['description'] = ' '.join(filter(None, trap_data['description']))
                    
                    # Map severity string to AlertSeverity enum if it's a string
                    if isinstance(trap_data['severity'], str):
                        severity_map = {
                            'emergency': AlertSeverity.CRITICAL,
                            'alert': AlertSeverity.CRITICAL,
                            'critical': AlertSeverity.CRITICAL,
                            'error': AlertSeverity.HIGH,
                            'warning': AlertSeverity.WARNING,
                            'notice': AlertSeverity.INFO,
                            'info': AlertSeverity.INFO,
                            'debug': AlertSeverity.INFO,
                            # Add numeric severity mappings
                            '0': AlertSeverity.INFO,
                            '1': AlertSeverity.WARNING,
                            '2': AlertSeverity.HIGH,
                            '3': AlertSeverity.CRITICAL
                        }
                        trap_data['severity'] = severity_map.get(
                            trap_data['severity'].lower(),
                            AlertSeverity.INFO
                        )
                    
                    # Ensure description includes all variables if no specific description was found
                    if not trap_data['description']:
                        var_desc = [f"{k}: {v}" for k, v in trap_data['variables'].items()]
                        trap_data['description'] = "Trap Variables:\n" + "\n".join(var_desc)
                    
                    self.logger.debug(f"Processed trap data: {trap_data}")
                    alert = self._format_alert(trap_data)
                    self._push_alert(alert.dict())
                    self.logger.info("Successfully processed and pushed SNMP trap as alert")
                    
                except Exception as e:
                    self.logger.error(f"Error processing SNMP trap: {str(e)}")
            
            # Set up notification receiver
            ntfrcv.NotificationReceiver(
                self.snmp_engine,
                trap_callback
            )
            
            self.logger.info("SNMP trap receiver configured successfully")
            self.snmp_engine.transport_dispatcher.jobStarted(1)
            try:
                self.snmp_engine.transport_dispatcher.runDispatcher()
            except Exception as e:
                self.logger.error(f"Error running SNMP dispatcher: {str(e)}")
                self.snmp_engine.transport_dispatcher.close_dispatcher()
                raise
                
        except Exception as e:
            self.logger.error(f"Error starting SNMP trap receiver: {str(e)}")
            if self.snmp_engine and self.snmp_engine.transport_dispatcher:
                self.snmp_engine.transport_dispatcher.close_dispatcher()
            raise ProviderException(f"Failed to start SNMP trap receiver: {str(e)}")

    def _notify(self, **kwargs):
        """
        Not implemented for SNMP provider as it only receives traps.
        """
        raise NotImplementedError("SNMP provider only supports receiving traps")

    def start_consume(self):
        """
        Start consuming SNMP traps.
        """
        self.logger.info("Starting SNMP trap consumer")
        try:
            self.start_trap_receiver()
            return True
        except Exception as e:
            self.logger.error(f"Failed to start SNMP trap consumer: {str(e)}")
            return False

    def status(self) -> dict:
        """
        Return the status of the SNMP trap receiver.
        """
        if not self.snmp_engine or not self.snmp_engine.transport_dispatcher:
            return {
                "status": "stopped",
                "error": "SNMP trap receiver not running"
            }
            
        try:
            # Check if dispatcher is actually running
            if self.snmp_engine.transport_dispatcher.jobs_are_pending():
                return {
                    "status": "running",
                    "error": ""
                }
            else:
                return {
                    "status": "stopped",
                    "error": "SNMP dispatcher has no pending jobs"
                }
        except Exception as e:
            return {
                "status": "error",
                "error": f"Error checking SNMP status: {str(e)}"
            }

    @property
    def is_consumer(self) -> bool:
        """
        SNMP provider is a consumer as it receives traps.
        """
        return True

    async def query(self, **kwargs):
        """
        Query SNMP agent using GET, GETNEXT, or GETBULK operations.
        """
        operation = kwargs.get('operation', 'GET')
        target_host = kwargs.get('host')
        target_port = kwargs.get('port', 161)
        oid = kwargs.get('oid')
        timeout = kwargs.get('timeout', 10)  # Default 10 second timeout
        retries = kwargs.get('retries', 3)   # Default 3 retries
        
        if not target_host or not oid:
            raise ProviderException("Host and OID are required for SNMP queries")

        snmp_engine = None
        dispatcher = None
        
        try:
            snmp_engine = SnmpEngine()
            
            # Initialize MIB view controller if not already initialized
            if not self.mib_view_controller:
                self._setup_mib_compiler()
            
            auth_data = None
            if self.authentication_config.snmp_version == 'v3':
                auth_data = UsmUserData(
                    self.authentication_config.username,
                    self.authentication_config.auth_key,
                    self.authentication_config.priv_key
                )
            else:
                auth_data = CommunityData(self.authentication_config.community_string, 
                                        mpModel=0 if self.authentication_config.snmp_version == 'v1' else 1)

            transport_target = await UdpTransportTarget.create(
                (target_host, target_port),
                timeout=timeout,
                retries=retries
            )
            context_data = ContextData()
            
            obj_type = ObjectType(ObjectIdentity(oid))
            
            try:
                if operation == 'GET':
                    error_indication, error_status, error_index, var_binds = await get_cmd(
                        snmp_engine,
                        auth_data,
                        transport_target,
                        context_data,
                        obj_type
                    )
                elif operation == 'GETNEXT':
                    error_indication, error_status, error_index, var_binds = await next_cmd(
                        snmp_engine,
                        auth_data,
                        transport_target,
                        context_data,
                        obj_type
                    )
                elif operation == 'GETBULK':
                    error_indication, error_status, error_index, var_binds = await bulk_cmd(
                        snmp_engine,
                        auth_data,
                        transport_target,
                        context_data,
                        0, 25,  # non-repeaters, max-repetitions
                        obj_type
                    )
                elif operation == 'SET':
                    value = kwargs.get('value')
                    value_type = kwargs.get('value_type', 'string').lower()
                    
                    if value is None:
                        raise ProviderException("Value is required for SET operation")

                    # Map of supported SNMP value types and their corresponding classes
                    type_map = {
                        'integer': Integer,
                        'int': Integer,
                        'int32': Integer,
                        'string': OctetString,
                        'octetstring': OctetString,
                        'ipaddress': IpAddress,
                        'counter32': Counter32,
                        'counter64': Counter64,
                        'gauge32': Gauge32,
                        'unsigned32': Unsigned32,
                        'timeticks': TimeTicks,
                        'bits': Bits,
                        'opaque': Opaque
                    }

                    if value_type not in type_map:
                        raise ProviderException(
                            f"Unsupported value type: {value_type}. "
                            f"Supported types are: {', '.join(type_map.keys())}"
                        )

                    try:
                        # Convert the value to the appropriate SNMP type
                        snmp_type = type_map[value_type]
                        if value_type in ['integer', 'int', 'int32', 'counter32', 'counter64', 'gauge32', 'unsigned32', 'timeticks']:
                            typed_value = snmp_type(int(value))
                        elif value_type == 'ipaddress':
                            # Validate IP address format
                            import ipaddress
                            ipaddress.ip_address(value)  # This will raise ValueError if invalid
                            typed_value = snmp_type(value)
                        elif value_type == 'bits':
                            # Expect a comma-separated list of bit positions
                            bit_positions = [int(x.strip()) for x in str(value).split(',')]
                            typed_value = snmp_type(names=bit_positions)
                        else:
                            typed_value = snmp_type(str(value))

                    except (ValueError, TypeError) as e:
                        raise ProviderException(
                            f"Invalid value format for type {value_type}: {str(e)}"
                        )

                    error_indication, error_status, error_index, var_binds = await set_cmd(
                        snmp_engine,
                        auth_data,
                        transport_target,
                        context_data,
                        ObjectType(ObjectIdentity(oid), typed_value)
                    )
                else:
                    raise ProviderException(f"Unsupported SNMP operation: {operation}")

                if error_indication:
                    error_msg = str(error_indication)
                    if "No SNMP response received before timeout" in error_msg:
                        raise ProviderException(
                            f"SNMP {operation} timed out after {timeout} seconds with {retries} retries. "
                            f"Consider increasing timeout or retries."
                        )
                    raise ProviderException(f"SNMP error: {error_indication}")
                elif error_status:
                    raise ProviderException(f"SNMP error: {error_status.prettyPrint()}")

                results = []
                for var_bind in var_binds:
                    name, value = var_bind
                    # Use MIB view controller to translate OID to proper MIB name
                    try:
                        if self.mib_view_controller:
                            mib_name = self.mib_view_controller.get_node_name(name)
                            if len(mib_name) > 0:
                                # First element is the MIB module name (e.g. 'SNMPv2-MIB')
                                mib_module = str(mib_name[0])
                                # Rest are the object parts (e.g. 'sysDescr', '0')
                                object_parts = []
                                for part in mib_name[1:]:
                                    if isinstance(part, (str, int)):
                                        object_parts.append(str(part))
                                oid = f"{mib_module}::{'.'.join(object_parts)}"
                            else:
                                oid = name.prettyPrint()
                        else:
                            oid = name.prettyPrint()
                    except Exception as e:
                        self.logger.debug(f"Failed to translate OID using MIB: {str(e)}")
                        oid = name.prettyPrint()
                        
                    results.append({
                        'oid': oid,
                        'value': value.prettyPrint()
                    })

                return results

            finally:
                # Clean up transport dispatcher
                if snmp_engine and hasattr(snmp_engine, 'transport_dispatcher'):
                    dispatcher = snmp_engine.transport_dispatcher
                    if hasattr(dispatcher, 'loopingcall'):
                        try:
                            if not dispatcher.loopingcall.done():
                                dispatcher.loopingcall.cancel()
                            await dispatcher.loopingcall
                        except (asyncio.CancelledError, Exception) as e:
                            self.logger.debug(f"Error canceling dispatcher timeout: {e}")
                    
                    try:
                        dispatcher.close_dispatcher()
                    except Exception as e:
                        self.logger.debug(f"Error closing dispatcher: {e}")

        except Exception as e:
            self.logger.error(f"Error performing SNMP {operation}: {str(e)}")
            raise ProviderException(f"SNMP {operation} failed: {str(e)}")
        finally:
            # Ensure engine resources are cleaned up
            if snmp_engine and hasattr(snmp_engine, 'transport_dispatcher'):
                try:
                    snmp_engine.transport_dispatcher.close_dispatcher()
                except Exception as e:
                    self.logger.debug(f"Error during final cleanup: {e}")