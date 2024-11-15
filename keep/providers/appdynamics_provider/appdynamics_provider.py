"""
AppDynamics Provider is a class that allows to install webhooks in AppDynamics.
"""

import dataclasses
import json
import tempfile
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
class AppdynamicsProviderAuthConfig:
    """
    AppDynamics authentication configuration.
    """

    appDynamicsAccessToken: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "AppDynamics Access Token",
            "hint": "Access Token",
        },
    )
    appDynamicsAccountName: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "AppDynamics Account Name",
            "hint": "AppDynamics Account Name",
        },
    )
    # appDynamicsPassword: str = dataclasses.field(
    #     metadata={
    #         "required": True,
    #         "description": "Password",
    #         "hint": "Password associated with your account",
    #         "sensitive": True,
    #     },
    # )
    appId: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "AppDynamics appId",
            "hint": "the app instance in which the webhook should be installed",
        },
    )
    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "AppDynamics host",
            "hint": "e.g. https://baseball202404101029219.saas.appdynamics.com",
        },
    )


class AppdynamicsProvider(BaseProvider):
    """Install Webhooks and receive alerts from AppDynamics."""

    PROVIDER_DISPLAY_NAME = "AppDynamics"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is Authorized",
            mandatory=True,
            mandatory_for_webhook=True,
            alias="Rules Reader",
        ),
        ProviderScope(
            name="administrator",
            description="Administrator privileges",
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
        Validates required configuration for AppDynamics provider.

        """
        self.authentication_config = AppdynamicsProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.host.startswith(
            "https://"
        ) and not self.authentication_config.host.startswith("http://"):
            self.authentication_config.host = (
                f"https://{self.authentication_config.host}"
            )

    def __get_url(self, paths: List[str] = None, query_params: dict = None, **kwargs):
        """
        Helper method to build the url for AppDynamics api requests.

        Example:

        paths = ["issue", "createmeta"]
        query_params = {"projectKeys": "key1"}
        url = __get_url("test", paths, query_params)

        # url = https://baseballxyz.saas.appdynamics.com/rest/api/2/issue/createmeta?projectKeys=key1
        """
        paths = paths or []

        url = urljoin(
            f"{self.authentication_config.host}/controller",
            "/".join(str(path) for path in paths),
        )

        # add query params
        if query_params:
            url = f"{url}?{urlencode(query_params)}"

        return url

    def get_user_id_by_name(self, name: str) -> Optional[str]:
        self.logger.info("Getting user ID by name")
        response = requests.get(
            url=self.__get_url(paths=["controller/api/rbac/v1/users/"]),
            headers=self.__get_headers(),
        )
        if response.ok:
            users = response.json()
            for user in users["users"]:
                if user["name"].lower() == name.lower():
                    return user["id"]
            return None
        else:
            self.logger.error(
                "Error while validating scopes for AppDynamics", extra=response.json()
            )

    def validate_scopes(self) -> dict[str, bool | str]:
        authenticated = False
        administrator = "Missing Administrator Privileges"
        self.logger.info("Validating AppDynamics Scopes")

        user_id = self.get_user_id_by_name(self.authentication_config.appDynamicsAccountName)

        url = self.__get_url(
            paths=[
                "controller/api/rbac/v1/users/",
                user_id,
            ]
        )

        response = requests.get(
            url=url,
            headers=self.__get_headers(),
        )
        if response.ok:
            authenticated = True
            response = response.json()
            for role in response["roles"]:
                if (
                    role["name"] == "Account Administrator"
                    or role["name"] == "Administrator"
                ):
                    administrator = True
                    self.logger.info(
                        "All scopes validated successfully for AppDynamics"
                    )
                    break
        else:
            self.logger.error(
                "Error while validating scopes for AppDynamics", extra=response.json()
            )

        return {"authenticated": authenticated, "administrator": administrator}

    def __get_headers(self):
        return {
            "Authorization": f"Bearer {self.authentication_config.appDynamicsAccessToken}",
        }

    def __create_http_response_template(self, keep_api_url: str, api_key: str):
        keep_api_host, keep_api_path = keep_api_url.rsplit("/", 1)

        # The httpactiontemplate.json is a template/skeleton for creating a new HTTP Request Action in AppDynamics
        temp = tempfile.NamedTemporaryFile(mode="w+t", delete=True)

        template = json.load(open(rf"{Path(__file__).parent}/httpactiontemplate.json"))
        template[0]["host"] = keep_api_host.lstrip("http://").lstrip("https://")
        template[0]["path"], template[0]["query"] = keep_api_path.split("?")
        template[0]["path"] = "/" + template[0]["path"].rstrip("/")

        template[0]["headers"][0]["value"] = api_key

        temp.write(json.dumps(template))
        temp.seek(0)

        res = requests.post(
            self.__get_url(paths=["controller/actiontemplate/httprequest"]),
            files={"template": temp},
            headers=self.__get_headers(),
        )
        res = res.json()
        temp.close()
        if res["success"] == "True":
            self.logger.info("HTTP Response template Successfully Created")
        else:
            self.logger.info("HTTP Response template creation failed", extra=res)
            if "already exists" in res["errors"][0]:
                self.logger.info(
                    "HTTP Response template creation failed as it already exists",
                    extra=res,
                )
                raise ResourceAlreadyExists()
            raise Exception(res["errors"])

    def __create_action(self):
        response = requests.post(
            url=self.__get_url(
                paths=[
                    "alerting/rest/v1/applications",
                    self.authentication_config.appId,
                    "actions",
                ]
            ),
            headers=self.__get_headers(),
            json={
                "actionType": "HTTP_REQUEST",
                "name": "KeepAction",
                "httpRequestTemplateName": "KeepWebhook",
                "customTemplateVariables": [],
            },
        )
        if response.ok:
            self.logger.info("Action Created")
        else:
            response = response.json()
            self.logger.info("Action Creation failed")
            if "already exists" in response["message"]:
                raise ResourceAlreadyExists()
            raise Exception(response["message"])

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        try:
            self.__create_http_response_template(
                keep_api_url=keep_api_url, api_key=api_key
            )
        except ResourceAlreadyExists:
            self.logger.info("Template already exists, proceeding with webhook setup")
        except Exception as e:
            raise e
        try:
            self.__create_action()
        except ResourceAlreadyExists:
            self.logger.info("Template already exists, proceeding with webhook setup")
        except Exception as e:
            raise e

        # Listing all policies in the specified app
        policies_response = requests.get(
            url=self.__get_url(
                paths=[
                    "alerting/rest/v1/applications",
                    self.authentication_config.appId,
                    "policies",
                ]
            ),
            headers=self.__get_headers(),
        )

        policies = policies_response.json()
        policy_config = {
            "actionName": "KeepAction",
            "actionType": "HTTP_REQUEST",
        }
        for policy in policies:
            curr_policy = requests.get(
                url=self.__get_url(
                    paths=[
                        "alerting/rest/v1/applications",
                        self.authentication_config.appId,
                        "policies",
                        policy["id"],
                    ]
                ),
                headers=self.__get_headers(),
            ).json()
            if policy_config not in curr_policy["actions"]:
                curr_policy["actions"].append(policy_config)
            if "executeActionsInBatch" not in curr_policy:
                curr_policy["executeActionsInBatch"] = True
            new_events_dictionary = {}
            for event_key, event_value in curr_policy["events"].items():
                if event_value is None or len(event_value) == 0:
                    continue
                else:
                    new_events_dictionary[event_key] = event_value

            curr_policy["events"] = new_events_dictionary
            request = requests.put(
                url=self.__get_url(
                    paths=[
                        "/alerting/rest/v1/applications",
                        self.authentication_config.appId,
                        "policies",
                        policy["id"],
                    ]
                ),
                headers=self.__get_headers(),
                json=curr_policy,
            )
            if not request.ok:
                self.logger.info("Failed to add Webhook")
                raise Exception("Could not create webhook")
        self.logger.info("Webhook created")

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        return AlertDto(
            id=event["id"],
            name=event["name"],
            severity=AppdynamicsProvider.SEVERITIES_MAP.get(event["severity"]),
            lastReceived=event["lastReceived"],
            message=event["message"],
            description=event["description"],
            event_id=event["event_id"],
            url=event["url"],
            source=["appdynamics"],
        )
