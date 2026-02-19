"""
UptimeKuma is a class that provides the necessary methods to interact with the UptimeKuma SDK
"""

import dataclasses

import pydantic
from socketio.exceptions import BadNamespaceError
from uptime_kuma_api import UptimeKumaApi

from keep.api.models.alert import AlertDto, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class UptimekumaProviderAuthConfig:
    """
    UptimekumaProviderAuthConfig is a class that holds the authentication information for the UptimekumaProvider.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "UptimeKuma Host URL",
            "sensitive": False,
            "validation": "any_http_url"
        },
    )

    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "UptimeKuma Username",
            "sensitive": False,
        },
    )

    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "UptimeKuma Password",
            "sensitive": True,
        },
    )


class UptimekumaProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "UptimeKuma"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="alerts",
            description="Read alerts from UptimeKuma",
        )
    ]

    STATUS_MAP = {
        # Possible firing
        "down": AlertStatus.FIRING.value,
        "unavailable": AlertStatus.FIRING.value,
        "firing": AlertStatus.FIRING.value,
        "0": AlertStatus.FIRING.value,
        0: AlertStatus.FIRING.value,

        # RESOLVED
        "up": AlertStatus.RESOLVED.value,
        "available": AlertStatus.RESOLVED.value,
        "1": AlertStatus.RESOLVED.value,
        1: AlertStatus.RESOLVED.value,
        "resolved": AlertStatus.RESOLVED.value,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def _get_api(self):
        api = UptimeKumaApi(self.authentication_config.host_url)
        api.login(
            self.authentication_config.username, self.authentication_config.password
        )
        return api

    def dispose(self):
        pass

    def validate_scopes(self):
        """
        Validate that the scopes provided in the config are valid
        """
        api = UptimeKumaApi(self.authentication_config.host_url)
        response = api.login(
            self.authentication_config.username, self.authentication_config.password
        )
        api.disconnect()
        if "token" in response:
            return {"alerts": True}
        return {"alerts": False}

    def validate_config(self):
        self.authentication_config = UptimekumaProviderAuthConfig(
            **self.config.authentication
        )

    def _get_heartbeats(self):
        try:
            api = self._get_api()
            response = api.get_heartbeats()

            length = len(response)

            if length == 0:
                return []

            heartbeats = []

            for key in response:
                heartbeat = response[key][-1]
                monitor_id = heartbeat.get("monitor_id", heartbeat.get("monitorID"))
                try:
                    name = api.get_monitor(monitor_id)["name"]
                except BadNamespaceError: # Most likely connection issues
                    try:
                        api.disconnect()
                    except Exception:
                        pass
                    # Single retry
                    api = self._get_api()
                    name = api.get_monitor(monitor_id)["name"]
            heartbeats.append(
                AlertDto(
                    id=heartbeat["id"],
                    name=name,
                    monitor_id=heartbeat["monitor_id"],
                    description=heartbeat["msg"],
                    status=self.STATUS_MAP.get(heartbeat["status"], "firing"),
                    lastReceived=self._format_datetime(heartbeat["localDateTime"], heartbeat["timezoneOffset"]),
                    ping=heartbeat["ping"],
                    source=["uptimekuma"],
                )
            )
            api.disconnect()
            return heartbeats
        except Exception as e:
            self.logger.error("Error getting heartbeats from UptimeKuma: %s", e)
            raise Exception(f"Error getting heartbeats from UptimeKuma: {e}")

    def _get_alerts(self) -> list[AlertDto]:
        try:
            self.logger.info("Collecting alerts (heartbeats) from UptimeKuma")
            alerts = self._get_heartbeats()
            return alerts
        except Exception as e:
            self.logger.error("Error getting alerts from UptimeKuma: %s", e)
            raise Exception(f"Error getting alerts from UptimeKuma: {e}")


    @classmethod
    def _format_alert(
        cls, event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        alert = AlertDto(
            id=event["monitor"]["id"],
            name=event["monitor"]["name"],
            monitor_url=event["monitor"]["url"],
            status=cls.STATUS_MAP.get(event["heartbeat"]["status"], "firing"),
            description=event["msg"],
            lastReceived=cls._format_datetime(event["heartbeat"]["localDateTime"], event["heartbeat"]["timezoneOffset"]),
            msg=event["heartbeat"]["msg"],
            source=["uptimekuma"],
        )

        return alert

    @staticmethod
    def _format_datetime(dt, offset):
        return dt + offset

if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    uptimekuma_host = os.environ.get("UPTIMEKUMA_HOST")
    uptimekuma_username = os.environ.get("UPTIMEKUMA_USERNAME")
    uptimekuma_password = os.environ.get("UPTIMEKUMA_PASSWORD")

    if uptimekuma_host is None:
        raise Exception("UPTIMEKUMA_HOST is required")
    if uptimekuma_username is None:
        raise Exception("UPTIMEKUMA_USERNAME is required")
    if uptimekuma_password is None:
        raise Exception("UPTIMEKUMA_PASSWORD is required")

    config = ProviderConfig(
        description="UptimeKuma Provider",
        authentication={
            "host_url": uptimekuma_host,
            "username": uptimekuma_username,
            "password": uptimekuma_password,
        },
    )

    provider = UptimekumaProvider(
        context_manager=context_manager,
        provider_id="uptimekuma",
        config=config,
    )

    alerts = provider.get_alerts()
    print(alerts)
    provider.dispose()
