"""
SumoLogic Provider is a class that allows to install webhooks in SumoLogic.
"""

import dataclasses
from datetime import datetime
from pathlib import Path
from typing import List
from urllib.parse import urlencode, urljoin, urlparse

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


class ResourceAlreadyExists(Exception):
    def __init__(self, *args):
        super().__init__(*args)


@pydantic.dataclasses.dataclass
class SumologicProviderAuthConfig:
    """
    SumoLogic authentication configuration.
    """

    sumoAccessId: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SumoLogic Access ID",
            "hint": "Your AccessID",
        },
    )
    sumoAccessKey: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SumoLogic Access Key",
            "hint": "SumoLogic Access Key ",
            "sensitive": True,
        },
    )

    deployment: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Deployment Region",
            "hint": "Your deployment Region: AU | CA | DE | EU | FED | IN | JP | KR | US1 | US2",
        },
    )


class SumologicProvider(BaseProvider):
    """Install Webhooks and receive alerts from SumoLogic."""

    PROVIDER_DISPLAY_NAME = "SumoLogic"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is Authorized",
            mandatory=True,
            mandatory_for_webhook=True,
            alias="Rules Reader",
        ),
        ProviderScope(
            name="authorized",
            description="Required privileges",
            mandatory=True,
            mandatory_for_webhook=True,
            alias="Rules Reader",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for SumoLogic provider.

        """
        self.authentication_config = SumologicProviderAuthConfig(
            **self.config.authentication
        )

    def __get_headers(self):
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def __get_url(self, paths: List[str] = [], query_params: dict = None, **kwargs):
        """
        Helper method to build the url for SumoLogic api requests.

        Example:

        paths = ["issue", "createmeta"]
        query_params = {"projectKeys": "key1"}
        url = __get_url("test", paths, query_params)
        # url = https://api.sumologic.com/api/v1/issue/createmeta?projectKeys=key1
        """
        if self.authentication_config.deployment.lower() != "us1":
            host = f"https://api.{self.authentication_config.deployment.lower()}.sumologic.com/api/v1/"
        else:
            host = "https://api.sumologic.com/api/v1/"
        url = urljoin(
            host,
            "/".join(str(path) for path in paths),
        )

        # add query params
        if query_params:
            url = f"{url}?{urlencode(query_params)}"

        return url

    def validate_scopes(self) -> dict[str, bool | str]:
        perms = {"manageScheduledViews", "manageConnections", "manageUsersAndRoles"}
        self.logger.info("Validating SumoLogic authentication.")
        try:
            account_owner_response = requests.get(
                url=self.__get_url(paths=["account", "accountOwner"]),
                auth=self.__get_auth(),
                headers=self.__get_headers(),
            )

            if account_owner_response.status_code == 200:
                authenticated = True
                user_id = account_owner_response.json()
                self.logger.info(
                    "Successfully retrieved user_id", extra={"user_id": user_id}
                )
            else:
                account_owner_response = account_owner_response.json()
                self.logger.error(
                    "Error while getting UserID",
                    extra={"error": str(account_owner_response)},
                )
                return {
                    "authenticated": str(account_owner_response),
                    "authorized": "Unauthorized",
                }

            self.logger.info("Fetching account info...", extra={"user_id": user_id})
            account_info_response = requests.get(
                url=self.__get_url(paths=["users", user_id]),
                auth=self.__get_auth(),
                headers=self.__get_headers(),
            )

            if account_info_response.status_code == 200:
                role_ids = account_info_response.json()["roleIds"]
                self.logger.info(
                    "Successfully fetched account info", extra={"roles": role_ids}
                )
            else:
                account_info_response = account_info_response.json()
                self.logger.error(
                    "Error while getting account info",
                    extra={"error": str(account_info_response)},
                )
                return {
                    "authenticated": authenticated,
                    "authorized": str(account_info_response),
                }

            # Checking if the required permissions exists
            for role_id in role_ids:
                role_info_response = requests.get(
                    url=self.__get_url(paths=["roles", role_id]),
                    auth=self.__get_auth(),
                    headers=self.__get_headers(),
                )
                if role_info_response.status_code == 200:
                    role_info_response = role_info_response.json()
                    self.logger.info(f"Successfully fetched role: {role_id}")
                    for capability in role_info_response["capabilities"]:
                        if capability in perms:
                            perms.remove(capability)
                else:
                    role_info_response = role_info_response.json()
                    self.logger.error(
                        f"Error while getting role: {role_id}",
                        extra={"error": str(role_info_response)},
                    )
                    return {
                        "authenticated": True,
                        "authorized": str(role_info_response),
                    }
                if len(perms) == 0:
                    self.logger.info("All required perms found, user is authorized :)")
                    return {"authenticated": True, "authorized": True}

        except Exception as e:
            self.logger.error("Error while getting User ID " + str(e))
            return {"authenticated": str(e), "authorized": str(e)}

    def __get_auth(self) -> tuple[str, str]:
        return (
            self.authentication_config.sumoAccessId,
            self.authentication_config.sumoAccessKey,
        )

    def __get_connection_id(self, connection_name: str):
        params = {"limit": 1000}
        while True:
            connections_response = requests.get(
                url=self.__get_url(paths=["connections"]),
                headers=self.__get_headers(),
                params=params,
                auth=self.__get_auth(),
            )
            if connections_response.status_code != 200:
                raise Exception(str(connections_response.json()))
            connections_response = connections_response.json()
            for connection in connections_response["data"]:
                if connection["name"] == connection_name:
                    return connection["id"]

            if connections_response["next"] is None:
                break
            params["token"] = connections_response["next"]
        return None

    def __update_existing_connection(self, connection_id: str, connection_payload):
        self.logger.info(f"Updating the connection: {connection_id}")
        connection_update_response = requests.put(
            url=self.__get_url(paths=["connections", connection_id]),
            headers=self.__get_headers(),
            auth=self.__get_auth(),
            json=connection_payload,
        )
        if connection_update_response.status_code == 200:
            self.logger.info(f"Successfully updated connection: {connection_id}")
            return connection_update_response.json()["id"]
        else:
            connection_update_response = connection_update_response.json()
            self.logger.error(
                f"Error while updating connection: {connection_id}",
                extra={"error": str(connection_update_response)},
            )
            raise Exception(str(connection_update_response))

    def __create_connection(self, connection_payload, connection_name: str):
        self.logger.info("Creating a Webhook connection with Sumo Logic")

        try:
            connection_creation_response = requests.post(
                url=self.__get_url(paths=["connections"]),
                json=connection_payload,
                headers=self.__get_headers(),
                auth=self.__get_auth(),
            )
            if connection_creation_response.status_code == 200:
                self.logger.info("Successfully created Webhook connection")
                return connection_creation_response.json()["id"]
            if connection_creation_response.status_code == 400:
                connection_creation_response = connection_creation_response.json()
                if (
                    connection_creation_response["errors"][0]["code"]
                    == "connection:name_already_exists"
                ):
                    self.logger.info(
                        "Webhook connection already exists, attempting to update it"
                    )
                    connection_id = self.__get_connection_id(
                        connection_name=connection_name
                    )
                    return self.__update_existing_connection(
                        connection_payload=connection_payload,
                        connection_id=connection_id,
                    )

                raise Exception(str(connection_creation_response))
            else:
                connection_creation_response = connection_creation_response.json()
                self.logger.error(
                    "Error while creating webhook connection",
                    extra={"error": str(connection_creation_response)},
                )
                raise Exception(connection_creation_response)
        except Exception as e:
            self.logger.error("Error while creating webhook connection " + str(e))
            raise e

    def __get_monitors_without_keep(self, connection_id: str):
        monitors = []
        params = {"query": "type:monitor"}
        monitors_response = requests.get(
            url=self.__get_url(paths=["monitors", "search"]),
            params=params,
            headers=self.__get_headers(),
            auth=self.__get_auth(),
        )

        if monitors_response.status_code == 200:
            self.logger.info("Successfully fetched all monitors")
            monitors_response = monitors_response.json()
            for monitor in monitors_response:
                print(monitor)
                for notification in monitor["item"]["notifications"]:
                    if notification["notification"]["connectionId"] == connection_id:
                        break
                else:
                    monitors.append(monitor["item"])
            return monitors
        else:
            monitors_response = monitors_response.json()
            self.logger.error(
                "Error while getting monitors", extra=str(monitors_response)
            )
            raise Exception(str(monitors_response))

    def __install_connection_in_monitor(self, monitor, connection_id: str):
        self.logger.info(f"Installing connection to monitor: {monitor['name']}")
        monitor["type"] = "MonitorsLibraryMonitorUpdate"
        triggers = [trigger["triggerType"] for trigger in monitor["triggers"]]
        keep_notification = {
            "notification": {
                "connectionType": "Webhook",
                "connectionId": connection_id,
                "payloadOverride": None,
                "resolutionPayloadOverride": None,
            },
            "runForTriggerTypes": triggers,
        }
        monitor["notifications"].append(keep_notification)
        monitor_update_response = requests.put(
            url=self.__get_url(paths=["monitors", monitor["id"]]),
            headers=self.__get_headers(),
            auth=self.__get_auth(),
            json=monitor,
        )
        if monitor_update_response.status_code == 200:
            self.logger.info(
                f"Successfully installed connection to monitor: {monitor['name']}"
            )
        else:
            raise Exception(str(monitor_update_response.json()))

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        try:
            parsed_url = urlparse(keep_api_url)

            # Extract the query string
            query_params = parsed_url.query

            # Find the provider_id in the query parameters
            # connection_template.json is the payload that will be sent to keep as an event
            provider_id = query_params.split("provider_id=")[-1]
            connection_name = f"KeepHQ-{provider_id}"
            connection_payload = {
                "type": "WebhookDefinition",
                "name": connection_name,
                "description": "A webhook connection that pushes alerts to KeepHQ",
                "url": keep_api_url,
                "headers": [],
                "customHeaders": [{"name": "X-API-KEY", "value": api_key}],
                "defaultPayload": open(
                    rf"{Path(__file__).parent}/connection_template.json"
                ).read(),
                "webhookType": "Webhook",
                "connectionSubtype": "Event",
                "resolutionPayload": open(
                    rf"{Path(__file__).parent}/connection_template.json"
                ).read(),
            }
            # Creating a sumo logic connection
            connection_id = self.__create_connection(
                connection_payload=connection_payload, connection_name=connection_name
            )

            # Monitors
            monitors = self.__get_monitors_without_keep(connection_id=connection_id)

            # Install connections in monitors that don't have keep
            for monitor in monitors:
                self.__install_connection_in_monitor(
                    monitor=monitor, connection_id=connection_id
                )
        except Exception as e:
            raise e

    @staticmethod
    def __extract_severity(severity: str):
        if "critical" in severity.lower():
            return AlertSeverity.CRITICAL
        elif "warning" in severity.lower():
            return AlertSeverity.WARNING
        elif "missing" in severity.lower():
            return AlertSeverity.INFO

    @staticmethod
    def __extract_status(status: str):
        if "resolved" in status.lower():
            return AlertStatus.RESOLVED
        else:
            return AlertStatus.FIRING

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        return AlertDto(
            id=event["id"],
            name=event["name"],
            severity=SumologicProvider.__extract_severity(
                severity=event["triggerType"]
            ),
            fingerprint=event["id"],
            status=SumologicProvider.__extract_status(status=event["triggerType"]),
            lastReceived=datetime.utcfromtimestamp(
                int(event["triggerTimeStart"]) / 1000
            ).isoformat()
            + "Z",
            firingTimeStart=datetime.utcfromtimestamp(
                int(event["triggerTimeStart"]) / 1000
            ).isoformat()
            + "Z",
            description=event["description"],
            url=event["alertResponseUrl"],
            source=["sumologic"],
        )
