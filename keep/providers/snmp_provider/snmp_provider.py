"""
SNMP Provider is a class that allows receiving SNMP traps and converting them to alerts.
"""

import dataclasses
import datetime
import hashlib
import logging
import threading
from typing import Optional

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)

# Standard SNMP Trap OIDs
SNMP_TRAP_OID = "1.3.6.1.6.3.1.1.4.1.0"  # snmpTrapOID
SYSUPTIME_OID = "1.3.6.1.2.1.1.3.0"  # sysUpTime

# Well-known trap OIDs for severity mapping
TRAP_SEVERITY_MAP = {
    # Generic traps (SNMPv1)
    "coldStart": AlertSeverity.WARNING,
    "warmStart": AlertSeverity.INFO,
    "linkDown": AlertSeverity.HIGH,
    "linkUp": AlertSeverity.INFO,
    "authenticationFailure": AlertSeverity.WARNING,
    "egpNeighborLoss": AlertSeverity.HIGH,
    # Default
    "default": AlertSeverity.WARNING,
}


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP Trap Receiver authentication configuration.
    """

    listen_port: int = dataclasses.field(
        default=162,
        metadata={
            "required": True,
            "description": "UDP port to listen for SNMP traps",
            "hint": "Standard SNMP trap port is 162 (requires root) or use 1162 for non-root",
        },
    )
    listen_address: str = dataclasses.field(
        default="0.0.0.0",
        metadata={
            "required": False,
            "description": "IP address to bind the trap receiver",
            "hint": "0.0.0.0 to listen on all interfaces",
        },
    )
    community_string: str = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": "SNMP community string for authentication",
            "hint": "Community string for SNMPv1/v2c traps",
            "sensitive": True,
        },
    )
    snmp_version: str = dataclasses.field(
        default="2c",
        metadata={
            "required": False,
            "description": "SNMP version to accept",
            "hint": "1, 2c, or 3",
            "type": "select",
            "options": ["1", "2c", "3"],
        },
    )
    # SNMPv3 authentication (optional)
    snmpv3_user: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 username",
            "hint": "Required for SNMPv3",
            "config_main_group": "snmpv3",
        },
    )
    snmpv3_auth_protocol: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 authentication protocol",
            "hint": "MD5, SHA, SHA224, SHA256, SHA384, SHA512",
            "type": "select",
            "options": ["MD5", "SHA", "SHA224", "SHA256", "SHA384", "SHA512"],
            "config_main_group": "snmpv3",
        },
    )
    snmpv3_auth_password: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 authentication password",
            "sensitive": True,
            "config_main_group": "snmpv3",
        },
    )
    snmpv3_priv_protocol: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 privacy protocol",
            "hint": "DES, 3DES, AES128, AES192, AES256",
            "type": "select",
            "options": ["DES", "3DES", "AES128", "AES192", "AES256"],
            "config_main_group": "snmpv3",
        },
    )
    snmpv3_priv_password: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMPv3 privacy password",
            "sensitive": True,
            "config_main_group": "snmpv3",
        },
    )


class SnmpProvider(BaseProvider):
    """
    SNMP Trap Receiver Provider.
    
    Listens for SNMP traps (v1, v2c, v3) and converts them to Keep alerts.
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="receive_traps",
            description="Permission to receive and process SNMP traps",
            mandatory=True,
            alias="Receive Traps",
        )
    ]
    PROVIDER_TAGS = ["alert", "queue"]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self._consume = False
        self._transport = None
        self._dispatcher = None
        self._thread: Optional[threading.Thread] = None
        self._err = ""

    def validate_config(self):
        """
        Validates required configuration for SNMP provider.
        """
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate that we can bind to the configured port.
        """
        scopes = {"receive_traps": True}
        
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(1)
            try:
                sock.bind((
                    self.authentication_config.listen_address,
                    self.authentication_config.listen_port
                ))
                sock.close()
            except PermissionError:
                scopes["receive_traps"] = (
                    f"Permission denied: Cannot bind to port {self.authentication_config.listen_port}. "
                    "Try using a port > 1024 or run with elevated privileges."
                )
            except OSError as e:
                scopes["receive_traps"] = f"Cannot bind to port: {str(e)}"
        except Exception as e:
            scopes["receive_traps"] = f"Error validating port: {str(e)}"
            
        return scopes

    def dispose(self):
        """
        Dispose of the provider.
        """
        self.stop_consume()

    def status(self) -> dict:
        """
        Return the status of the provider.
        """
        if not self._consume:
            status = "stopped"
        elif self._transport is None:
            status = "not-initialized"
        else:
            status = "running"
            
        return {
            "status": status,
            "error": self._err,
            "port": self.authentication_config.listen_port,
            "address": self.authentication_config.listen_address,
        }

    def start_consume(self):
        """
        Start the SNMP trap receiver.
        """
        self._consume = True
        self._err = ""
        
        try:
            from pysnmp.carrier.asyncio.dgram import udp
            from pysnmp.entity import config as snmp_config
            from pysnmp.entity import engine
            from pysnmp.entity.rfc3413 import ntfrcv
            import asyncio
        except ImportError as e:
            self._err = f"pysnmp not installed: {str(e)}. Install with: pip install pysnmp-lextudio"
            self.logger.error(self._err)
            return

        self.logger.info(
            f"Starting SNMP trap receiver on "
            f"{self.authentication_config.listen_address}:{self.authentication_config.listen_port}"
        )

        # Create SNMP engine
        snmp_engine = engine.SnmpEngine()
        
        # Configure transport
        try:
            snmp_config.addTransport(
                snmp_engine,
                udp.DOMAIN_NAME,
                udp.UdpTransport().openServerMode(
                    (self.authentication_config.listen_address,
                     self.authentication_config.listen_port)
                )
            )
        except Exception as e:
            self._err = f"Failed to bind to port: {str(e)}"
            self.logger.error(self._err)
            return

        # Configure community string for SNMPv1/v2c
        if self.authentication_config.snmp_version in ["1", "2c"]:
            snmp_config.addV1System(
                snmp_engine,
                "keep-area",
                self.authentication_config.community_string
            )

        # Configure SNMPv3 user if provided
        if (self.authentication_config.snmp_version == "3" and 
            self.authentication_config.snmpv3_user):
            self._configure_snmpv3(snmp_engine)

        # Create callback for receiving traps
        def trap_callback(snmp_engine, state_ref, context_id, context_name, var_binds, cb_ctx):
            self._handle_trap(snmp_engine, state_ref, context_id, context_name, var_binds)

        # Register callback
        ntfrcv.NotificationReceiver(snmp_engine, trap_callback)

        self.logger.info("SNMP trap receiver started successfully")
        
        # Run the SNMP engine in a separate thread
        def run_engine():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                snmp_engine.transportDispatcher.jobStarted(1)
                
                while self._consume:
                    try:
                        snmp_engine.transportDispatcher.runDispatcher(timeout=1.0)
                    except Exception as e:
                        if self._consume:
                            self.logger.warning(f"Dispatcher error: {e}")
                        break
                        
            except Exception as e:
                self._err = str(e)
                self.logger.exception("SNMP engine error")
            finally:
                snmp_engine.transportDispatcher.closeDispatcher()
                self.logger.info("SNMP trap receiver stopped")

        self._thread = threading.Thread(target=run_engine, daemon=True)
        self._thread.start()

    def _configure_snmpv3(self, snmp_engine):
        """
        Configure SNMPv3 authentication and privacy.
        """
        from pysnmp.entity import config as snmp_config
        from pysnmp.hlapi import (
            usmHMACMD5AuthProtocol,
            usmHMACSHAAuthProtocol,
            usmHMAC128SHA224AuthProtocol,
            usmHMAC192SHA256AuthProtocol,
            usmHMAC256SHA384AuthProtocol,
            usmHMAC384SHA512AuthProtocol,
            usmDESPrivProtocol,
            usm3DESEDEPrivProtocol,
            usmAesCfb128Protocol,
            usmAesCfb192Protocol,
            usmAesCfb256Protocol,
            usmNoAuthProtocol,
            usmNoPrivProtocol,
        )

        auth_protocols = {
            "MD5": usmHMACMD5AuthProtocol,
            "SHA": usmHMACSHAAuthProtocol,
            "SHA224": usmHMAC128SHA224AuthProtocol,
            "SHA256": usmHMAC192SHA256AuthProtocol,
            "SHA384": usmHMAC256SHA384AuthProtocol,
            "SHA512": usmHMAC384SHA512AuthProtocol,
        }

        priv_protocols = {
            "DES": usmDESPrivProtocol,
            "3DES": usm3DESEDEPrivProtocol,
            "AES128": usmAesCfb128Protocol,
            "AES192": usmAesCfb192Protocol,
            "AES256": usmAesCfb256Protocol,
        }

        auth_proto = auth_protocols.get(
            self.authentication_config.snmpv3_auth_protocol,
            usmNoAuthProtocol
        )
        priv_proto = priv_protocols.get(
            self.authentication_config.snmpv3_priv_protocol,
            usmNoPrivProtocol
        )

        snmp_config.addV3User(
            snmp_engine,
            self.authentication_config.snmpv3_user,
            auth_proto,
            self.authentication_config.snmpv3_auth_password or "",
            priv_proto,
            self.authentication_config.snmpv3_priv_password or "",
        )

    def _handle_trap(self, snmp_engine, state_ref, context_id, context_name, var_binds):
        """
        Handle incoming SNMP trap and push as alert.
        """
        try:
            # Extract trap information
            trap_data = {}
            trap_oid = None
            
            for oid, val in var_binds:
                oid_str = str(oid)
                val_str = str(val) if val else ""
                
                # Extract trap OID
                if oid_str == SNMP_TRAP_OID or oid_str.startswith("1.3.6.1.6.3.1.1.4.1"):
                    trap_oid = val_str
                
                trap_data[oid_str] = val_str

            # Get source address if available
            try:
                exec_context = snmp_engine.observer.getExecutionContext(
                    'rfc3412.receiveMessage:request'
                )
                source_address = exec_context.get('transportAddress', ('unknown', 0))
                source_ip = source_address[0] if source_address else 'unknown'
            except Exception:
                source_ip = 'unknown'

            self.logger.info(
                f"Received SNMP trap from {source_ip}",
                extra={"trap_oid": trap_oid, "var_binds_count": len(var_binds)}
            )

            # Build alert
            alert_data = self._build_alert_data(trap_oid, trap_data, source_ip)
            
            # Push alert to Keep
            self._push_alert(alert_data)
            
        except Exception as e:
            self.logger.exception(f"Error handling SNMP trap: {e}")

    def _build_alert_data(self, trap_oid: str, trap_data: dict, source_ip: str) -> dict:
        """
        Build alert data from SNMP trap.
        """
        # Determine trap name from OID
        trap_name = self._get_trap_name(trap_oid)
        
        # Determine severity
        severity = self._get_severity(trap_oid, trap_data)
        
        # Generate fingerprint
        fingerprint = self._generate_fingerprint(trap_oid, source_ip, trap_data)
        
        # Build description from var binds
        description_parts = []
        for oid, value in trap_data.items():
            if oid != SNMP_TRAP_OID and oid != SYSUPTIME_OID:
                description_parts.append(f"{oid}: {value}")
        description = "\n".join(description_parts) if description_parts else f"SNMP trap received: {trap_oid}"

        return {
            "id": fingerprint,
            "name": trap_name,
            "status": AlertStatus.FIRING.value,
            "severity": severity.value if hasattr(severity, 'value') else severity.name.lower(),
            "source": ["snmp"],
            "message": f"SNMP trap from {source_ip}: {trap_name}",
            "description": description,
            "lastReceived": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "fingerprint": fingerprint,
            "labels": {
                "source_ip": source_ip,
                "trap_oid": trap_oid or "unknown",
                **{k: v for k, v in trap_data.items() if k not in [SNMP_TRAP_OID, SYSUPTIME_OID]},
            },
            "service": source_ip,
            "environment": "production",
        }

    def _get_trap_name(self, trap_oid: str) -> str:
        """
        Get human-readable name from trap OID.
        """
        # Standard SNMPv1 generic traps
        standard_traps = {
            "1.3.6.1.6.3.1.1.5.1": "coldStart",
            "1.3.6.1.6.3.1.1.5.2": "warmStart",
            "1.3.6.1.6.3.1.1.5.3": "linkDown",
            "1.3.6.1.6.3.1.1.5.4": "linkUp",
            "1.3.6.1.6.3.1.1.5.5": "authenticationFailure",
            "1.3.6.1.6.3.1.1.5.6": "egpNeighborLoss",
        }
        
        if trap_oid in standard_traps:
            return standard_traps[trap_oid]
        
        return f"snmp-trap-{trap_oid}" if trap_oid else "snmp-trap-unknown"

    def _get_severity(self, trap_oid: str, trap_data: dict) -> AlertSeverity:
        """
        Determine severity from trap OID or data.
        """
        trap_name = self._get_trap_name(trap_oid)
        
        # Check known trap types
        for name, severity in TRAP_SEVERITY_MAP.items():
            if name.lower() in trap_name.lower():
                return severity
        
        # Check for severity in trap data
        for oid, value in trap_data.items():
            value_lower = str(value).lower()
            if "critical" in value_lower:
                return AlertSeverity.CRITICAL
            elif "error" in value_lower or "high" in value_lower:
                return AlertSeverity.HIGH
            elif "warning" in value_lower:
                return AlertSeverity.WARNING
            elif "info" in value_lower:
                return AlertSeverity.INFO
        
        return AlertSeverity.WARNING

    def _generate_fingerprint(self, trap_oid: str, source_ip: str, trap_data: dict) -> str:
        """
        Generate a unique fingerprint for the trap.
        """
        # Create fingerprint from trap OID and source
        fingerprint_data = f"{trap_oid}:{source_ip}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]

    def stop_consume(self):
        """
        Stop the SNMP trap receiver.
        """
        self._consume = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self.logger.info("SNMP trap receiver stop requested")

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "SnmpProvider" = None
    ) -> AlertDto:
        """
        Format an incoming SNMP trap event into an AlertDto.
        
        This is called when receiving events via webhook endpoint.
        """
        # Extract trap information
        trap_oid = event.get("trap_oid", event.get("oid", ""))
        source_ip = event.get("source_ip", event.get("agent", "unknown"))
        var_binds = event.get("var_binds", event.get("variables", {}))
        
        # Get trap name
        trap_name = "snmp-trap"
        standard_traps = {
            "1.3.6.1.6.3.1.1.5.1": "coldStart",
            "1.3.6.1.6.3.1.1.5.2": "warmStart",
            "1.3.6.1.6.3.1.1.5.3": "linkDown",
            "1.3.6.1.6.3.1.1.5.4": "linkUp",
            "1.3.6.1.6.3.1.1.5.5": "authenticationFailure",
        }
        if trap_oid in standard_traps:
            trap_name = standard_traps[trap_oid]
        
        # Determine severity
        severity = AlertSeverity.WARNING
        severity_map = {
            "linkDown": AlertSeverity.HIGH,
            "linkUp": AlertSeverity.INFO,
            "coldStart": AlertSeverity.WARNING,
            "warmStart": AlertSeverity.INFO,
            "authenticationFailure": AlertSeverity.WARNING,
        }
        if trap_name in severity_map:
            severity = severity_map[trap_name]
        
        # Check event data for severity hints
        event_str = str(event).lower()
        if "critical" in event_str:
            severity = AlertSeverity.CRITICAL
        elif "error" in event_str:
            severity = AlertSeverity.HIGH
        
        # Generate fingerprint
        fingerprint = hashlib.sha256(
            f"{trap_oid}:{source_ip}".encode()
        ).hexdigest()[:16]
        
        # Build description
        if isinstance(var_binds, dict):
            description = "\n".join([f"{k}: {v}" for k, v in var_binds.items()])
        elif isinstance(var_binds, list):
            description = "\n".join([str(v) for v in var_binds])
        else:
            description = str(var_binds) if var_binds else f"SNMP trap: {trap_oid}"
        
        return AlertDto(
            id=fingerprint,
            name=trap_name,
            status=AlertStatus.FIRING,
            severity=severity,
            source=["snmp"],
            message=event.get("message", f"SNMP trap from {source_ip}"),
            description=description,
            lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            fingerprint=fingerprint,
            labels={
                "source_ip": source_ip,
                "trap_oid": trap_oid,
                **(var_binds if isinstance(var_binds, dict) else {}),
            },
            service=source_ip,
        )

    @classmethod
    def simulate_alert(cls) -> dict:
        """
        Simulate an SNMP trap alert for testing.
        """
        import random
        
        traps = [
            {
                "trap_oid": "1.3.6.1.6.3.1.1.5.3",
                "name": "linkDown",
                "source_ip": "192.168.1.1",
                "message": "Interface eth0 is down",
                "var_binds": {
                    "ifIndex": "1",
                    "ifDescr": "eth0",
                    "ifAdminStatus": "up",
                    "ifOperStatus": "down",
                },
            },
            {
                "trap_oid": "1.3.6.1.6.3.1.1.5.4",
                "name": "linkUp",
                "source_ip": "192.168.1.1",
                "message": "Interface eth0 is up",
                "var_binds": {
                    "ifIndex": "1",
                    "ifDescr": "eth0",
                    "ifAdminStatus": "up",
                    "ifOperStatus": "up",
                },
            },
            {
                "trap_oid": "1.3.6.1.6.3.1.1.5.1",
                "name": "coldStart",
                "source_ip": "192.168.1.2",
                "message": "Device rebooted",
                "var_binds": {
                    "sysUpTime": "0",
                    "sysDescr": "Network Switch Model XYZ",
                },
            },
            {
                "trap_oid": "1.3.6.1.6.3.1.1.5.5",
                "name": "authenticationFailure",
                "source_ip": "192.168.1.100",
                "message": "SNMP authentication failure",
                "var_binds": {
                    "snmpTrapCommunity": "wrong_community",
                },
            },
        ]
        
        return random.choice(traps)


if __name__ == "__main__":
    # Test the provider
    import logging
    import os
    import time
    
    logging.basicConfig(level=logging.INFO)
    
    os.environ["KEEP_API_URL"] = "http://localhost:8080"
    
    from keep.api.core.dependencies import SINGLE_TENANT_UUID
    
    context_manager = ContextManager(tenant_id=SINGLE_TENANT_UUID)
    config = {
        "authentication": {
            "listen_port": 1162,  # Non-root port for testing
            "listen_address": "0.0.0.0",
            "community_string": "public",
            "snmp_version": "2c",
        }
    }
    
    from keep.providers.providers_factory import ProvidersFactory
    
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="snmp-test",
        provider_type="snmp",
        provider_config=config,
    )
    
    print(f"Provider status: {provider.status()}")
    print("Starting SNMP trap receiver...")
    provider.start_consume()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        provider.stop_consume()
