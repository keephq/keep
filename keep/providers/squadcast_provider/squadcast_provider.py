"""
SquadcastProvider is a class that implements the Squadcast API and allows creating incidents and notes.
"""

import dataclasses
import json

import pydantic
import requests
from requests import HTTPError

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.validation.fields import HttpsUrl


@pydantic.dataclasses.dataclass
class SquadcastProviderAuthConfig:
    service_region: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Service region: EU/US",
            "hint": "https://apidocs.squadcast.com/#intro",
            "sensitive": False,
        }
    )
    refresh_token: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "Squadcast Refresh Token",
            "hint": "https://support.squadcast.com/docs/squadcast-public-api",
            "sensitive": True,
        },
        default=None,
    )
    webhook_url: HttpsUrl | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "Incident webhook url",
            "hint": "https://support.squadcast.com/integrations/incident-webhook-incident-webhook-api",
            "sensitive": True,
            "validation": "https_url",
        },
        default=None,
    )


class SquadcastProvider(BaseProvider):
    """Create incidents and notes using the Squadcast API."""

    PROVIDER_DISPLAY_NAME = "Squadcast"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Incident Management"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="The user can connect to the client",
            mandatory=False,
            alias="Connect to the client",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_scopes(self):
        """
        Validates that the user has the required scopes to use the provider.
        """
        refresh_headers = {
            "content-type": "application/json",
            "X-Refresh-Token": f"{self.authentication_config.refresh_token}",
        }
        resp = requests.get(
            f"{self.__get_endpoint('auth')}/oauth/access-token", headers=refresh_headers
        )
        try:
            resp.raise_for_status()
            scopes = {
                "authenticated": True,
            }
        except Exception as e:
            self.logger.exception("Error validating scopes")
            scopes = {
                "authenticated": str(e),
            }
        return scopes

    def __get_endpoint(self, endpoint: str):
        if endpoint == "auth":
            return ("https://auth.eu.squadcast.com", "https://auth.squadcast.com")[
                self.authentication_config.service_region == "US"
            ]
        elif endpoint == "api":
            return ("https://api.eu.squadcast.com", "https://api.squadcast.com")[
                self.authentication_config.service_region == "US"
            ]

    def validate_config(self):
        self.authentication_config = SquadcastProviderAuthConfig(
            **self.config.authentication
        )
        if (
            not self.authentication_config.refresh_token
            and not self.authentication_config.webhook_url
        ):
            raise ProviderConfigException(
                "SquadcastProvider requires either refresh_token or webhook_url",
                provider_id=self.provider_id,
            )

    def _create_incidents(
        self,
        headers: dict,
        message: str,
        description: str,
        tags: dict = {},
        priority: str = "",
        status: str = "",
        event_id: str = "",
        additional_json: str = "",
    ):
        body = json.dumps(
            {
                "message": message,
                "description": description,
                "tags": tags,
                "priority": priority,
                "status": status,
                "event_id": event_id,
            }
        )

        # append body to additional_json we are doing this way because we don't want to override the core body fields
        body = json.dumps({**json.loads(additional_json), **json.loads(body)})

        return requests.post(
            self.authentication_config.webhook_url, data=body, headers=headers
        )

    def _crete_notes(
        self, headers: dict, message: str, incident_id: str, attachments: list = []
    ):
        body = json.dumps({"message": message, "attachments": attachments})
        return requests.post(
            f"{self.__get_endpoint('api')}/v3/incidents/{incident_id}/warroom",
            data=body,
            headers=headers,
        )

    def _notify(
        self,
        notify_type: str,
        message: str = "",
        description: str = "",
        incident_id: str = "",
        priority: str = "",
        tags: dict = {},
        status: str = "",
        event_id: str = "",
        attachments: list = [],
        additional_json: str = "",
        **kwargs,
    ) -> dict:
        """
        Create an incident or notes using the Squadcast API.
        """

        self.logger.info(
            f"Creating {notify_type} using SquadcastProvider",
            extra={notify_type: notify_type},
        )
        refresh_headers = {
            "content-type": "application/json",
            "X-Refresh-Token": f"{self.authentication_config.refresh_token}",
        }
        api_key_resp = requests.get(
            f"{self.__get_endpoint('auth')}/oauth/access-token", headers=refresh_headers
        )
        headers = {
            "content-type": "application/json",
            "Authorization": f"Bearer {api_key_resp.json()['data']['access_token']}",
        }
        if notify_type == "incident":
            if message == "" or description == "":
                raise Exception(
                    f'message: "{message}" and description: "{description}" cannot be empty'
                )
            resp = self._create_incidents(
                headers=headers,
                message=message,
                description=description,
                tags=tags,
                priority=priority,
                status=status,
                event_id=event_id,
                additional_json=additional_json,
            )
        elif notify_type == "notes":
            if message == "" or incident_id == "":
                raise Exception(
                    f'message: "{message}" and incident_id: "{incident_id}" cannot be empty'
                )
            resp = self._crete_notes(
                headers=headers,
                message=message,
                incident_id=incident_id,
                attachments=attachments,
            )
        else:
            raise Exception(
                "notify_type is a mandatory field, expected: incident | notes"
            )
        try:
            resp.raise_for_status()
            return resp.json()
        except HTTPError as e:
            raise Exception(f"Failed to create issue: {str(e)}")

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass


if __name__ == "__main__":
    import os

    squadcast_api_key = os.environ.get("SQUADCAST_API_KEY")
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Initalize the provider and provider config
    config = ProviderConfig(
        authentication={"api_key": squadcast_api_key},
    )
    provider = SquadcastProvider(
        context_manager, provider_id="squadcast-test", config=config
    )
    response = provider.notify(
        description="test",
    )
    print(response)
