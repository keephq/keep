"""
UptimeKuma is a class that provides the necessary methods to interact with the UptimeKuma SDK
"""

import dataclasses

import pydantic
from uptime_kuma_api import UptimeKumaApi

from keep.api.models.alert import AlertDto, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class UptimeKumaProviderAuthConfig:
    """
    UptimeKumaProviderAuthConfig is a class that holds the authentication information for the UptimekumaProvider.
    """

    host_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "UptimeKuma Host URL",
            "sensitive": False,
        },
        default=None,
    )

    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "UptimeKuma Username",
            "sensitive": False,
        },
        default=None,
    )

    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "UptimeKuma Password",
            "sensitive": True,
        },
        default=None,
    )


class UptimeKumaProvider(BaseProvider):
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
        "up": AlertStatus.RESOLVED,
        "down": AlertStatus.FIRING,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

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
        self.authentication_config = UptimeKumaProviderAuthConfig(
            **self.config.authentication
        )
        if self.authentication_config.host_url is None:
            raise ProviderException("UptimeKuma Host URL is required")
        if self.authentication_config.username is None:
            raise ProviderException("UptimeKuma Username is required")
        if self.authentication_config.password is None:
            raise ProviderException("UptimeKuma Password is required")

    def _get_heartbeats(self):
        try:
            api = UptimeKumaApi(self.authentication_config.host_url)
            api.login(
                self.authentication_config.username, self.authentication_config.password
            )
            response = api.get_heartbeats()
            api.disconnect()

            length = len(response)

            if length == 0:
                return []

            for key in response:
                heartbeat = response[key][-1]
                name = api.get_monitor(heartbeat["monitor_id"])["name"]

                return AlertDto(
                    id=heartbeat["id"],
                    name=name,
                    monitor_id=heartbeat["monitor_id"],
                    description=heartbeat["msg"],
                    status=heartbeat["status"].name.lower(),
                    lastReceived=heartbeat["time"],
                    ping=heartbeat["ping"],
                    source=["uptimekuma"],
                )

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

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:

        alert = AlertDto(
            id=event["monitor"]["id"],
            name=event["monitor"]["name"],
            monitor_url=event["monitor"]["url"],
            status=event["heartbeat"]["status"],
            description=event["msg"],
            lastReceived=event["heartbeat"]["localDateTime"],
            msg=event["heartbeat"]["msg"],
            source=["uptimekuma"],
        )

        return alert


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

    provider = UptimeKumaProvider(
        context_manager=context_manager,
        provider_id="uptimekuma",
        config=config,
    )

    alerts = provider.get_alerts()
    print(alerts)
    provider.dispose()
