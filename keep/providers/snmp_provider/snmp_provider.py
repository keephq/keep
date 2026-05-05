"""
SNMP Provider for receiving SNMP traps.
"""

import asyncio
import hashlib
import json
import socket
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import uuid

from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import config, engine
from pysnmp.entity.rfc3413 import ntfrcv
from pysnmp.proto import rfc1902
from pysnmp.hlapi.v3arch.asyncio import (
    usmHMACMD5AuthProtocol, usmHMACSHAAuthProtocol,
    usmDESPrivProtocol, usmAesCfb128Protocol,
    usmNoAuthProtocol, usmNoPrivProtocol,
)
import pyasn1.codec.ber.decoder

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
            "validation": "port",
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

    severity_mapping: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "JSON mapping of OID patterns to Keep severity levels [Optional]",
            "config_main_group": "authentication",
        },
        default=None,
    )

    username: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 username",
            "config_main_group": "authentication",
        },
        default=None,
    )

    auth_protocol: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "Authentication protocol (MD5 or SHA)",
            "config_main_group": "authentication",
        },
        default=None,
    )

    auth_key: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 authentication password",
            "config_main_group": "authentication",
            "sensitive": True,
        },
        default=None,
    )

    priv_protocol: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "Privacy protocol (DES or AES)",
            "config_main_group": "authentication",
        },
        default=None,
    )

    priv_key: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 privacy password",
            "config_main_group": "authentication",
            "sensitive": True,
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

    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["alert"]
    FINGERPRINT_FIELDS = ["fingerprint"]

    DEFAULT_OID_SEVERITY_MAP = {
        # Standard SNMPv2 trap types
        "1.3.6.1.6.3.1.1.5.1": AlertSeverity.INFO,       # coldStart
        "1.3.6.1.6.3.1.1.5.2": AlertSeverity.INFO,       # warmStart
        "1.3.6.1.6.3.1.1.5.3": AlertSeverity.HIGH,       # linkDown
        "1.3.6.1.6.3.1.1.5.4": AlertSeverity.INFO,       # linkUp
        "1.3.6.1.6.3.1.1.5.5": AlertSeverity.WARNING,    # authenticationFailure
        "1.3.6.1.6.3.1.1.5.6": AlertSeverity.WARNING,    # egpNeighborLoss
        # UPS / Power
        "1.3.6.1.2.1.33.2.0.1": AlertSeverity.CRITICAL,  # UPS on battery
        "1.3.6.1.2.1.33.2.0.2": AlertSeverity.CRITICAL,  # UPS battery low
        "1.3.6.1.2.1.33.2.0.3": AlertSeverity.CRITICAL,  # UPS battery depleted
        "1.3.6.1.2.1.33.2.0.4": AlertSeverity.INFO,      # UPS power restored
        # Cisco
        "1.3.6.1.4.1.9.9.43.2.0.1": AlertSeverity.CRITICAL,  # Cisco config change
        "1.3.6.1.4.1.9.2.1.56":     AlertSeverity.CRITICAL,  # Cisco reload
        # Interface / Network
        "1.3.6.1.2.1.10.166.3":     AlertSeverity.HIGH,   # MPLS tunnel down
        "1.3.6.1.4.1.9.9.187.1.2.0.1": AlertSeverity.HIGH,  # BGP backward transition
    }

    # Auto-detect severity from trap value keywords
    SEVERITY_KEYWORDS = {
        AlertSeverity.CRITICAL: ["critical", "fatal", "emergency", "down", "fail", "crash", "unreachable"],
        AlertSeverity.HIGH:     ["error", "major", "high", "unavailable", "lost"],
        AlertSeverity.WARNING:  ["warning", "warn", "minor", "degraded", "slow"],
        AlertSeverity.INFO:     ["info", "notice", "up", "clear", "normal", "ok", "restored", "success"],
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.snmp_engine = None
        self.trap_thread = None
        self.running = False
        self._severity_mapping = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        if self.authentication_config.severity_mapping:
            try:
                self._severity_mapping = json.loads(self.authentication_config.severity_mapping)
                self.logger.info(f"Loaded severity mapping: {self._severity_mapping}")
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse severity mapping JSON: {e}")

    def validate_config(self):
        """Validate the provider configuration."""
        self.authentication_config = SnmpProviderAuthConfig(**self.config.authentication)

        auth = self.authentication_config
        if auth.username:
            valid_auth_protocols = {None, "MD5", "SHA"}
            if auth.auth_protocol not in valid_auth_protocols:
                raise ValueError("auth_protocol must be one of: MD5, SHA")

            valid_priv_protocols = {None, "DES", "AES"}
            if auth.priv_protocol not in valid_priv_protocols:
                raise ValueError("priv_protocol must be one of: DES, AES")

            if auth.auth_protocol and not auth.auth_key:
                raise ValueError("auth_key required when auth_protocol is set")

            if auth.auth_key and not auth.auth_protocol:
                raise ValueError("auth_protocol required when auth_key is set")

            if auth.priv_protocol and not auth.auth_protocol:
                raise ValueError("auth_protocol must be set when priv_protocol is used")

            if auth.priv_protocol and not auth.priv_key:
                raise ValueError("priv_key required when priv_protocol is set")

            if auth.priv_key and not auth.priv_protocol:
                raise ValueError("priv_protocol required when priv_key is set")

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
            f"Starting SNMP trap receiver on "
            f"{self.authentication_config.listen_address}:{self.authentication_config.port}"
        )

        self.running = True
        self.trap_thread = threading.Thread(
            target=self._start_trap_receiver,
            daemon=True
        )
        self.trap_thread.start()
        self.logger.info(
            f"SNMP trap receiver thread started successfully on "
            f"{self.authentication_config.listen_address}:{self.authentication_config.port}"
        )
        return {"status": "SNMP trap receiver started"}

    def _start_trap_receiver(self):
        """Start the SNMP trap receiver in a separate thread."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop

            self.snmp_engine = engine.SnmpEngine()

            config.addTransport(
                self.snmp_engine,
                udp.domainName,
                udp.UdpTransport().openServerMode(
                    (self.authentication_config.listen_address, self.authentication_config.port)
                )
            )

            config.addV1System(
                self.snmp_engine,
                'keep-snmp-security-domain',
                self.authentication_config.community or "public"
            )

            # Add v3 ONLY if configured
            auth = self.authentication_config

            if auth.username:
                auth_map = {
                    "MD5": usmHMACMD5AuthProtocol,
                    "SHA": usmHMACSHAAuthProtocol,
                }
                priv_map = {
                    "DES": usmDESPrivProtocol,
                    "AES": usmAesCfb128Protocol,
                }

                auth_proto = auth_map.get(auth.auth_protocol, usmNoAuthProtocol)
                priv_proto = priv_map.get(auth.priv_protocol, usmNoPrivProtocol)

                if auth.auth_protocol and auth.priv_protocol:
                    security_level = 'authPriv'
                elif auth.auth_protocol:
                    security_level = 'authNoPriv'
                else:
                    security_level = 'noAuthNoPriv'

                try:
                    # Register under local engine with passphrase
                    config.add_v3_user(
                        self.snmp_engine,
                        auth.username,
                        auth_proto,
                        auth.auth_key,
                        priv_proto,
                        auth.priv_key,
                    )
                    self.logger.info("addV3User local engine success")

                    # Register under wildcard with passphrase
                    # When trap arrives, dynamically re-register under sender's real engine ID
                    config.add_v3_user(
                        self.snmp_engine,
                        auth.username,
                        auth_proto,
                        auth.auth_key,
                        priv_proto,
                        auth.priv_key,
                        securityEngineId=rfc1902.OctetString(hexValue="0000000000"),
                    )
                    self.logger.info(" addV3User wildcard engine success")

                    config.addVacmUser(
                        self.snmp_engine,
                        3,
                        auth.username,
                        security_level,
                        (1, 3, 6),
                        (1, 3, 6),
                        (1, 3, 6),
                        contextName=b''
                    )

                    # Patch USM to auto-register user under sender's engine ID on first trap
                    _auth_username = auth.username
                    _auth_key = auth.auth_key
                    _priv_key = auth.priv_key
                    _auth_proto = auth_proto
                    _priv_proto = priv_proto
                    _snmp_engine = self.snmp_engine
                    _registered_engine_ids = set()
                    _logger = self.logger

                    usm = _snmp_engine.security_models[
                        list(_snmp_engine.security_models.keys())[0]
                        if not hasattr(_snmp_engine, 'security_models')
                        else 3
                    ]

                    # Get the actual USM security model
                    from pysnmp.proto.secmod.rfc3414 import service as usm_service
                    original_process = None
                    for model_id, model in _snmp_engine.security_models.items():
                        if isinstance(model, usm_service.SnmpUSMSecurityModel):
                            original_process = model.process_incoming_message
                            
                            def patched_process(snmpEngine, messageProcessingModel, maxMessageSize,
                                              securityParameters, securityModel, securityLevel,
                                              wholeMsg, msg, _original=original_process):
                                try:
                                    return _original(snmpEngine, messageProcessingModel, maxMessageSize,
                                                    securityParameters, securityModel, securityLevel,
                                                    wholeMsg, msg)
                                except Exception as e:
                                    # Extract sender engine ID from security parameters
                                    try:
                                        from pysnmp.proto.secmod.rfc3414.service import UsmSecurityParameters
                                        params = UsmSecurityParameters()
                                        params.setComponentByPosition(0)
                                        decoded, _ = pyasn1.codec.ber.decoder.decode(
                                            securityParameters, asn1Spec=params
                                        )
                                        sender_engine_id = decoded.getComponentByPosition(0)
                                        engine_id_hex = sender_engine_id.prettyPrint().replace('0x', '')
                                        
                                        if engine_id_hex not in _registered_engine_ids:
                                            _logger.info(f" Auto-registering user under engine ID: {engine_id_hex}")
                                            config.add_v3_user(
                                                _snmp_engine,
                                                _auth_username,
                                                _auth_proto,
                                                _auth_key,
                                                _priv_proto,
                                                _priv_key,
                                                securityEngineId=rfc1902.OctetString(
                                                    bytes.fromhex(engine_id_hex)
                                                ),
                                            )
                                            _registered_engine_ids.add(engine_id_hex)
                                            # Retry
                                            return _original(snmpEngine, messageProcessingModel, maxMessageSize,
                                                          securityParameters, securityModel, securityLevel,
                                                          wholeMsg, msg)
                                    except Exception as inner_e:
                                        _logger.error(f" Auto-register failed: {inner_e}")
                                    raise

                            model.process_incoming_message = patched_process
                            _logger.info(" USM process_incoming_message patched for dynamic engine ID registration")
                            break

                    self.logger.info(
                        f"SNMPv3 user '{auth.username}' registered successfully "
                        f"with security level '{security_level}'"
                    )
                except Exception as e:
                    self.logger.error(f"Failed to register SNMPv3 user: {e}")
                    self.logger.error(traceback.format_exc())
                    

            ntfrcv.NotificationReceiver(self.snmp_engine, self._handle_trap)

            self.logger.info("SNMP trap receiver is ready to receive traps")

            self.snmp_engine.transportDispatcher.jobStarted(1)

            self.snmp_engine.transportDispatcher.runDispatcher()

        except Exception as e:
            self.logger.error(f"Error starting SNMP trap receiver: {e}")
            self.logger.error(traceback.format_exc())
            self.running = False
        finally:
            # Clean up the loop reference when the thread exits
            self._loop = None

    def _handle_trap(self, snmp_engine, state_reference, context_engine_id, context_name, var_binds, cb_ctx):
        """Handle incoming SNMP traps."""
        try:
            self.logger.debug("Received SNMP trap")

            trap_data = {}
            trap_oids = []

            if not var_binds:
                self.logger.warning("Received SNMP trap with no variable bindings")
                return

            for oid, val in var_binds:
                try:
                    oid_str = str(oid)
                    trap_oids.append(oid_str)

                    try:
                        val_str = val.prettyPrint()
                    except Exception:
                        val_str = str(val)

                    trap_data[oid_str] = val_str

                except Exception as val_err:
                    self.logger.error(f"Error processing OID value: {str(val_err)}")

            severity = self._determine_severity(trap_oids, trap_data)

            raw_fingerprint = "-".join([
                "-".join(trap_oids),                          
                str(context_engine_id),                        
                datetime.utcnow().strftime("%Y%m%d%H%M%S%f"), 
            ])
            fingerprint = hashlib.md5(raw_fingerprint.encode()).hexdigest()

            alert_title = "SNMP Trap Received"
            if '1.3.6.1.6.3.1.1.4.1.0' in trap_data:
                trap_type_oid = trap_data['1.3.6.1.6.3.1.1.4.1.0']
                alert_title = f"SNMP Trap: {trap_type_oid}"

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
        """Determine alert severity using 4-level priority chain."""

        # Priority 1 — User-provided manual JSON mapping (highest priority)
        if self._severity_mapping:
            for pattern, severity_str in self._severity_mapping.items():
                for oid in oids:
                    if pattern in oid:
                        return self._parse_severity(severity_str)
                for value in data.values():
                    if pattern in value:
                        return self._parse_severity(severity_str)

        # Priority 2 — Built-in OID map (standard well-known trap OIDs)
        for oid in oids:
            for known_oid, severity in self.DEFAULT_OID_SEVERITY_MAP.items():
                if known_oid in oid:
                    self.logger.info(f"Severity '{severity.value}' matched OID pattern '{known_oid}'")
                    return severity

        # Priority 3 — Auto-detect from trap value keywords
        for val in data.values():
            val_lower = val.lower()
            for severity, keywords in self.SEVERITY_KEYWORDS.items():
                if any(kw in val_lower for kw in keywords):
                    self.logger.info(f"Severity '{severity.value}' auto-detected from value '{val}'")
                    return severity

        # Priority 4 — Default fallback
        return AlertSeverity.WARNING

    def _parse_severity(self, severity_str: str) -> AlertSeverity:
        """Parse severity string into AlertSeverity enum value."""
        severity_map = {
            "INFO": AlertSeverity.INFO,
            "WARNING": AlertSeverity.WARNING,
            "ERROR": AlertSeverity.HIGH,
            "CRITICAL": AlertSeverity.CRITICAL,
        }
        return severity_map.get(severity_str, AlertSeverity.WARNING)

    def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get logs from the provider."""
        logs = []

        debug_info = self.debug_info()
        logs.append({
            "message": "SNMP Provider Debug Information",
            "timestamp": datetime.utcnow().isoformat(),
            "level": "INFO",
            "details": debug_info
        })

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

        if self.running:
            logs.append({
                "message": f"SNMP trap receiver is running on "
                           f"{self.authentication_config.listen_address}:{self.authentication_config.port}",
                "timestamp": datetime.utcnow().isoformat(),
                "level": "INFO",
                "details": {
                    "community": "***" if self.authentication_config.community else "Not set"
                }
            })

            if self._severity_mapping:
                logs.append({
                    "message": "SNMP trap severity mapping configured",
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": "INFO",
                    "details": {"severity_mapping": dict(self._severity_mapping)}
                })
            else:
                logs.append({
                    "message": "No SNMP trap severity mapping configured",
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": "WARNING",
                    "details": {"default_severity": "WARNING"}
                })

        return logs

    def debug_info(self) -> Dict[str, Any]:
        """Get debugging information about the SNMP provider."""
        if self.running:
            port_test = {
                "status": "In use by receiver",
                "message": "Port is actively bound by the SNMP trap receiver",
                "port": self.authentication_config.port,
            }
        else:
            port_test = {"status": "Unknown", "message": "", "port": self.authentication_config.port}
            try:
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                test_socket.bind((self.authentication_config.listen_address, self.authentication_config.port))
                test_socket.close()
                port_test = {
                    "status": "Available",
                    "message": "Port is available and ready to bind",
                    "port": self.authentication_config.port,
                }
            except Exception as e:
                port_test = {
                    "status": "Failed",
                    "message": str(e),
                    "port": self.authentication_config.port,
                    "reason": f"Port {self.authentication_config.port} might already be in use or requires elevated privileges",
                }

        engine_info = {"status": "Not initialized"}
        if self.snmp_engine:
            try:
                engine_info = {
                    "status": "Initialized",
                    "transport_dispatcher_jobs": getattr(
                        self.snmp_engine.transportDispatcher, "jobsAmount", "Unknown"
                    ),
                    "snmp_engine_id": str(
                        getattr(self.snmp_engine, "snmpEngineID", b"Not available")
                    ),
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
                "has_severity_mapping": bool(self._severity_mapping),
            },
            "port_test": port_test,
            "snmp_engine": engine_info,
            "thread_active": bool(self.trap_thread and self.trap_thread.is_alive()),
        }

    def validate_scopes(self) -> Dict[str, Union[bool, str]]:
        """Validate provider scopes."""
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            test_socket.bind((self.authentication_config.listen_address, self.authentication_config.port))
            test_socket.close()
            return {"receive_traps": True}
        except Exception as e:
            return {
                "receive_traps": (
                    f"Failed to bind to "
                    f"{self.authentication_config.listen_address}:{self.authentication_config.port}: {str(e)}"
                )
            }

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
    
    @staticmethod
    def _format_alert(event: dict, provider_instance=None):
        from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
        return AlertDto(
            id=event.get("fingerprint", str(uuid.uuid4())),
            name=event.get("title", "SNMP Trap"),
            description=event.get("description", ""),
            severity=AlertSeverity(event.get("severity", "warning")),
            status=AlertStatus.FIRING,
            source=["snmp"],
            fingerprint=event.get("fingerprint"),
        )

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
                self.logger.info(
                    f"SNMP engine transport dispatcher stopped, "
                    f"port {self.authentication_config.port} released"
                )
            except Exception as e:
                self.logger.error(f"Error during SNMP engine cleanup: {e}")
            finally:
                self.snmp_engine = None

        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

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

    def status(self) -> dict:
        return {
            "status": "running" if self.running else "stopped",
            "error": ""
        }


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")
    config = ProviderConfig(
        authentication={
            "listen_address": "0.0.0.0",
            "port": 162,
            "community": "public",
        }
    )
    provider = SnmpProvider(context_manager, "snmp-test", config)
    provider.start_consume()
    print("SNMP provider started, listening for traps...")