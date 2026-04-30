"""
SNMP Provider allows Keep to monitor network devices via the SNMP protocol,
supporting SNMP GET/WALK operations and receiving SNMP traps.
"""

import dataclasses
import logging
from datetime import datetime, timezone
from typing import Optional

import pydantic
from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
    nextCmd,
)

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP authentication configuration.
    """

    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SNMP Device Host",
            "hint": "192.168.1.1 or snmp.example.com",
            "sensitive": False,
        }
    )
    port: int = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMP Device Port",
            "hint": "161",
            "sensitive": False,
        },
        default=161,
    )
    community: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMP Community String (v1/v2c)",
            "hint": "public",
            "sensitive": True,
        },
        default="public",
    )
    version: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMP Version (1, 2c, or 3)",
            "hint": "2c",
            "sensitive": False,
        },
        default="2c",
    )
    security_name: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 Security Name (username)",
            "hint": "snmpuser",
            "sensitive": False,
        },
        default="",
    )
    auth_protocol: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 Authentication Protocol (MD5 or SHA)",
            "hint": "SHA",
            "sensitive": False,
        },
        default="",
    )
    auth_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 Authentication Key",
            "hint": "authpassphrase",
            "sensitive": True,
        },
        default="",
    )
    priv_protocol: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 Privacy Protocol (DES, AES128, AES192, AES256)",
            "hint": "AES128",
            "sensitive": False,
        },
        default="",
    )
    priv_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SNMPv3 Privacy Key",
            "hint": "privpassphrase",
            "sensitive": True,
        },
        default="",
    )


class SnmpProvider(BaseProvider):
    """
    Query SNMP devices and receive SNMP traps into Keep.
    """

    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_TAGS = ["networking", "monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_device",
            description="Read device information via SNMP",
            mandatory=True,
            mandatory_for_webhook=False,
            documentation_url="https://docs.pysnmp.readthedocs.io/",
        ),
    ]
    PROVIDER_METHODS = [
        ProviderMethod(
            name="get",
            description="SNMP GET - Query a single OID",
            params=[
                ProviderMethod.Param(
                    name="oid", description="The OID to query", type="string", required=True
                ),
            ],
        ),
        ProviderMethod(
            name="walk",
            description="SNMP WALK - Walk an OID subtree",
            params=[
                ProviderMethod.Param(
                    name="oid",
                    description="The starting OID to walk",
                    type="string",
                    required=True,
                ),
            ],
        ),
    ]

    SEVERITY_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "major": AlertSeverity.HIGH,
        "minor": AlertSeverity.WARNING,
        "warning": AlertSeverity.WARNING,
        "normal": AlertSeverity.INFO,
        "info": AlertSeverity.INFO,
        "indeterminate": AlertSeverity.INFO,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.host:
            raise ValueError("SNMP host is required")

    def dispose(self):
        pass

    def _get_auth(self):
        """Build SNMP authentication object based on version."""
        config = self.authentication_config
        if config.version == "3":
            from pysnmp.hlapi import UsmUserData
            return UsmUserData(
                userName=config.security_name,
                authKey=config.auth_key or None,
                authProtocol=config.auth_protocol or None,
                privKey=config.priv_key or None,
                privProtocol=config.priv_protocol or None,
            )
        else:
            mp_model = 1 if config.version == "2c" else 0
            return CommunityData(config.community, mpModel=mp_model)

    def _get_transport_target(self):
        """Build UDP transport target."""
        config = self.authentication_config
        return UdpTransportTarget(
            (config.host, config.port), timeout=10, retries=3
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate SNMP scopes by performing a test SNMP GET on sysDescr."""
        try:
            results = self._query_impl(oid="1.3.6.1.2.1.1.1.0", method="get")
            if results:
                self.logger.info(
                    "SNMP scope validation successful", extra={"result": results}
                )
                return {"read_device": True}
            return {"read_device": "No response from device"}
        except Exception as e:
            self.logger.warning(
                "SNMP scope validation failed", extra={"error": str(e)}
            )
            return {"read_device": str(e)}

    def _query_impl(self, oid: str, method: str = "get") -> dict:
        """Internal implementation of SNMP query."""
        auth = self._get_auth()
        transport = self._get_transport_target()
        results = {}

        if method.lower() == "get":
            error_indication, error_status, error_index, var_binds = next(
                getCmd(
                    SnmpEngine(),
                    auth,
                    transport,
                    ContextData(),
                    ObjectType(ObjectIdentity(oid)),
                )
            )
            if error_indication:
                raise Exception(f"SNMP Error: {error_indication}")
            elif error_status:
                raise Exception(
                    f"SNMP Status Error: {error_status.prettyPrint()} at "
                    f"{error_index and var_binds[int(error_index) - 1][0] or '?'}"
                )
            else:
                for var_bind in var_binds:
                    results[str(var_bind[0])] = str(var_bind[1])

        elif method.lower() == "walk":
            for (
                error_indication,
                error_status,
                error_index,
                var_binds,
            ) in nextCmd(
                SnmpEngine(),
                auth,
                transport,
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False,
            ):
                if error_indication:
                    raise Exception(f"SNMP Error: {error_indication}")
                elif error_status:
                    raise Exception(
                        f"SNMP Status Error: {error_status.prettyPrint()} at "
                        f"{error_index and var_binds[int(error_index) - 1][0] or '?'}"
                    )
                else:
                    for var_bind in var_binds:
                        results[str(var_bind[0])] = str(var_bind[1])

        return results

    def _query(self, oid: str, method: str = "get", **kwargs) -> dict:
        """
        Query an SNMP device using GET or WALK.

        Args:
            oid (str): The OID to query.
            method (str): The method to use - "get" or "walk".

        Returns:
            dict: The result of the query as {oid: value}.
        """
        self.logger.info(
            "Querying SNMP device %s for OID %s using %s",
            self.authentication_config.host,
            oid,
            method,
        )
        return self._query_impl(oid, method)

    def pull_alerts(self):
        """
        Pull alerts from SNMP device by polling key system OIDs.
        Polls IF-MIB interfaces, system status, and common alert OIDs.
        Returns only non-normal statuses as alerts.
        """
        alerts = []
        try:
            # Walk IF-MIB to get interface statuses
            try:
                if_status = self._query_impl("1.3.6.1.2.1.2.2.1.8", "walk")
                self.logger.info("Found %d interface status entries", len(if_status))
            except Exception as e:
                self.logger.warning("Failed to poll IF-MIB: %s", e)
                if_status = {}

            status_map = {
                "1": AlertStatus.RESOLVED,
                "2": AlertStatus.FIRING,
                "3": AlertStatus.FIRING,
                "4": AlertStatus.FIRING,
                "5": AlertStatus.ACKNOWLEDGED,
                "6": AlertStatus.RESOLVED,
                "7": AlertStatus.FIRING,
            }

            try:
                if_descr = self._query_impl("1.3.6.1.2.1.2.2.1.2", "walk")
            except Exception:
                if_descr = {}

            try:
                if_type = self._query_impl("1.3.6.1.2.1.2.2.1.3", "walk")
            except Exception:
                if_type = {}

            try:
                if_speed = self._query_impl("1.3.6.1.2.1.2.2.1.5", "walk")
            except Exception:
                if_speed = {}

            for oid_str, status_val in if_status.items():
                parts = oid_str.rsplit(".", 1)
                if len(parts) != 2:
                    continue
                oid_base, idx = parts
                idx = idx.strip()

                if status_val not in ("1",):
                    descr = if_descr.get(f"{oid_base.replace('1.8', '1.2')}.{idx}", f"Interface {idx}")
                    iface_type = if_type.get(f"{oid_base.replace('1.8', '1.3')}.{idx}", "")
                    speed = if_speed.get(f"{oid_base.replace('1.8', '1.5')}.{idx}", "")

                    alert = AlertDto(
                        id=f"{self.authentication_config.host}-if-{idx}",
                        name=f"Interface Down: {descr}",
                        description=f"Interface {idx} ({iface_type}) is down. Speed: {speed}",
                        severity=AlertSeverity.CRITICAL,
                        status=status_map.get(status_val, AlertStatus.FIRING),
                        host=self.authentication_config.host,
                        source=["snmp"],
                        lastReceived=datetime.now(timezone.utc).isoformat(),
                    )
                    alerts.append(alert)
                    self.logger.info("Interface alert: %s - status %s", descr, status_val)

            # Poll HOST-RESOURCES-MIB
            try:
                hr_status = self._query_impl("1.3.6.1.2.1.25.3.2.1.5", "walk")
                hr_descr = self._query_impl("1.3.6.1.2.1.25.3.2.1.3", "walk")

                for oid_str, status_val in hr_status.items():
                    if status_val not in ("1", "2"):
                        idx = oid_str.rsplit(".", 1)[-1].strip()
                        descr = hr_descr.get(f"1.3.6.1.2.1.25.3.2.1.3.{idx}", f"Device {idx}")
                        alert = AlertDto(
                            id=f"{self.authentication_config.host}-hr-{idx}",
                            name=f"Device Alert: {descr}",
                            description=f"Host resource device status: {status_val}",
                            severity=AlertSeverity.WARNING,
                            status=AlertStatus.FIRING,
                            host=self.authentication_config.host,
                            source=["snmp"],
                            lastReceived=datetime.now(timezone.utc).isoformat(),
                        )
                        alerts.append(alert)
            except Exception as e:
                self.logger.warning("Failed to poll HOST-RESOURCES-MIB: %s", e)

        except Exception as e:
            self.logger.exception("Error pulling SNMP alerts: %s", e)

        self.logger.info("Pulled %d alerts from SNMP device", len(alerts))
        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format incoming SNMP trap data into an AlertDto.
        Handles SNMP trap v1 and v2c formats.
        """
        oid = event.get("oid", event.get("SNMPv2-SMI::snmpTrapOID.0", ""))
        var_binds = event.get("var_binds", event)

        name = event.get("name", f"SNMP Trap: {oid}")
        description = event.get("description", "")
        severity_str = event.get("severity", "").lower()

        severity = SnmpProvider.SEVERITY_MAP.get(severity_str, AlertSeverity.INFO)

        source_host = event.get("host", "")
        if not source_host and isinstance(var_binds, dict):
            source_host = (
                var_binds.get("1.3.6.1.6.3.18.1.3.0", "")
                or var_binds.get("SNMP-COMMUNITY-MIB::snmpTrapAddress.0", "")
            )

        alert = AlertDto(
            id=event.get("id", oid),
            name=name,
            description=description,
            severity=severity,
            status=AlertStatus.FIRING,
            host=source_host,
            source=["snmp"],
            lastReceived=datetime.now(timezone.utc).isoformat(),
            **{
                k: v
                for k, v in event.items()
                if k not in ("id", "name", "description", "severity", "host")
            },
        )
        return alert


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")
    config = ProviderConfig(
        description="SNMP Provider",
        authentication={"host": "localhost", "community": "public", "version": "2c"},
    )
    provider = SnmpProvider(context_manager, "snmp", config)
    provider.validate_config()
    print("SNMP Provider Initialized")
    try:
        result = provider._query("1.3.6.1.2.1.1.1.0", "get")
        print(f"SNMP GET result: {result}")
    except Exception as e:
        print(f"SNMP GET failed (expected if no device): {e}")
