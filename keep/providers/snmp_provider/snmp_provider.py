"""
SNMP Provider is a class that provides a way to receive SNMP traps and convert them into Keep alerts.

This provider supports:
- SNMPv1, SNMPv2c, and SNMPv3 trap reception
- Authentication and encryption for SNMPv3
- Automatic conversion of SNMP traps to Keep alerts
- Configurable listening address and port
"""

import dataclasses
import datetime
import threading
from typing import Any, Dict, List, Optional

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SnmpProviderAuthConfig is a class that allows you to configure SNMP trap receiver.
    """

    listen_address: str = dataclasses.field(
        default="0.0.0.0",
        metadata={
            "required": False,
            "description": "IP address to listen on for SNMP traps",
            "hint": "0.0.0.0 (listen on all interfaces)",
            "sensitive": False,
        }
    )

    listen_port: int = dataclasses.field(
        default=162,
        metadata={
            "required": False,
            "description": "UDP port to listen on for SNMP traps",
            "hint": "162 (default SNMP trap port)",
            "sensitive": False,
        }
    )

    community_string: str = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": "SNMP community string for v1/v2c traps",
            "hint": "public",
            "sensitive": True,
        }
    )

    snmp_engine_id: str = dataclasses.field(
        default="80001f8880e9630000d61ff449",
        metadata={
            "required": False,
            "description": "SNMP Engine ID for v3 (hex string)",
            "hint": "80001f8880e9630000d61ff449",
            "sensitive": False,
        }
    )

    # SNMPv3 User-based Security Model (USM) configuration
    security_name: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 security name (username)",
            "hint": "snmpuser",
            "sensitive": False,
        }
    )

    auth_protocol: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 authentication protocol (MD5 or SHA)",
            "hint": "MD5",
            "sensitive": False,
        }
    )

    auth_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 authentication key",
            "hint": "authkey123",
            "sensitive": True,
        }
    )

    priv_protocol: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 privacy protocol (DES or AES)",
            "hint": "DES",
            "sensitive": False,
        }
    )

    priv_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 privacy key",
            "hint": "privkey123",
            "sensitive": True,
        }
    )


class SnmpProvider(BaseProvider):
    """Receive SNMP traps and convert them to Keep alerts."""
    
    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring", "Network"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="receive_traps",
            description="Receive SNMP traps and convert to alerts",
        ),
    ]

    # SNMP trap severity mapping based on generic trap types
    SEVERITY_MAP = {
        "1.3.6.1.6.3.1.1.5.1": AlertSeverity.INFO,      # coldStart
        "1.3.6.1.6.3.1.1.5.2": AlertSeverity.INFO,      # warmStart  
        "1.3.6.1.6.3.1.1.5.3": AlertSeverity.CRITICAL,  # linkDown
        "1.3.6.1.6.3.1.1.5.4": AlertSeverity.INFO,      # linkUp
        "1.3.6.1.6.3.1.1.5.5": AlertSeverity.WARNING,   # authenticationFailure
        "1.3.6.1.6.3.1.1.5.6": AlertSeverity.WARNING,   # egpNeighborLoss
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.snmp_engine = None
        self.trap_receiver_thread = None
        self.stop_event = threading.Event()
        self.received_traps = []

    def dispose(self):
        """
        Dispose the provider and stop SNMP trap receiver
        """
        self.logger.info("Disposing SNMP provider")
        if self.stop_event:
            self.stop_event.set()
        if self.trap_receiver_thread and self.trap_receiver_thread.is_alive():
            self.trap_receiver_thread.join(timeout=5)
        if self.snmp_engine:
            self.snmp_engine.closeDispatcher()

    def validate_config(self):
        """
        Validates required configuration for SNMP provider.
        """
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        """
        Validate scopes for the provider by checking configuration
        """
        self.logger.info("Validating SNMP provider scopes")
        try:
            # Validate port number
            if not (0 < self.authentication_config.listen_port < 65536):
                raise ValueError(f"Invalid port number: {self.authentication_config.listen_port}. Must be between 1 and 65535")
            
            # Validate IP address format
            import socket
            try:
                socket.inet_aton(self.authentication_config.listen_address)
            except socket.error:
                raise ValueError(f"Invalid IP address: {self.authentication_config.listen_address}")
            
            # Validate SNMPv3 configuration if provided
            if self.authentication_config.security_name:
                if not self.authentication_config.auth_protocol:
                    raise ValueError("SNMPv3 security name provided but auth protocol is missing")
                if not self.authentication_config.auth_key:
                    raise ValueError("SNMPv3 security name provided but auth key is missing")
                if self.authentication_config.auth_protocol not in ["MD5", "SHA"]:
                    raise ValueError(f"Invalid auth protocol: {self.authentication_config.auth_protocol}. Must be MD5 or SHA")
                if self.authentication_config.priv_protocol and self.authentication_config.priv_protocol not in ["DES", "AES"]:
                    raise ValueError(f"Invalid privacy protocol: {self.authentication_config.priv_protocol}. Must be DES or AES")
            
            self.logger.info("SNMP provider configuration validated successfully")
            return {"receive_traps": True}
        except Exception as e:
            self.logger.error(f"SNMP provider validation failed: {str(e)}")
            return {"receive_traps": str(e)}

    def _start_trap_receiver(self):
        """
        Start the SNMP trap receiver in a separate thread
        """
        self.logger.info("Starting SNMP trap receiver")
        self.trap_receiver_thread = threading.Thread(
            target=self._run_trap_receiver, daemon=True
        )
        self.trap_receiver_thread.start()

    def _run_trap_receiver(self):
        """
        Run the SNMP trap receiver using threading (simplified)
        """
        try:
            self._setup_snmp_engine()
            self._listen_for_traps()
        except Exception as e:
            self.logger.exception("Error in SNMP trap receiver", extra={"error": e})

    def _setup_snmp_engine(self):
        """
        Setup SNMP engine and configure communities/users (simplified)
        """
        try:
            from pysnmp.carrier.asyncio import dgram
            from pysnmp.entity import config, engine
            from pysnmp.entity.rfc3413 import ntfrcv
            
            self.snmp_engine = engine.SnmpEngine()

            # Configure transport
            config.addTransport(
                self.snmp_engine,
                dgram.udpDomainName,
                dgram.UdpTransport().openServerMode(
                    (self.authentication_config.listen_address, 
                     self.authentication_config.listen_port)
                )
            )

            # Configure community for SNMPv1/v2c
            config.addV1System(
                self.snmp_engine, 
                "my-area", 
                self.authentication_config.community_string
            )

            # Configure SNMPv3 user if credentials provided
            if self.authentication_config.security_name:
                auth_protocol = None
                priv_protocol = None
                
                if self.authentication_config.auth_protocol:
                    if self.authentication_config.auth_protocol.upper() == "MD5":
                        auth_protocol = config.usmHMACMD5AuthProtocol
                    elif self.authentication_config.auth_protocol.upper() == "SHA":
                        auth_protocol = config.usmHMACSHAAuthProtocol
                        
                if self.authentication_config.priv_protocol:
                    if self.authentication_config.priv_protocol.upper() == "DES":
                        priv_protocol = config.usmDESPrivProtocol
                    elif self.authentication_config.priv_protocol.upper() == "AES":
                        priv_protocol = config.usmAesCfb128Protocol

                config.addV3User(
                    self.snmp_engine,
                    self.authentication_config.security_name,
                    auth_protocol,
                    self.authentication_config.auth_key,
                    priv_protocol, 
                    self.authentication_config.priv_key
                )

            self.logger.info("SNMP engine configured successfully")
        except ImportError:
            self.logger.warning("pysnmp not available, SNMP trap receiver disabled")
            raise

    def _listen_for_traps(self):
        """
        Listen for SNMP traps and process them (simplified)
        """
        try:
            from pysnmp.entity.rfc3413 import ntfrcv
            
            ntfrcv.NotificationReceiver(self.snmp_engine, self._cb_fun)
            
            self.logger.info(
                f"SNMP trap receiver listening on {self.authentication_config.listen_address}:{self.authentication_config.listen_port}"
            )
            
            self.snmp_engine.transportDispatcher.jobStarted(1)
            
            try:
                # Run until stop event is set
                while not self.stop_event.is_set():
                    self.snmp_engine.transportDispatcher.runDispatcher(timeout=1.0)
            finally:
                self.snmp_engine.transportDispatcher.jobFinished(1)
        except ImportError:
            self.logger.warning("pysnmp not available for trap listening")
            raise

    def _cb_fun(self, snmp_engine, state_reference, context_engine_id, context_name,
                var_binds, cb_ctx):
        """
        Callback function to process received SNMP traps
        
        Args:
            snmp_engine: The SNMP engine instance
            state_reference: State reference for the notification
            context_engine_id: Context engine ID
            context_name: Context name
            var_binds: Variable bindings from the trap
            cb_ctx: Callback context
        """
        try:
            # Extract source IP from transport data if available
            transport_info = {}
            exec_context = snmp_engine.observer.getExecutionContext(
                'rfc3412.receiveMessage:request'
            )
            if exec_context:
                transport_domain, transport_address = exec_context.get(
                    'transportDomain', (None, None)
                ), exec_context.get('transportAddress', (None, None))
                if transport_address:
                    transport_info['source_ip'] = transport_address[0]
                    transport_info['source_port'] = transport_address[1]
            
            # Extract trap information
            trap_data = self._extract_trap_data(var_binds)
            trap_data.update(transport_info)
            
            # Convert to AlertDto
            alert = self._convert_trap_to_alert(trap_data)
            
            # Store the alert with overflow protection
            max_alerts = 1000  # Maximum alerts to keep in memory
            if len(self.received_traps) >= max_alerts:
                self.logger.warning(f"Alert buffer full ({max_alerts}), removing oldest alert")
                self.received_traps.pop(0)
            
            self.received_traps.append(alert)
            
            self.logger.info(
                "Received SNMP trap",
                extra={
                    "trap_oid": trap_data.get("trap_oid"),
                    "source_ip": trap_data.get("source_ip"),
                    "alert_name": alert.name,
                    "severity": alert.severity.value
                }
            )
            
        except Exception as e:
            self.logger.error(
                f"Error processing SNMP trap: {str(e)}",
                extra={"var_binds": str(var_binds)[:200]}  # Log first 200 chars
            )

    def _extract_trap_data(self, var_binds) -> Dict[str, Any]:
        """
        Extract data from SNMP trap variable bindings
        """
        trap_data = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "variables": {},
            "trap_oid": None,
            "enterprise_oid": None,
            "generic_trap": None,
            "specific_trap": None,
        }

        for name, val in var_binds:
            oid_str = str(name)
            value_str = str(val)
            
            # Store all variable bindings
            trap_data["variables"][oid_str] = value_str
            
            # Extract specific trap information
            if oid_str == "1.3.6.1.6.3.1.1.4.1.0":  # snmpTrapOID
                trap_data["trap_oid"] = value_str
            elif oid_str == "1.3.6.1.2.1.1.3.0":  # sysUpTime
                trap_data["uptime"] = value_str
            elif oid_str == "1.3.6.1.2.1.1.5.0":  # sysName
                trap_data["system_name"] = value_str
            elif oid_str == "1.3.6.1.2.1.1.1.0":  # sysDescr
                trap_data["system_description"] = value_str

        return trap_data

    def _convert_trap_to_alert(self, trap_data: Dict[str, Any]) -> AlertDto:
        """
        Convert SNMP trap data to AlertDto
        
        Args:
            trap_data: Dictionary containing extracted trap information
            
        Returns:
            AlertDto: Converted alert object
        """
        trap_oid = trap_data.get("trap_oid", "unknown")
        system_name = trap_data.get("system_name", "unknown")
        source_ip = trap_data.get("source_ip", "")
        
        # Determine severity based on trap OID
        severity = self.SEVERITY_MAP.get(trap_oid, AlertSeverity.WARNING)
        
        # Generate alert name based on trap type
        trap_names = {
            "1.3.6.1.6.3.1.1.5.1": "Cold Start",
            "1.3.6.1.6.3.1.1.5.2": "Warm Start", 
            "1.3.6.1.6.3.1.1.5.3": "Link Down",
            "1.3.6.1.6.3.1.1.5.4": "Link Up",
            "1.3.6.1.6.3.1.1.5.5": "Authentication Failure",
            "1.3.6.1.6.3.1.1.5.6": "EGP Neighbor Loss",
        }
        
        trap_type = trap_names.get(trap_oid, "SNMP Trap")
        alert_name = f"{trap_type} - {system_name}"
        
        # Build detailed message
        message_parts = [f"SNMP trap received: {trap_oid}"]
        if source_ip:
            message_parts.append(f"from {source_ip}")
        
        # Add interface info for link up/down traps
        if trap_oid in ["1.3.6.1.6.3.1.1.5.3", "1.3.6.1.6.3.1.1.5.4"]:
            if_index = trap_data.get("variables", {}).get("1.3.6.1.2.1.2.2.1.1.1", "")
            if_descr = trap_data.get("variables", {}).get("1.3.6.1.2.1.2.2.1.2.1", "")
            if if_descr:
                message_parts.append(f"Interface: {if_descr}")
            elif if_index:
                message_parts.append(f"Interface Index: {if_index}")
        
        # Build description
        description = trap_data.get("system_description", f"{trap_type} notification")
        if trap_data.get("uptime"):
            description += f" (System uptime: {trap_data['uptime']})"
        
        # Prepare labels - clean up OIDs for readability
        labels = {
            "trap_oid": trap_oid,
            "trap_type": trap_type,
            "system_name": system_name,
            "source_ip": source_ip,
        }
        
        # Add uptime if available
        if trap_data.get("uptime"):
            labels["uptime"] = trap_data["uptime"]
        
        # Add other variables with cleaner names where possible
        oid_names = {
            "1.3.6.1.2.1.1.1.0": "system_description",
            "1.3.6.1.2.1.1.3.0": "uptime_ticks",
            "1.3.6.1.2.1.1.5.0": "system_name",
            "1.3.6.1.2.1.2.2.1.1.1": "interface_index",
            "1.3.6.1.2.1.2.2.1.2.1": "interface_description",
        }
        
        for oid, value in trap_data.get("variables", {}).items():
            label_name = oid_names.get(oid, oid)
            labels[label_name] = str(value)

        return AlertDto(
            id=None,
            name=alert_name,
            status=AlertStatus.FIRING,
            severity=severity,
            lastReceived=trap_data["timestamp"],
            message=" ".join(message_parts),
            description=description,
            source=["snmp"],
            labels=labels,
            hostname=system_name if system_name != "unknown" else source_ip,
        )

    def _get_alerts(self) -> List[AlertDto]:
        """
        Get received SNMP trap alerts
        """
        self.logger.info("Getting SNMP trap alerts")
        
        # Start trap receiver if not already running
        if not self.trap_receiver_thread or not self.trap_receiver_thread.is_alive():
            self._start_trap_receiver()
        
        # Return accumulated alerts
        alerts = self.received_traps.copy()
        self.received_traps.clear()  # Clear after retrieving
        
        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format SNMP trap webhook alert (if webhook functionality is added later)
        """
        return AlertDto(
            id=event.get("id"),
            name=event.get("name", "SNMP Trap Alert"),
            status=AlertStatus.FIRING,
            severity=AlertSeverity.WARNING,
            lastReceived=event.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat()),
            message=event.get("message", "SNMP trap received via webhook"),
            description=event.get("description"),
            source=["snmp"],
            labels=event.get("labels", {}),
            hostname=event.get("hostname"),
        )


