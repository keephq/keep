import asyncio
from typing import Any, Optional
import pydantic
from dataclasses import field
from pysnmp.hlapi import *  # type: ignore
from pysnmp.entity import engine, config  # type: ignore
from pysnmp.entity.rfc3413 import ntfrcv  # type: ignore
from pysnmp.carrier.asyncio.dgram import udp  # type: ignore

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.api.models.alert import AlertSeverity, AlertStatus


@pydantic.dataclasses.dataclass
class SnmpProviderAuthConfig:
    """
    SNMP authentication configuration.
    """

    tags: list[str] = field(default_factory=list)
    port: int = field(
        default=162,
        metadata={
            "required": False,
            "description": "Port to listen for SNMP traps",
            "hint": "Default is 162",
        },
    )
    community: str = field(
        default="public",
        metadata={
            "required": False,
            "description": "SNMP v2c Community String",
            "hint": "Default is public",
        },
    )
    # SNMP v3 auth
    v3_user: Optional[str] = field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMP v3 Security Name",
            "hint": "Username for SNMP v3",
        },
    )
    v3_auth_key: Optional[str] = field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMP v3 Auth Key",
            "sensitive": True,
        },
    )
    v3_priv_key: Optional[str] = field(
        default=None,
        metadata={
            "required": False,
            "description": "SNMP v3 Priv Key",
            "sensitive": True,
        },
    )
    v3_auth_proto: str = field(
        default="sha",
        metadata={
            "required": False,
            "description": "SNMP v3 Auth Protocol",
            "hint": "sha, md5, etc.",
        },
    )
    v3_priv_proto: str = field(
        default="aes",
        metadata={
            "required": False,
            "description": "SNMP v3 Priv Protocol",
            "hint": "aes, des, etc.",
        },
    )


class SnmpProvider(BaseProvider):
    """
    SNMP provider class for receiving traps.
    """

    PROVIDER_DISPLAY_NAME = "SNMP"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert", "topology"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.snmp_engine = engine.SnmpEngine()
        self.consume = False

    def validate_config(self) -> None:
        self.authentication_config = SnmpProviderAuthConfig(
            **self.config.authentication  # type: ignore
        )

    def dispose(self) -> None:
        self.stop_consume()

    def _trap_callback(
        self,
        snmpEngine: Any,
        stateReference: Any,
        contextEngineId: Any,
        contextName: Any,
        varBinds: Any,
        cbCtx: Any,
    ) -> None:
        """
        Callback executed when a trap is received.
        """
        self.logger.info("SNMP Trap received")

        # Extract basic info
        alert_data: dict[str, Any] = {
            "source": ["snmp"],
            "severity": AlertSeverity.INFO,
            "status": AlertStatus.FIRING,
            "description": "",
            "varbinds": {},
        }

        # Trap OID is usually one of the varbinds
        trap_oid = "unknown"
        for name, val in varBinds:
            name_str = str(name)
            val_str = str(val)
            alert_data["varbinds"][name_str] = val_str

            # snmpTrapOID.0 = 1.3.6.1.6.3.1.1.4.1.0
            if "1.3.6.1.6.3.1.1.4.1.0" in name_str:
                trap_oid = val_str

            alert_data["description"] += f"{name_str}: {val_str}\n"

        alert_data["name"] = f"SNMP Trap: {trap_oid}"

        try:
            self._push_alert(alert_data)
        except Exception:
            self.logger.exception("Failed to push SNMP alert to Keep")

    def start_consume(self) -> None:
        """
        Start listening for SNMP traps.
        """
        self.consume = True
        self.logger.info(
            f"Starting SNMP Trap listener on port {self.authentication_config.port}"
        )

        # 1. Setup SNMP v2c Community
        config.addV1System(
            self.snmp_engine, "keep-area", self.authentication_config.community
        )

        # 2. Setup SNMP v3 User (if configured)
        if self.authentication_config.v3_user:
            auth_proto = (
                config.usmHMACSHAAuthProtocol
                if self.authentication_config.v3_auth_proto.lower() == "sha"
                else config.usmHMACMD5AuthProtocol
            )
            priv_proto = (
                config.usmAesCfb128Protocol
                if self.authentication_config.v3_priv_proto.lower() == "aes"
                else config.usmDesPrivProtocol
            )

            config.addV3User(
                self.snmp_engine,
                self.authentication_config.v3_user,
                auth_proto,
                self.authentication_config.v3_auth_key,
                priv_proto,
                self.authentication_config.v3_priv_key,
            )

        # 3. Transport Setup
        config.addTransport(
            self.snmp_engine,
            udp.domainName,
            udp.UdpAsyncioTransport().openServerMode(
                ("0.0.0.0", self.authentication_config.port)
            ),
        )

        # 4. Register Notification Receiver
        ntfrcv.NotificationReceiver(self.snmp_engine, self._trap_callback)

        # 5. Run the background loop
        self.logger.info("SNMP listener active")
        try:
            # Thread-safe event loop management for Python 3.12+
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            async def listen() -> None:
                while self.consume:
                    await asyncio.sleep(0.1)  # Faster polling for stop signal

            if loop.is_running():
                # If we're in a thread with a running loop (like some test runners)
                asyncio.run_coroutine_threadsafe(listen(), loop)
            else:
                loop.run_until_complete(listen())
        except Exception:
            self.logger.exception("Error in SNMP listener loop")
        finally:
            self.logger.info("SNMP listener stopped")

    def stop_consume(self) -> None:
        self.consume = False
        # Unsubscribe/close transport if needed
        # self.snmp_engine.transportDispatcher.closeDispatcher() - usually handles it
