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

    async def _cleanup_dispatcher(self, dispatcher, operation_name=""):
        """
        Helper method to safely cleanup SNMP dispatcher resources.
        """
        if not dispatcher:
            return
        
        # Handle loopingcall cleanup
        if hasattr(dispatcher, 'loopingcall'):
            try:
                loopingcall = dispatcher.loopingcall
                if isinstance(loopingcall, asyncio.Future) and not loopingcall.done():
                    loopingcall.cancel()
                    try:
                        await asyncio.shield(loopingcall)
                    except (asyncio.CancelledError, Exception) as e:
                        self.logger.debug(f"Error during loopingcall cleanup ({operation_name}): {e}")
            except Exception as e:
                self.logger.debug(f"Error handling loopingcall ({operation_name}): {e}")
        
        # Close transports
        if hasattr(dispatcher, '_transports'):
            for transport in dispatcher._transports.values():
                if hasattr(transport, 'close'):
                    try:
                        transport.close()
                    except Exception as e:
                        self.logger.debug(f"Error closing transport ({operation_name}): {e}")
        
        # Close dispatcher
        try:
            dispatcher.close_dispatcher()
        except Exception as e:
            self.logger.debug(f"Error closing dispatcher ({operation_name}): {e}")

    async def dispose(self):
        """
        Clean up SNMP engine and trap receiver.
        """
        if self.snmp_engine:
            try:
                dispatcher = self.snmp_engine.transport_dispatcher
                await self._cleanup_dispatcher(dispatcher, "dispose")
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

    @dataclasses.dataclass
    class SnmpQueryParams:
        """Parameters for SNMP query operations."""
        host: str
        oid: str
        operation: typing.Literal["GET", "GETNEXT", "GETBULK", "SET"] = "GET"
        port: int = 161
        timeout: int = 10
        retries: int = 3
        value: typing.Optional[typing.Any] = None
        value_type: typing.Optional[str] = None

    class SnmpValueTypeHandler:
        """Handler for SNMP value type conversions."""
        
        TYPE_MAP = {
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
        
        NUMERIC_TYPES = {'integer', 'int', 'int32', 'counter32', 'counter64', 
                         'gauge32', 'unsigned32', 'timeticks'}
        
        @classmethod
        def convert_value(cls, value: typing.Any, value_type: str) -> typing.Any:
            """Convert a value to its appropriate SNMP type."""
            value_type = value_type.lower()
            
            if value_type not in cls.TYPE_MAP:
                raise ProviderException(
                    f"Unsupported value type: {value_type}. "
                    f"Supported types are: {', '.join(cls.TYPE_MAP.keys())}"
                )
            
            snmp_type = cls.TYPE_MAP[value_type]
            
            try:
                if value_type in cls.NUMERIC_TYPES:
                    try:
                        return snmp_type(int(str(value).strip()))
                    except (ValueError, TypeError) as e:
                        raise ProviderException(f"Invalid numeric value '{value}' for type {value_type}: {str(e)}")
                elif value_type == 'ipaddress':
                    import ipaddress
                    try:
                        ipaddress.ip_address(str(value))  # Validate IP address format
                        return snmp_type(str(value))
                    except ValueError as e:
                        raise ProviderException(f"Invalid IP address format: {str(e)}")
                elif value_type == 'bits':
                    try:
                        bit_positions = [int(x.strip()) for x in str(value).split(',')]
                        return snmp_type(names=bit_positions)
                    except (ValueError, TypeError) as e:
                        raise ProviderException(f"Invalid bits format. Expected comma-separated integers: {str(e)}")
                else:
                    return snmp_type(str(value))
            except Exception as e:
                if isinstance(e, ProviderException):
                    raise
                raise ProviderException(f"Error converting value '{value}' to type {value_type}: {str(e)}")

    async def query(self, **kwargs):
        """
        Query SNMP agent using GET, GETNEXT, GETBULK, or SET operations.
        """
        # Check required parameters first
        if not kwargs.get('host') or not kwargs.get('oid'):
            raise ProviderException("Host and OID are required for SNMP queries")
            
        try:
            params = self.SnmpQueryParams(**kwargs)
        except TypeError as e:
            raise ProviderException(f"Invalid query parameters: {str(e)}")

        snmp_engine = None
        
        try:
            snmp_engine = SnmpEngine()
            
            # Initialize MIB view controller if not already initialized
            if not self.mib_view_controller:
                self._setup_mib_compiler()
            
            auth_data = self._get_auth_data()
            try:
                transport_target = await UdpTransportTarget.create(
                    (str(params.host), int(params.port)),
                    timeout=int(params.timeout),
                    retries=int(params.retries)
                )
            except Exception as e:
                raise ProviderException(f"Failed to create transport target: {str(e)}")
            context_data = ContextData()
            
            # Prepare the object type based on operation
            if params.operation == 'SET':
                if params.value is None:
                    raise ProviderException("Value is required for SET operation")
                if params.value_type is None:
                    raise ProviderException("Value type is required for SET operation")
                try:
                    typed_value = self.SnmpValueTypeHandler.convert_value(
                        params.value, 
                        params.value_type
                    )
                    obj_identity = ObjectIdentity(params.oid)
                    obj_type = ObjectType(obj_identity, typed_value)
                except Exception as e:
                    raise ProviderException(f"Failed to convert value for SET operation: {str(e)}")
            else:
                obj_type = ObjectType(ObjectIdentity(params.oid))
            
            # Execute SNMP command
            cmd_map = {
                'GET': get_cmd,
                'GETNEXT': next_cmd,
                'GETBULK': bulk_cmd,
                'SET': set_cmd
            }
            
            cmd_func = cmd_map.get(params.operation)
            if not cmd_func:
                raise ProviderException(f"Unsupported SNMP operation: {params.operation}")
            
            # Add GETBULK specific parameters
            cmd_args = [snmp_engine, auth_data, transport_target, context_data]
            if params.operation == 'GETBULK':
                cmd_args.extend([0, 25])  # non-repeaters, max-repetitions
            cmd_args.append(obj_type)
            
            error_indication, error_status, error_index, var_binds = await cmd_func(*cmd_args)
            
            if error_indication:
                error_msg = str(error_indication)
                if "No SNMP response received before timeout" in error_msg:
                    raise ProviderException(
                        f"SNMP {params.operation} timed out after {params.timeout} seconds "
                        f"with {params.retries} retries. Consider increasing timeout or retries."
                    )
                raise ProviderException(f"SNMP error: {error_indication}")
            elif error_status:
                raise ProviderException(f"SNMP error: {error_status.prettyPrint()}")

            return [
                {
                    'oid': self._format_oid(name),
                    'value': value.prettyPrint()
                }
                for name, value in var_binds
            ]

        except Exception as e:
            self.logger.error(f"Error performing SNMP {params.operation}: {str(e)}")
            raise ProviderException(f"SNMP {params.operation} failed: {str(e)}")
        finally:
            if snmp_engine and hasattr(snmp_engine, 'transport_dispatcher'):
                await self._cleanup_dispatcher(snmp_engine.transport_dispatcher, f"query_{params.operation}")

    def _get_auth_data(self) -> typing.Union[UsmUserData, CommunityData]:
        """Get authentication data based on SNMP version."""
        if self.authentication_config.snmp_version == 'v3':
            return UsmUserData(
                self.authentication_config.username,
                self.authentication_config.auth_key,
                self.authentication_config.priv_key
            )
        return CommunityData(
            self.authentication_config.community_string,
            mpModel=0 if self.authentication_config.snmp_version == 'v1' else 1
        )

    def _format_oid(self, name: ObjectIdentifier) -> str:
        """Format OID using MIB information if available."""
        try:
            if self.mib_view_controller:
                mib_name = self.mib_view_controller.get_node_name(name)
                if len(mib_name) > 0:
                    mib_module = str(mib_name[0])
                    object_parts = [
                        str(part) for part in mib_name[1:]
                        if isinstance(part, (str, int))
                    ]
                    return f"{mib_module}::{'.'.join(object_parts)}"
        except Exception as e:
            self.logger.debug(f"Failed to translate OID using MIB: {str(e)}")
        
        return name.prettyPrint()