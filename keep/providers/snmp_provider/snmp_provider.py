"""
SNMP Provider for Keep.

This provider supports both sending SNMP traps and receiving SNMP trap events
via webhook from external SNMP trap receivers.
"""

import dataclasses
import json

import pydantic
from pydantic.dataclasses import dataclass

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.models.provider_method import ProviderMethod
from typing import Literal


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP Provider authentication configuration.
    """

    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SNMP agent host to send traps to",
            "hint": "IP address or hostname of the SNMP agent",
        }
    )
    oid: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "OID for SNMP trap",
            "hint": "Object Identifier to include in traps",
        }
    )
    port: int = dataclasses.field(
        default=162,
        metadata={
            "required": False,
            "description": "SNMP agent port",
            "hint": "Default is 162 (SNMP trap port)",
            "type": "number",
        },
    )
    community: str | None = dataclasses.field(
        default="public",
        metadata={
            "required": False,
            "description": "SNMP community string",
            "sensitive": True,
        },
    )


class SnmpProvider(BaseProvider):
    """
    SNMP Provider for Keep.

    Supports both sending SNMP traps to external agents and receiving
    SNMP trap events via webhook from SNMP trap collectors/receivers.
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    webhook_description = "Configure your SNMP trap receiver (e.g., Zabbix, Nagios, SNMPTT) to send traps to Keep. Use the webhook URL below to receive SNMP traps as alerts in Keep."
    webhook_template = ""

    PROVIDER_CATEGORY: list[
        Literal[
            "AI",
            "Monitoring",
            "Incident Management",
            "Cloud Infrastructure",
            "Ticketing",
            "Identity",
            "Developer Tools",
            "Database",
            "Identity and Access Management",
            "Security",
            "Collaboration",
            "Organizational Tools",
            "CRM",
            "Queues",
            "Orchestration",
            "Others",
        ]
    ] = ["Monitoring"]
    PROVIDER_TAGS: list[
        Literal[
            "alert", "ticketing", "messaging", "data", "queue", "topology", "incident"
        ]
    ] = ["alert", "messaging"]
    FINGERPRINT_FIELDS: list[str] = ["oid", "message"]
    PROVIDER_METHODS: list[ProviderMethod] = []

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    @staticmethod
    def get_alert_schema() -> dict:
        pass

    def _notify(
        self,
        message: str = "",
        **kwargs,
    ):
        """
        Sends an SNMP trap.

        Note: Requires pysnmp library to be installed.
        For receiving traps via webhook, pysnmp is not required.

        Args:
            message (str): The message to be sent as part of the SNMP trap.
            **kwargs: Additional parameters for the SNMP trap.
        """
        try:
            from pysnmp.hlapi import (
                UdpTransportTarget,
                CommunityData,
                CommandGenerator,
                OctetString,
                ObjectIdentity,
                NotificationType,
                sendNotification,
                ContextData,
            )
        except ImportError:
            self.logger.warning(
                "pysnmp library not installed. SNMP trap sending is disabled. "
                "Install pysnmp to enable: pip install pysnmp"
            )
            self.logger.info(
                "SNMP trap (simulated)", extra={"message": message, "kwargs": kwargs}
            )
            return "SNMP trap simulated (pysnmp not installed)"
        self.logger.info(
            "Sending SNMP trap", extra={"message": message, "kwargs": kwargs}
        )

        try:
            # Extract configuration
            host = self.authentication_config.host
            port = self.authentication_config.port
            community = self.authentication_config.community
            oid = self.authentication_config.oid

            # Prepare CommandGenerator
            cmdGen = CommandGenerator()

            # Prepare PDU
            errorIndication, errorStatus, errorIndex, varBinds = sendNotification(
                cmdGen,
                CommunityData(community),
                UdpTransportTarget((host, port)),
                ContextData(),
                "trap",
                NotificationType(
                    ObjectIdentity(oid),
                ).addVarBinds(
                    (ObjectIdentity("1.3.6.1.6.3.1.1.4.1.0"), ObjectIdentity(oid)),
                    (ObjectIdentity("1.3.6.1.2.1.1.0"), OctetString(message)),
                ),
            )

            if errorIndication:
                self.logger.error(f"Error sending SNMP trap: {errorIndication}")
                raise Exception(f"Error sending SNMP trap: {errorIndication}")
            else:
                if errorStatus:
                    self.logger.error(
                        f"Error sending SNMP trap: {errorStatus} at {errorIndex and varBinds[int(errorIndex) - 1][0] or '?'}"
                    )
                    raise Exception(
                        f"Error sending SNMP trap: {errorStatus} at {errorIndex and varBinds[int(errorIndex) - 1][0] or '?'}"
                    )
                else:
                    self.logger.info("SNMP trap sent successfully.")
                    return "SNMP trap sent successfully"

        except Exception as e:
            self.logger.error(f"Failed to send SNMP trap: {e}")
            raise

    def _query(self, **kwargs: dict):
        """
        Query the SNMP agent (not implemented for now).
        """
        raise NotImplementedError("SNMP provider does not support querying yet.")

    @staticmethod
    def parse_event_raw_body(raw_body: bytes | dict) -> dict:
        """
        Parse the raw body of an incoming SNMP trap event.

        Expected JSON format:
        {
            "oid": "1.3.6.1.4.1.12345.1.2.3",
            "message": "CPU usage is high",
            "source": "server01",
            "severity": "critical"
        }

        Args:
            raw_body (bytes | dict): The raw body of the incoming event

        Returns:
            dict: Parsed event dict
        """
        if isinstance(raw_body, dict):
            return raw_body
        return json.loads(raw_body)

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "SnmpProvider" = None
    ) -> AlertDto:
        """
        Format an SNMP trap event into an AlertDto.

        Args:
            event (dict): The parsed SNMP trap event
            provider_instance: The provider instance (optional)

        Returns:
            AlertDto: Formatted alert
        """
        severity_map = {
            "critical": AlertSeverity.CRITICAL,
            "error": AlertSeverity.HIGH,
            "high": AlertSeverity.HIGH,
            "warning": AlertSeverity.WARNING,
            "medium": AlertSeverity.MEDIUM,
            "low": AlertSeverity.LOW,
            "info": AlertSeverity.INFO,
        }

        severity_str = event.get("severity", "info").lower()
        severity = severity_map.get(severity_str, AlertSeverity.INFO)

        name = event.get("message", event.get("oid", "SNMP Trap"))
        source = event.get("source", "snmp")
        if isinstance(source, str):
            source = [source]

        return AlertDto(
            name=name,
            status=AlertStatus.FIRING,
            severity=severity,
            lastReceived=event.get("timestamp", ""),
            description=event.get("message", ""),
            source=source,
            message=event.get("message", ""),
            fingerprint=event.get("oid", event.get("message", "")),
            **event,
        )
