"""
OpenObserve Provider is a class that allows to install webhooks in OpenObserve.
"""

import dataclasses
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlencode, urljoin

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


class ResourceAlreadyExists(Exception):
    def __init__(self, *args):
        super().__init__(*args)


@pydantic.dataclasses.dataclass
class OpenobserveProviderAuthConfig:
    """
    OpenObserve authentication configuration.
    """

    openObserveUsername: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "OpenObserve Username",
            "hint": "Your Username",
        },
    )
    openObservePassword: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Password",
            "hint": "Password associated with your account",
            "sensitive": True,
        },
    )
    openObserveHost: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "OpenObserve host url || default: localhost",
            "hint": "Eg. localhost",
        },
    )

    openObservePort: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "OpenObserve Host|| default: 5080",
            "hint": "Eg. 5080",
        },
    )
    organisationID: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "OpenObserve organisationID",
            "hint": "default",
        },
    )


class OpenobserveProvider(BaseProvider):
    """Install Webhooks and receive alerts from OpenObserve."""

    PROVIDER_DISPLAY_NAME = "OpenObserve"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is Authorized",
            mandatory=True,
            mandatory_for_webhook=True,
            alias="Rules Reader",
        ),
    ]

    SEVERITIES_MAP = {
        "ERROR": AlertSeverity.CRITICAL,
        "WARN": AlertSeverity.WARNING,
        "INFO": AlertSeverity.INFO,
    }

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
        Validates required configuration for OpenObserve provider.

        """
        self.authentication_config = OpenobserveProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.openObserveHost.startswith(
            "https://"
        ) and not self.authentication_config.openObserveHost.startswith("http://"):
            self.authentication_config.openObserveHost = (
                f"https://{self.authentication_config.openObserveHost}"
            )

    def __get_url(self, paths: List[str] = [], query_params: dict = None, **kwargs):
        """
        Helper method to build the url for OpenObserve api requests.

        Example:

        paths = ["issue", "createmeta"]
        query_params = {"projectKeys": "key1"}
        url = __get_url("test", paths, query_params)

        # url = https://baseballxyz.saas.openobserve.com/rest/api/2/issue/createmeta?projectKeys=key1
        """

        url = urljoin(
            f"{self.authentication_config.openObserveHost}:{self.authentication_config.openObservePort}",
            "/".join(str(path) for path in paths),
        )

        # add query params
        if query_params:
            url = f"{url}?{urlencode(query_params)}"

        return url

    def validate_scopes(self) -> dict[str, bool | str]:
        authenticated = False
        self.logger.info("Validating OpenObserve Scopes")
        try:
            response = requests.post(
                url=self.__get_url(
                    paths=[
                        "auth/login",
                    ]
                ),
                json={
                    "name": self.authentication_config.openObserveUsername,
                    "password": self.authentication_config.openObservePassword,
                },
                timeout=10,
            )
        except Exception as e:
            self.logger.error(
                "Error while validating scopes for OpenObserve",
                extra=e,
            )
            return {"authenticated": str(e)}
        print(
            self.__get_url(
                paths=[
                    "auth/login",
                ]
            )
        )
        if response.ok:
            response = response.json()
            authenticated = response["status"]
        else:
            self.logger.error(
                "Error while validating scopes for OpenObserve",
                extra={"status_code": response.status_code, "error": response.text},
            )

        return {"authenticated": authenticated}

    def __get_auth(self) -> tuple[str, str]:
        return (
            self.authentication_config.openObserveUsername,
            self.authentication_config.openObservePassword,
        )

    def __update_alert_template(self, data):
        res = requests.put(
            url=self.__get_url(
                paths=[
                    f"api/{self.authentication_config.organisationID}/alerts/templates/KeepAlertTemplate"
                ]
            ),
            json=data,
            auth=self.__get_auth(),
        )
        if res.ok:
            res = res.json()
            if res["code"] == 200:
                self.logger.info("Alert template Updated Successfully")
            else:

                self.logger.error(
                    "Failed to update Alert Template",
                    extra={"code": res["code"], "error": res["message"]},
                )
        else:
            self.logger.error(
                "Error while updating Alert Template",
                extra={"status_code": res.status_code, "error": res.text},
            )

    def __create_alert_template(self):

        # This is the template used for creating the alert template in openobserve
        template = open(rf"{Path(__file__).parent}/alerttemplate.json", "rt")
        data = template.read()
        try:
            res = requests.post(
                self.__get_url(
                    paths=[
                        f"api/{self.authentication_config.organisationID}/alerts/templates"
                    ]
                ),
                json={"body": data, "isDefault": False, "name": "KeepAlertTemplate"},
                auth=self.__get_auth(),
            )
            res = res.json()
            if res["code"] == 200:
                self.logger.info("Alert template Successfully Created")

            elif "already exists" in res["message"]:
                self.logger.info(
                    "Alert template creation failed as it already exists",
                    extra={"code": res["code"], "error": res["message"]},
                )
                self.logger.info(
                    "Attempting to Update Alert Template with latest data..."
                )
                self.__update_alert_template(
                    data={"body": data, "isDefault": False, "name": "KeepAlertTemplate"}
                )
            else:
                self.logger.error(
                    "Alert template creation failed",
                    extra={"code": res["code"], "error": res["message"]},
                )

        except Exception as e:
            self.logger.error(
                "Error While making alert Template",
                extra=e,
            )

    def __update_destination(self, keep_api_url: str, api_key: str, data):
        res = requests.put(
            json=data,
            url=self.__get_url(
                paths=[
                    f"api/{self.authentication_config.organisationID}/alerts/destinations/KeepDestination"
                ]
            ),
            auth=self.__get_auth(),
        )
        if res.ok:
            self.logger.info("Destination Successfully Updated")
        else:
            self.logger.error(
                "Error while updating destination",
                extra={"code": res.status_code, "error": res.text},
            )

    def __create_destination(self, keep_api_url: str, api_key: str):
        data = {
            "headers": {
                "X-API-KEY": api_key,
            },
            "method": "post",
            "name": "KeepDestination",
            "template": "KeepAlertTemplate",
            "url": keep_api_url,
        }

        response = requests.post(
            url=self.__get_url(
                paths=[
                    f"api/{self.authentication_config.organisationID}/alerts/destinations"
                ]
            ),
            auth=self.__get_auth(),
            json=data,
        )
        # if response.ok:
        res = response.json()
        if res["code"] == 200:
            self.logger.info("Destination Successfully Created")
        elif "already exists" in res["message"]:
            self.logger.info("Destination creation failed as it already exists")
            self.logger.info("Attempting to Update Destination...")
            self.__update_destination(
                keep_api_url=keep_api_url, api_key=api_key, data=data
            )
        else:
            self.logger.error(
                "Destination creation failed",
                extra={"code": res["code"], "error": res["message"]},
            )

    def __get_all_stream_names(self) -> list[str]:
        names = []
        response = requests.get(
            url=self.__get_url(
                paths=[f"api/{self.authentication_config.organisationID}/streams"]
            ),
            auth=self.__get_auth(),
        )
        res = response.json()
        for stream in res["list"]:
            names.append(stream["name"])
        return names

    def __get_and_update_actions(self):
        response = requests.get(
            url=self.__get_url(
                paths=[f"api/{self.authentication_config.organisationID}/alerts"]
            ),
            auth=self.__get_auth(),
        )
        res = response.json()
        for alert in res["list"]:
            alert_stream = alert["stream_name"]
            alert_name = alert["name"]
            if "KeepDestination" not in alert["destinations"]:
                alert["destinations"].append("KeepDestination")
            self.logger.info(f"Updating Alert: {alert_name} in Stream: {alert_stream}")
            update_response = requests.put(
                url=self.__get_url(
                    paths=[f"api/default/{alert_stream}/alerts/{alert_name}"]
                ),
                auth=self.__get_auth(),
                json=alert,
            )
            update_res = update_response.json()
            if update_res["code"] == 200:
                self.logger.info(
                    f"Updated Alert: {alert_name} in Stream: {alert_stream}",
                    extra={"code": update_res["code"], "error": update_res["message"]},
                )
            else:
                self.logger.error(
                    f"Error while updating Alert: {alert_name} in Stream: {alert_stream}",
                    extra={"code": update_res["code"], "error": update_res["message"]},
                )

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        try:
            self.__create_alert_template()
        except Exception as e:
            self.logger.error("Error while creating Alert Template", extra=e)
        self.__create_destination(keep_api_url=keep_api_url, api_key=api_key)
        try:
            self.__get_and_update_actions()
        except Exception as e:
            self.logger.error("Error while updating Alerts", extra=e)
        self.logger.info("Webhook created")

    @staticmethod
    def _format_alert(
        event: dict,
        provider_instance: Optional["OpenobserveProvider"] = None,
    ) -> AlertDto:
        return AlertDto(
            id=event["org_name"],  # Mapping 'org_name' to 'id'
            name=event["alert_name"],  # Mapping 'alert_name' to 'name'
            severity=AlertSeverity.WARNING,
            environment=event["stream_name"],  # Mapping 'stream_name' to 'environment'
            startedAt=event[
                "alert_start_time"
            ],  # Mapping 'alert_start_time' to 'startedAt'
            lastReceived=event[
                "alert_start_time"
            ],  # Mapping 'alert_start_time' to 'startedAt'
            description=event["alert_type"],  # Mapping 'alert_type' to 'description'
            labels={
                "url": event["alert_url"],
                "alert_period": event["alert_period"],
                "alert_operator": event["alert_operator"],
                "alert_threshold": event["alert_threshold"],
                "alert_count": event["alert_count"],
                "alert_agg_value": event["alert_agg_value"],
                "alert_end_time": event["alert_end_time"],
            },
            source=["openobserve"],
        )
