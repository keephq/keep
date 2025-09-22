"""
SNMP Provider for receiving SNMP traps.
"""

import asyncio
import json
import socket
import threading
from datetime import datetime
from typing import Any, Dict, List, Union


from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import config, engine
from pysnmp.entity.rfc3413 import ntfrcv

import pydantic
import dataclasses
from keep.api.models.alert import AlertSeverity
import traceback
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    listen_address: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "IP address to listen on for SNMP traps",
            "config_main_group": "authentication",
        },
        default="0.0.0.0",
    )

    port: int = dataclasses.field(
        metadata={
            "required": False,
            "description": "UDP port to listen on for SNMP traps",
            "config_main_group": "authentication",
        },
        default=162,
    )

    community: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMP community string for authentication",
            "config_main_group": "authentication",
            "sensitive": True,
        },
        default="public",
    )

    severity_mapping: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "JSON mapping of OID patterns to Keep severity levels",
            "config_main_group": "authentication",
        },
        default=None,
    )


class SnmpProvider(BaseProvider):
    """
    SNMP Provider for receiving SNMP traps from network devices and converting them to Keep alerts.
    """
    PROVIDER_SCOPES = [
        ProviderScope(
            name="receive_traps",
            description="Receive and process SNMP traps",
            mandatory=True,
            alias="Receive SNMP Traps",
        )
    ]
    
    PROVIDER_CATEGORY = ["Monitoring", "Network Management"]
    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    
    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.snmp_engine = None
        self.trap_thread = None
        self.running = False
        self._severity_mapping = {}
        
        # Parse severity mapping if provided
        if self.authentication_config.severity_mapping:
            try:
                self._severity_mapping = json.loads(self.authentication_config.severity_mapping)
                self.logger.info(f"Loaded severity mapping: {self._severity_mapping}")
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse severity mapping JSON: {e}")
    
    def validate_config(self):
        """Validate the provider configuration."""
        self.authentication_config = SnmpProviderAuthConfig(**self.config.authentication)
    
    def _query(self, **kwargs):
        """Query method for provider - not applicable for SNMP trap receiver."""
        self.logger.warning("SNMP provider does not support querying")
        return None
    
    def _notify(self, **kwargs):
        """SNMP provider doesn't support direct notification as it's a receiver."""
        self.logger.warning("SNMP provider is a receiver and does not support direct notification")
        return None
    
    def start_consume(self):
        """Start the SNMP trap receiver."""
        if self.running:
            self.logger.warning("SNMP trap receiver is already running")
            return

        self.logger.info(
            f"Starting SNMP trap receiver on {self.authentication_config.listen_address}:{self.authentication_config.port}"
        )
        
        self.running = True
        self.trap_thread = threading.Thread(
            target=self._start_trap_receiver, 
            daemon=True
        )
        self.trap_thread.start()
        self.logger.info(f"SNMP trap receiver thread started successfully on {self.authentication_config.listen_address}:{self.authentication_config.port}")
        
        return {"status": "SNMP trap receiver started"}
    
    def _start_trap_receiver(self):
        """Start the SNMP trap receiver in a separate thread."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Create SNMP engine
            self.snmp_engine = engine.SnmpEngine()
            
            # Configure transport
            config.addTransport(
                self.snmp_engine,
                udp.domainName,
                udp.UdpTransport().openServerMode(
                    (self.authentication_config.listen_address, self.authentication_config.port)
                )
            )
            
            # Configure community string for SNMP v1 and v2c
            config.addV1System(
                self.snmp_engine,
                'keep-snmp-security-domain',
                self.authentication_config.community
            )
            
            # Register callback
            ntfrcv.NotificationReceiver(self.snmp_engine, self._handle_trap)
            
            self.logger.info("SNMP trap receiver is ready to receive traps")
            
            # Start the event loop
            self.snmp_engine.transportDispatcher.jobStarted(1)
            loop.run_forever()
            
        except Exception as e:
            self.logger.error(f"Error starting SNMP trap receiver: {e}")
            self.running = False
    
    def _handle_trap(self, snmp_engine, state_reference, context_engine_id, context_name, var_binds, cb_ctx):
        """Handle incoming SNMP traps."""
        try:
            self.logger.debug("Received SNMP trap")
            
            # Extract trap data
            trap_data = {}
            trap_oids = []
            
            # Process variable bindings (OIDs and values)
            for oid, val in var_binds:
                try:
                    oid_str = str(oid)
                    trap_oids.append(oid_str)
                    
                    # Convert value based on type
                    val_type = val.__class__.__name__
                    if val_type == 'Integer':
                        val_str = str(val)
                    elif val_type == 'OctetString':
                        try:
                            val_str = str(val)
                        except Exception:
                            val_str = val.prettyPrint()
                    else:
                        val_str = val.prettyPrint()
                    
                    trap_data[oid_str] = val_str
                except Exception as val_err:
                    self.logger.error(f"Error processing OID value: {str(val_err)}")
                    # Continue with other OIDs even if one fails
            
            # Determine severity based on mapping
            severity = self._determine_severity(trap_oids, trap_data)
            
            # Create a unique fingerprint for the trap
            fingerprint = "-".join(trap_oids)
            
            # Format alert title and description
            alert_title = "SNMP Trap Received"
            # The OID 1.3.6.1.6.3.1.1.4.1.0 is the standard SNMP trap OID identifier
            if '1.3.6.1.6.3.1.1.4.1.0' in trap_data:
                trap_type_oid = trap_data['1.3.6.1.6.3.1.1.4.1.0']
                alert_title = f"SNMP Trap: {trap_type_oid}"
            
            # Convert trap data to readable format
            alert_description = "\n".join([f"{oid}: {val}" for oid, val in trap_data.items()])
            
            
            alert = {
                "title": alert_title,
                "description": f"SNMP Trap received with the following data:\n{alert_description}",
                "severity": severity.value,
                "fingerprint": fingerprint,
                "source": ["snmp"],
                "raw_data": json.dumps(trap_data),
                "created_at": datetime.utcnow().isoformat(),
            }
            
            self.logger.info(f"Sending alert for SNMP trap: {alert['title']}")
            self._push_alert(alert)
            
        except Exception as e:
            self.logger.error(f"Error processing SNMP trap: {str(e)}")
            self.logger.error(traceback.format_exc())
    
    def _determine_severity(self, oids: List[str], data: Dict[str, str]) -> AlertSeverity:
        """Determine alert severity based on the configured mapping."""
        # Default severity
        default_severity = AlertSeverity.WARNING
        
        if not self._severity_mapping:
            return default_severity
        
        # Check if any OIDs match the patterns in the severity mapping
        for pattern, severity_str in self._severity_mapping.items():
            # Check if pattern matches any OID
            for oid in oids:
                if pattern in oid:
                    return self._parse_severity(severity_str)
            
            # Check if pattern matches any value
            for value in data.values():
                if pattern in value:
                    return self._parse_severity(severity_str)
        
        return default_severity
    
    def _parse_severity(self, severity_str: str) -> AlertSeverity:
        """
        Parse severity string into AlertSeverity enum value.
        
        Args:
            severity_str: Severity string from trap data
            
        Returns:
            AlertSeverity enum value
        """
        severity_map = {
            "INFO": AlertSeverity.INFO,
            "WARNING": AlertSeverity.WARNING,
            "ERROR": AlertSeverity.HIGH,  # 'ERROR' maps to 'high' in Keep system
            "CRITICAL": AlertSeverity.CRITICAL,
        }
        
        return severity_map.get(severity_str, AlertSeverity.WARNING)
    
    def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get logs from the provider."""
        logs = []
        
        # Add debugging information
        debug_info = self.debug_info()
        logs.append({
            "message": "SNMP Provider Debug Information",
            "timestamp": datetime.utcnow().isoformat(),
            "level": "INFO",
            "details": debug_info
        })
        
        # Add basic status information
        status = "Running" if self.running else "Stopped"
        logs.append({
            "message": f"SNMP trap receiver status: {status}",
            "timestamp": datetime.utcnow().isoformat(),
            "level": "INFO",
            "details": {
                "status": status,
                "listen_address": self.authentication_config.listen_address,
                "port": self.authentication_config.port
            }
        })
        
        # Add log for when the trap receiver was started
        if self.running:
            logs.append({
                "message": f"SNMP trap receiver is running on {self.authentication_config.listen_address}:{self.authentication_config.port}",
                "timestamp": datetime.utcnow().isoformat(),
                "level": "INFO",
                "details": {
                    "community": "***" if self.authentication_config.community else "Not set"
                }
            })
            
            # Check if we have a severity mapping
            if self._severity_mapping:
                severity_info = {k: v for k, v in self._severity_mapping.items()}
                logs.append({
                    "message": "SNMP trap severity mapping configured",
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": "INFO",
                    "details": {
                        "severity_mapping": severity_info
                    }
                })
            else:
                logs.append({
                    "message": "No SNMP trap severity mapping configured",
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": "WARNING",
                    "details": {
                        "default_severity": "WARNING"
                    }
                })
        
        return logs
    
    def debug_info(self) -> Dict[str, Any]:
        """Get debugging information about the SNMP provider."""
        # Test UDP port binding
        port_test = {"status": "Unknown", "message": "", "port": self.authentication_config.port}
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            test_socket.bind((self.authentication_config.listen_address, self.authentication_config.port))
            test_socket.close()
            port_test = {"status": "Success", "message": "Port is available", "port": self.authentication_config.port}
        except Exception as e:
            port_test = {
                "status": "Failed", 
                "message": str(e), 
                "port": self.authentication_config.port,
                "reason": f"Port {self.authentication_config.port} might already be in use or requires elevated privileges"
            }
        
        # Get information about the SNMP engine
        engine_info = {"status": "Not initialized"}
        if self.snmp_engine:
            try:
                engine_info = {
                    "status": "Initialized",
                    "transport_dispatcher_jobs": getattr(self.snmp_engine.transportDispatcher, "jobsAmount", "Unknown"),
                    "snmp_engine_id": str(getattr(self.snmp_engine, "snmpEngineID", b"Not available")),
                }
            except Exception as e:
                engine_info = {"status": "Error", "message": str(e)}
        
        return {
            "provider_id": self.provider_id,
            "running": self.running,
            "configuration": {
                "listen_address": self.authentication_config.listen_address,
                "port": self.authentication_config.port,
                "community": "***" if self.authentication_config.community else "Not set",
                "has_severity_mapping": bool(self._severity_mapping)
            },
            "port_test": port_test,
            "snmp_engine": engine_info,
            "thread_active": bool(self.trap_thread and self.trap_thread.is_alive()) if self.trap_thread else False,
        }
    
    def validate_scopes(self) -> Dict[str, Union[bool, str]]:
        """Validate provider scopes."""
        # Check if we can bind to the specified UDP port
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            test_socket.bind((self.authentication_config.listen_address, self.authentication_config.port))
            test_socket.close()
            return {"receive_traps": True}
        except Exception as e:
            return {"receive_traps": f"Failed to bind to {self.authentication_config.listen_address}:{self.authentication_config.port}: {str(e)}"}
    
    @staticmethod
    def get_alert_schema() -> Dict[str, Any]:
        """Get the alert schema description for this provider."""
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Alert title"},
                "description": {"type": "string", "description": "Detailed description of the SNMP trap"},
                "severity": {"type": "string", "enum": ["info", "warning", "error", "critical"]},
                "source": {"type": "array", "items": {"type": "string"}, "description": "Sources of the SNMP trap"},
                "raw_data": {"type": "object", "description": "Raw trap data as OID-value pairs"},
            }
        }
    
    def dispose(self):
        """Clean up resources and release all ports used by the SNMP trap receiver."""
        if not self.running:
            return
            
        self.logger.info("Stopping SNMP trap receiver")
        self.running = False
        
        if self.snmp_engine:
            try:
                transport_dispatcher = self.snmp_engine.transportDispatcher
                
                transport_dispatcher.jobFinished(1)
                
                transport_dispatcher.closeDispatcher()
                
                self.logger.info(f"SNMP engine transport dispatcher stopped, port {self.authentication_config.port} released")
                
            except Exception as e:
                self.logger.error(f"Error during SNMP engine cleanup: {e}")
            finally:
                self.snmp_engine = None
        
     
        if self.trap_thread and self.trap_thread.is_alive():
            try:
                self.trap_thread.join(timeout=5.0) 
                if self.trap_thread.is_alive():
                    self.logger.warning("SNMP trap thread did not stop gracefully within timeout")
            except Exception as e:
                self.logger.error(f"Error joining SNMP trap thread: {e}")
            finally:
                self.trap_thread = None
    
    @property
    def is_consumer(self) -> bool:
        """Mark this provider as a consumer that can be started/stopped."""
        return True
    
    def status(self) -> bool:
        """Check if the SNMP trap receiver is running."""
        return self.running
    
    @staticmethod
    def simulate_alert() -> Dict[str, Any]:
        """Simulate an SNMP trap alert for testing purposes."""
        return {
            "title": "SNMP Trap: coldStart",
            "description": "SNMP Trap received with the following data:\n1.3.6.1.6.3.1.1.5.1: coldStart\n1.3.6.1.2.1.1.1.0: Keep SNMP Test Device",
            "severity": "info",
            "fingerprint": f"snmp-test-trap-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "source": ["snmp"],
            "labels": {
                "trap_oid": "1.3.6.1.6.3.1.1.5.1",
                "device": "Keep SNMP Test Device",
                "trap_type": "coldStart"
            },
            "raw_data": json.dumps({
                "1.3.6.1.6.3.1.1.5.1": "coldStart",
                "1.3.6.1.2.1.1.1.0": "Keep SNMP Test Device"
            }),
            "created_at": datetime.utcnow().isoformat(),
        }