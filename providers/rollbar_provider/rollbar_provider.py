"""
RollbarProvider is a class that allows to install webhooks and get alerts in Rollbar.
"""

import dataclasses
import datetime
from typing import List
from urllib.parse import urljoin

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class RollbarProviderAuthConfig:
    """
    RollbarProviderAuthConfig is a class that allows to authenticate in Rollbar.
    """

    rollbarAccessToken: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Project Access Token",
            "sensitive": True,
        },
        default=None,
    )


class RollbarProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Rollbar"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is Authenticated",
        ),
    ]

    SEVERITIES_MAP = {
        "warning": AlertSeverity.WARNING,
        "error": AlertSeverity.HIGH,
        "info": AlertSeverity.INFO,
        "critical": AlertSeverity.CRITICAL,
        "debug": AlertSeverity.LOW,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """
        Validate the configuration of the provider.
        """
        self.authentication_config = RollbarProviderAuthConfig(
            **self.config.authentication
        )

    def __get_url(self, path: str):
        """
        Get the URL for the request.
        """
        return urljoin("https://api.rollbar.com/api/1/", path)

    def __get_headers(self):
        """
        Get the headers for the request.
        """
        return {
            "X-Rollbar-Access-Token": self.authentication_config.rollbarAccessToken,
            "accept": "application/json; charset=utf-8",
            "content-type": "application/json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate the scopes of the provider.
        """
        try:
            response = requests.get(
                self.__get_url("items"), headers=self.__get_headers()
            )
            if response.status_code == 200:
                scopes = {"authenticated": True}
            else:
                self.logger.error(
                    "Unable to read projects from Rollbar, statusCode: %s",
                    response.status_code,
                )
                scopes = {
                    "authenticated": f"Unable to read projects from Rollbar, statusCode: {response.status_code}"
                }

        except Exception as e:
            self.logger.error("Error validating scopes for Rollbar: %s", e)
            scopes = {"authenticated": f"Error validating scopes for Rollbar: {e}"}

        return scopes

    def __get_occurences(self) -> List[AlertDto]:
        try:
            response = requests.get(
                self.__get_url("instances"), headers=self.__get_headers()
            )

            if not response.ok:
                self.logger.error(
                    "Failed to get occurrences from Rollbar: %s", response.json()
                )
                raise Exception("Could not get occurrences from Rollbar")

            return [
                AlertDto(
                    id=alert["id"],
                    name=alert["project_id"],
                    environment=alert["data"]["environment"],
                    event_id=alert["data"]["uuid"],
                    language=alert["data"]["language"],
                    message=alert["data"]["body"]["message"]["body"],
                    host=alert["data"]["server"]["host"],
                    pid=alert["data"]["server"]["pid"],
                    severity=RollbarProvider.SEVERITIES_MAP[alert["data"]["level"]],
                    lastReceived=datetime.datetime.fromtimestamp(
                        alert["timestamp"]
                    ).isoformat(),
                )
                for alert in response.json()["result"]["instances"]
            ]

        except Exception as e:
            self.logger.error("Error getting occurrences from Rollbar: %s", e)
            raise Exception(f"Error getting occurrences from Rollbar: {e}")

    def _get_alerts(self) -> List[AlertDto]:
        alerts = []
        try:
            self.logger.info("Collecting alerts (occurrences) from Rollbar")
            occurences_alert = self.__get_occurences()
            alerts.extend(occurences_alert)
        except Exception as e:
            self.logger.error("Error getting occurrences from Rollbar: %s", e)

        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        item_data = event["data"]["item"]
        occurrence_data = event["data"]["occurrence"]
        return AlertDto(
            id=str(item_data["id"]),
            name=event["event_name"],
            severity=RollbarProvider.SEVERITIES_MAP[occurrence_data["level"]],
            lastReceived=datetime.datetime.fromtimestamp(
                item_data["last_occurrence_timestamp"]
            ).isoformat(),
            environment=item_data["environment"],
            service="Rollbar",
            source=[occurrence_data["framework"]],
            url=event["data"]["url"],
            message=occurrence_data["body"]["message"]["body"],
            description=item_data["title"],
            event_id=str(occurrence_data["uuid"]),
            labels={"level": item_data["level"]},
            fingerprint=item_data["hash"],
        )

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        self.logger.info("Setting up webhook for Rollbar")
        self.logger.info("Enabling Webhook in Rollbar")
        try:
            response = requests.put(
                self.__get_url("notifications/webhook"),
                headers=self.__get_headers(),
                json={
                    "enabled": True,
                    "url": f"{keep_api_url}?api_key={api_key}",
                },
            )

            if response.ok:
                response = requests.post(
                    self.__get_url("notifications/webhook/rules"),
                    headers=self.__get_headers(),
                    json={
                        {
                            "trigger": "occurrence",
                        }
                    },
                )
                if response.ok:
                    self.logger.info("Created occurrence rule in Rollbar")
                else:
                    self.logger.error(
                        "Failed to enable webhook in Rollbar: %s", response.json()
                    )
                    raise Exception("Failed to enable webhook in Rollbar")

            self.logger.info("Webhook enabled in Rollbar")
        except Exception as e:
            self.logger.error("Error setting up webhook for Rollbar: %s", e)
            raise Exception(f"Error setting up webhook for Rollbar: {e}")


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    rollbar_host = os.environ.get("ROLLBAR_HOST")

    if rollbar_host is None:
        raise Exception("ROLLBAR_HOST is not set")

    config = ProviderConfig(
        description="Rollbar Provider",
        authentication={
            "rollbarAccessToken": rollbar_host,
        },
    )

    provider = RollbarProvider(
        context_manager,
        provider_id="rollbar",
        config=config,
    )

    provider._get_alerts()
