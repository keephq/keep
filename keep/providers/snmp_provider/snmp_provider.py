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


@pydantic.dataclasses.dataclass
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
            "description": "SNMP community string for authentication",
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
            "description": "SNMPv3 username",
            "config_main_group": "authentication",
        },
        default="",
    )

    auth_protocol: typing.Literal["MD5", "SHA"] = dataclasses.field(
        default="SHA",
        metadata={
            "required": False,
            "description": "SNMPv3 authentication protocol",
            "type": "select",
            "options": ["MD5", "SHA"],
            "config_main_group": "authentication",
        },
    )

    auth_key: str = dataclasses.field(
        metadata={
            "required": False,
            "sensitive": True,
            "description": "SNMPv3 authentication key",
            "config_main_group": "authentication",
        },
        default="",
    )

    priv_protocol: typing.Literal["DES", "AES"] = dataclasses.field(
        default="AES",
        metadata={
            "required": False,
            "description": "SNMPv3 privacy protocol",
            "type": "select",
            "options": ["DES", "AES"],
            "config_main_group": "authentication",
        },
    )

    priv_key: str = dataclasses.field(
        metadata={
            "required": False,
            "sensitive": True,
            "description": "SNMPv3 privacy key",
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
                            # Wait for cancellation to complete
                            try:
                                asyncio.wait_for(dispatcher.loopingcall, timeout=1)
                            except (asyncio.TimeoutError, asyncio.CancelledError):
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

        # Validate SNMPv3 configuration if v3 is selected
        if self.authentication_config.snmp_version == "v3":
            if not self.authentication_config.username:
                raise ProviderException("Username is required for SNMPv3")
            if not self.authentication_config.auth_key:
                raise ProviderException("Authentication key is required for SNMPv3")
            if not self.authentication_config.priv_key:
                raise ProviderException("Privacy key is required for SNMPv3")

        # Validate MIB directories
        for mib_dir in self.authentication_config.mib_dirs:
            if not os.path.isdir(mib_dir):
                raise ProviderException(f"MIB directory does not exist: {mib_dir}")

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate that the scopes provided are correct.
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
            return {"receive_traps": str(e)}

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
                """
                try:
                    self.logger.info("Received SNMP trap")
                    trap_data = {
                        'trap_type': 'SNMP Trap',
                        'message': '',
                        'description': '',
                        'severity': AlertSeverity.INFO,
                        'variables': {},
                        'context': {
                            'engine_id': context_engine_id.prettyPrint() if context_engine_id else None,
                            'context_name': context_name.prettyPrint() if context_name else None
                        }
                    }
                    
                    for name, val in var_binds:
                        try:
                            if isinstance(name, ObjectIdentifier):
                                var_name = self._parse_trap_oid(name)
                            else:
                                var_name = str(name)
                                
                            trap_data['variables'][var_name] = val.prettyPrint()
                            
                            # Try to identify trap type and severity from common OIDs
                            if 'trapType' in var_name.lower():
                                trap_data['trap_type'] = val.prettyPrint()
                            elif 'severity' in var_name.lower():
                                trap_data['severity'] = val.prettyPrint()
                            elif 'message' in var_name.lower():
                                trap_data['message'] = val.prettyPrint()
                            elif 'description' in var_name.lower():
                                trap_data['description'] = val.prettyPrint()
                                
                        except Exception as e:
                            self.logger.error(f"Error processing trap variable {name}: {str(e)}")
                            trap_data['variables'][str(name)] = str(val)
                    
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
        
        if not target_host or not oid:
            raise ProviderException("Host and OID are required for SNMP queries")

        snmp_engine = SnmpEngine()
        
        try:
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

            transport_target = await UdpTransportTarget.create((target_host, target_port))
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
                    if value is None:
                        raise ProviderException("Value is required for SET operation")
                    error_indication, error_status, error_index, var_binds = await set_cmd(
                        snmp_engine,
                        auth_data,
                        transport_target,
                        context_data,
                        obj_type,
                        value
                    )
                else:
                    raise ProviderException(f"Unsupported SNMP operation: {operation}")

                if error_indication:
                    raise ProviderException(f"SNMP error: {error_indication}")
                elif error_status:
                    raise ProviderException(f"SNMP error: {error_status.prettyPrint()}")

                results = []
                for var_bind in var_binds:
                    name, value = var_bind
                    results.append({
                        'oid': name.prettyPrint(),
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
                    self.logger.debug(f"Error during final engine cleanup: {e}")