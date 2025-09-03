"""
SNMP Provider for Keep.

This provider enables Keep to receive SNMP traps from network devices
and convert them into actionable alerts.
"""

import asyncio
import dataclasses
import datetime
import logging
from typing import Optional, Dict, Any
import threading

import pydantic

try:
    from pysnmp.entity import engine, config
    from pysnmp.entity.rfc3413 import ntfrcv
    from pysnmp.carrier.asyncore.dgram import udp
    from pysnmp.proto.api import v2c
    from pysnmp.proto import rfc1902
    from pysnmp.smi import builder, view, compiler
except ImportError:
    # Fallback for older pysnmp versions or different package names
    try:
        from pysnmp.entity import engine, config
        from pysnmp.entity.rfc3413 import ntfrcv
        from pysnmp.carrier.asyncio.dgram import udp
        from pysnmp.proto.api import v2c
        from pysnmp.proto import rfc1902
        from pysnmp.smi import builder, view, compiler
    except ImportError as e:
        raise ImportError(f"Failed to import pysnmp modules. Please install pysnmp: {e}")

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """SNMP Provider authentication configuration."""
    
    listen_address: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "IP address to listen for SNMP traps",
            "hint": "0.0.0.0 for all interfaces, or specific IP",
        },
        default="0.0.0.0"
    )
    
    listen_port: int = dataclasses.field(
        metadata={
            "required": True,
            "description": "UDP port to listen for SNMP traps",
            "hint": "Standard SNMP trap port is 162, use 1162+ for non-root",
        },
        default=162
    )
    
    community_string: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMP community string for v1/v2c",
            "hint": "Default community string, often 'public'",
            "sensitive": True,
        },
        default="public"
    )
    
    # SNMPv3 Configuration
    security_name: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 security name (username)",
            "hint": "Required for SNMPv3 authentication",
        },
        default=None
    )
    
    auth_protocol: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 authentication protocol",
            "hint": "MD5 or SHA",
            "options": ["MD5", "SHA"],
        },
        default=None
    )
    
    auth_key: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 authentication key",
            "hint": "Authentication passphrase (8+ characters)",
            "sensitive": True,
        },
        default=None
    )
    
    priv_protocol: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 privacy protocol",
            "hint": "DES or AES",
            "options": ["DES", "AES"],
        },
        default=None
    )
    
    priv_key: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 privacy key",
            "hint": "Privacy passphrase (8+ characters)",
            "sensitive": True,
        },
        default=None
    )


class SnmpProvider(BaseProvider):
    """SNMP Provider for receiving SNMP traps and converting them to Keep alerts."""
    
    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]
    
    PROVIDER_SCOPES = [
        ProviderScope(
            name="receive_traps",
            description="Receive SNMP traps from network devices",
            mandatory=True,
            alias="Receive SNMP Traps",
        )
    ]
    
    # Standard SNMP trap OID to severity mapping
    TRAP_SEVERITY_MAP = {
        "1.3.6.1.6.3.1.1.5.1": AlertSeverity.INFO,      # coldStart
        "1.3.6.1.6.3.1.1.5.2": AlertSeverity.INFO,      # warmStart
        "1.3.6.1.6.3.1.1.5.3": AlertSeverity.WARNING,   # linkDown
        "1.3.6.1.6.3.1.1.5.4": AlertSeverity.INFO,      # linkUp
        "1.3.6.1.6.3.1.1.5.5": AlertSeverity.HIGH,      # authenticationFailure
        "1.3.6.1.6.3.1.1.5.6": AlertSeverity.WARNING,   # egpNeighborLoss
    }
    
    # Standard SNMP trap names
    TRAP_NAMES = {
        "1.3.6.1.6.3.1.1.5.1": "coldStart",
        "1.3.6.1.6.3.1.1.5.2": "warmStart", 
        "1.3.6.1.6.3.1.1.5.3": "linkDown",
        "1.3.6.1.6.3.1.1.5.4": "linkUp",
        "1.3.6.1.6.3.1.1.5.5": "authenticationFailure",
        "1.3.6.1.6.3.1.1.5.6": "egpNeighborLoss",
    }
    
    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.snmp_engine = None
        self.transport_dispatcher = None
        self.trap_receiver_task = None
        self.logger = logging.getLogger(__name__)

        # Auto-start trap receiver after configuration validation
        try:
            self.validate_config()
            self.start_trap_receiver()
        except Exception as e:
            self.logger.warning(f"Failed to auto-start SNMP trap receiver: {e}")
        
    def validate_config(self):
        """Validate the SNMP provider configuration."""
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )
        
        # Validate SNMPv3 configuration consistency
        if self.authentication_config.security_name:
            if self.authentication_config.auth_protocol and not self.authentication_config.auth_key:
                raise ValueError("auth_key is required when auth_protocol is specified")
            if self.authentication_config.priv_protocol and not self.authentication_config.priv_key:
                raise ValueError("priv_key is required when priv_protocol is specified")
            if self.authentication_config.priv_protocol and not self.authentication_config.auth_protocol:
                raise ValueError("auth_protocol is required when priv_protocol is specified")
                
        # Validate port range
        if not (1 <= self.authentication_config.listen_port <= 65535):
            raise ValueError("listen_port must be between 1 and 65535")
            
    def validate_scopes(self) -> Dict[str, bool | str]:
        """Validate provider scopes by testing SNMP engine initialization."""
        validated_scopes = {}

        try:
            # Test SNMP engine initialization
            test_engine = engine.SnmpEngine()
            test_engine.closeDispatcher()
            validated_scopes["receive_traps"] = True
        except Exception as e:
            self.logger.exception("Error validating SNMP scopes")
            validated_scopes["receive_traps"] = f"Failed to initialize SNMP engine: {str(e)}"

        return validated_scopes

    def _setup_snmp_engine(self):
        """Initialize and configure the SNMP engine."""
        if self.snmp_engine:
            return

        self.snmp_engine = engine.SnmpEngine()

        # Configure transport
        config.addTransport(
            self.snmp_engine,
            udp.domainName + (1,),
            udp.UdpTransport().openServerMode(
                (self.authentication_config.listen_address,
                 self.authentication_config.listen_port)
            )
        )

        # Configure community strings for v1/v2c
        config.addV1System(
            self.snmp_engine,
            'my-area',
            self.authentication_config.community_string
        )
        config.addV3User(
            self.snmp_engine,
            'my-user',
            config.usmHMACMD5AuthProtocol, 'my-authkey',
            config.usmDESPrivProtocol, 'my-privkey'
        )

        # Configure SNMPv3 if credentials provided
        if self.authentication_config.security_name:
            self._configure_snmpv3()

    def _configure_snmpv3(self):
        """Configure SNMPv3 authentication and privacy."""
        auth_protocol = None
        priv_protocol = None

        # Map authentication protocols
        if self.authentication_config.auth_protocol:
            if self.authentication_config.auth_protocol.upper() == "MD5":
                auth_protocol = config.usmHMACMD5AuthProtocol
            elif self.authentication_config.auth_protocol.upper() == "SHA":
                auth_protocol = config.usmHMACSHAAuthProtocol

        # Map privacy protocols
        if self.authentication_config.priv_protocol:
            if self.authentication_config.priv_protocol.upper() == "DES":
                priv_protocol = config.usmDESPrivProtocol
            elif self.authentication_config.priv_protocol.upper() == "AES":
                priv_protocol = config.usmAesCfb128Protocol

        # Add SNMPv3 user
        config.addV3User(
            self.snmp_engine,
            self.authentication_config.security_name,
            auth_protocol,
            self.authentication_config.auth_key,
            priv_protocol,
            self.authentication_config.priv_key
        )

    def _trap_handler(self, snmp_engine, state_reference, context_engine_id,
                     context_name, var_binds, cb_ctx):
        """Handle incoming SNMP traps."""
        try:
            # Extract trap information
            trap_data = self._extract_trap_data(var_binds, cb_ctx)

            # Process the trap asynchronously
            asyncio.create_task(self._process_trap(trap_data))

        except Exception as e:
            self.logger.exception(f"Error handling SNMP trap: {e}")

    def _extract_trap_data(self, var_binds, cb_ctx) -> Dict[str, Any]:
        """Extract relevant data from SNMP trap."""
        trap_data = {
            "timestamp": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            "variables": {},
            "source": None,
            "trap_oid": None,
        }

        # Extract source address from callback context
        if hasattr(cb_ctx, 'transportAddress'):
            trap_data["source"] = str(cb_ctx.transportAddress[0])

        # Process variable bindings
        for oid, val in var_binds:
            oid_str = str(oid)

            # Check if this is the trap OID
            if oid_str.startswith("1.3.6.1.6.3.1.1.4.1"):
                trap_data["trap_oid"] = str(val)
            else:
                # Convert value to string representation
                if hasattr(val, 'prettyPrint'):
                    val_str = val.prettyPrint()
                else:
                    val_str = str(val)
                trap_data["variables"][oid_str] = val_str

        return trap_data

    async def _process_trap(self, trap_data: Dict[str, Any]):
        """Process trap data and send to Keep."""
        try:
            # Import here to avoid circular imports
            from keep.api.tasks.process_event_task import process_event

            # Create alert from trap data
            alert_data = self._create_alert_from_trap(trap_data)

            # Send to Keep's event processing system
            await process_event(
                tenant_id=self.context_manager.tenant_id,
                provider_type="snmp",
                provider_id=self.provider_id,
                fingerprint=alert_data.get("fingerprint"),
                api_key_name=None,
                trace_id=None,
                event=alert_data
            )

        except Exception as e:
            self.logger.exception(f"Error processing SNMP trap: {e}")

    def _create_alert_from_trap(self, trap_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create alert data structure from trap data."""
        trap_oid = trap_data.get("trap_oid", "unknown")
        trap_name = self.TRAP_NAMES.get(trap_oid, f"SNMP Trap {trap_oid}")
        severity = self.TRAP_SEVERITY_MAP.get(trap_oid, AlertSeverity.INFO)

        # Create description from trap variables
        description_parts = [f"SNMP Trap: {trap_name}"]
        if trap_data.get("source"):
            description_parts.append(f"Source: {trap_data['source']}")

        for oid, value in trap_data.get("variables", {}).items():
            description_parts.append(f"{oid}: {value}")

        alert_data = {
            "name": trap_name,
            "description": "\n".join(description_parts),
            "severity": severity.value,
            "status": AlertStatus.FIRING.value,
            "source": trap_data.get("source", "unknown"),
            "fingerprint": f"snmp-{trap_oid}-{trap_data.get('source', 'unknown')}",
            "lastReceived": trap_data["timestamp"],
            "labels": {
                "trap_oid": trap_oid,
                "provider": "snmp",
                **trap_data.get("variables", {})
            }
        }

        return alert_data

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format incoming SNMP trap event into AlertDto.

        Args:
            event: Raw SNMP trap event data
            provider_instance: Optional provider instance for context

        Returns:
            AlertDto: Formatted alert object
        """
        # Extract basic alert information
        name = event.get("name", "SNMP Trap")
        description = event.get("description", "SNMP trap received")
        severity = event.get("severity", AlertSeverity.INFO.value)
        status = event.get("status", AlertStatus.FIRING.value)
        source = event.get("source", "unknown")
        fingerprint = event.get("fingerprint", f"snmp-{source}")
        last_received = event.get("lastReceived")
        labels = event.get("labels", {})

        # Convert severity string to AlertSeverity enum if needed
        if isinstance(severity, str):
            try:
                severity = AlertSeverity(severity)
            except ValueError:
                severity = AlertSeverity.INFO

        # Convert status string to AlertStatus enum if needed
        if isinstance(status, str):
            try:
                status = AlertStatus(status)
            except ValueError:
                status = AlertStatus.FIRING

        # Parse timestamp if it's a string
        if isinstance(last_received, str):
            try:
                last_received = datetime.datetime.fromisoformat(
                    last_received.replace('Z', '+00:00')
                )
            except (ValueError, AttributeError):
                last_received = datetime.datetime.now(tz=datetime.timezone.utc)
        elif not last_received:
            last_received = datetime.datetime.now(tz=datetime.timezone.utc)

        return AlertDto(
            id=fingerprint,
            name=name,
            description=description,
            severity=severity,
            status=status,
            source=source,
            fingerprint=fingerprint,
            lastReceived=last_received,
            labels=labels,
        )

    def start_trap_receiver(self):
        """Start the SNMP trap receiver."""
        if self.trap_receiver_task and not self.trap_receiver_task.done():
            self.logger.warning("SNMP trap receiver is already running")
            return

        try:
            self._setup_snmp_engine()

            # Register trap handler
            ntfrcv.NotificationReceiver(self.snmp_engine, self._trap_handler)

            # Start the receiver in a separate thread to avoid blocking
            self.trap_receiver_task = threading.Thread(
                target=self._run_trap_receiver,
                daemon=True
            )
            self.trap_receiver_task.start()

            self.logger.info(
                f"SNMP trap receiver started on {self.authentication_config.listen_address}:"
                f"{self.authentication_config.listen_port}"
            )

        except Exception as e:
            self.logger.exception(f"Failed to start SNMP trap receiver: {e}")
            raise

    def _run_trap_receiver(self):
        """Run the SNMP trap receiver loop."""
        try:
            self.snmp_engine.transportDispatcher.jobStarted(1)
            self.snmp_engine.transportDispatcher.runDispatcher()
        except Exception as e:
            self.logger.exception(f"SNMP trap receiver error: {e}")
        finally:
            self.logger.info("SNMP trap receiver stopped")

    def stop_trap_receiver(self):
        """Stop the SNMP trap receiver."""
        if self.snmp_engine:
            try:
                self.snmp_engine.transportDispatcher.jobFinished(1)
                self.snmp_engine.closeDispatcher()
                self.logger.info("SNMP trap receiver stopped")
            except Exception as e:
                self.logger.exception(f"Error stopping SNMP trap receiver: {e}")

        if self.trap_receiver_task and self.trap_receiver_task.is_alive():
            self.trap_receiver_task.join(timeout=5.0)

    def dispose(self):
        """Clean up provider resources."""
        self.logger.info("Disposing SNMP provider")
        self.stop_trap_receiver()
        self.snmp_engine = None
        self.trap_receiver_task = None

    def _notify(self, **kwargs):
        """
        SNMP provider is primarily for receiving traps, not sending notifications.
        This method is implemented for completeness but will raise an error.
        """
        raise NotImplementedError(
            "SNMP provider is designed for receiving traps, not sending notifications"
        )

    def _query(self, **kwargs):
        """
        SNMP provider is primarily for receiving traps, not querying.
        This method is implemented for completeness but will raise an error.
        """
        raise NotImplementedError(
            "SNMP provider is designed for receiving traps, not querying data"
        )
