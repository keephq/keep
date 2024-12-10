"""
WebhookProvider is a class that provides a way to notify a 3rd party service using a webhook.
"""

import base64
import dataclasses
import json
import typing

import pydantic
import requests
from requests.exceptions import JSONDecodeError

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class WebhookProviderAuthConfig:
    """
    Webhook authentication configuration.
    """

    url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Webhook URL",
            "validation": "any_http_url"
        }
    )

    method: typing.Literal["GET", "POST", "PUT", "DELETE"] = dataclasses.field(
        default="POST",
        metadata={
            "required": True,
            "description": "HTTP method",
            "type": "select",
            "options": ["POST", "GET", "PUT", "DELETE"],
        },
    )

    http_basic_authentication_username: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "description": "HTTP basic authentication - Username",
            "config_sub_group": "basic_authentication",
            "config_main_group": "authentication",
        },
    )

    http_basic_authentication_password: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "description": "HTTP basic authentication - Password",
            "sensitive": True,
            "config_sub_group": "basic_authentication",
            "config_main_group": "authentication",
        },
    )

    api_key: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "description": "API key",
            "sensitive": True,
            "config_sub_group": "api_key",
            "config_main_group": "authentication",
        },
    )

    headers: typing.Optional[dict[str, str]] = dataclasses.field(
        default=None,
        metadata={
            "description": "Headers",
            "type": "form",
        },
    )


class WebhookProvider(BaseProvider):
    """Enrich alerts with data from Webhook."""

    BLACKLISTED_ENDPOINTS = [
        "metadata.google.internal",
        "metadata.internal",
        "169.254.169.254",
        "localhost",
        "googleapis.com",
    ]
    PROVIDER_CATEGORY = ["Developer Tools"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="send_webhook",
            mandatory=True,
            alias="Send Webhook",
        )
    ]

    PROVIDER_TAGS = ["messaging"]
    PROVIDER_DISPLAY_NAME = "Webhook"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Nothing to do here.
        """
        pass

    def validate_scopes(self) -> dict[str, bool | str]:
        validated_scopes = {}
        # try to send the webhook with TEST payload
        try:
            self._notify(body={"test": "payload"})
        except Exception as e:
            validated_scopes["send_webhook"] = str(e)
            return validated_scopes
        validated_scopes["send_webhook"] = True
        return validated_scopes

    def validate_config(self):
        self.authentication_config = WebhookProviderAuthConfig(
            **self.config.authentication
        )

    def __validate_url(self, url: str):
        """
        Validate that the url is not blacklisted.
        """
        for endpoint in WebhookProvider.BLACKLISTED_ENDPOINTS:
            if endpoint in url:
                raise Exception(f"URL {url} is blacklisted")

    def _notify(
        self,
        body: dict = None,
        params: dict = None,
        **kwargs,
    ):
        """
        Send a HTTP request to the given url.
        """
        self.query(
            url=self.authentication_config.url,
            method=self.authentication_config.method,
            http_basic_authentication_username=self.authentication_config.http_basic_authentication_username,
            http_basic_authentication_password=self.authentication_config.http_basic_authentication_password,
            api_key=self.authentication_config.api_key,
            headers=self.authentication_config.headers,
            body=body,
            params=params,
            **kwargs,
        )

    def _query(
        self,
        url: str,
        method: typing.Literal["GET", "POST", "PUT", "DELETE"] = "POST",
        http_basic_authentication_username: str = None,
        http_basic_authentication_password: str = None,
        api_key: str = None,
        headers: str = None,
        body: dict = None,
        params: dict = None,
        **kwargs: dict,
    ) -> dict:
        """
        Trigger a webhook with the given method, headers, body and params.
        """
        self.__validate_url(url)
        if headers is None:
            headers = {}
        if isinstance(headers, str):
            headers =  json.loads(headers) if len(headers) > 0 else  {}
        if body is None:
            body = {}
        if isinstance(body, str):
           body =  json.loads(body) if len(body) > 0 else  {}    
        if params is None:
            params = {}
        if isinstance(params, str):
           params =  json.loads(params) if len(params) > 0 else  {}  

        if http_basic_authentication_username and http_basic_authentication_password:
            credentials = f"{http_basic_authentication_username}:{http_basic_authentication_password}"
            encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode(
                "utf-8"
            )
            headers["Authorization"] = f"Basic {encoded_credentials}"

        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self.logger.debug(
            f"Sending {method} request to {url}",
            extra={
                "body": body,
                "headers": headers,
                "params": params,
            },
        )
        if method == "GET":
            response = requests.get(url, headers=headers, params=params, **kwargs)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=body, **kwargs)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=body, **kwargs)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, json=body, **kwargs)

        self.logger.debug(
            f"Trigger a webhook with {method} on {url}",
            extra={
                "body": body,
                "headers": headers,
                "params": params,
                "status_code": response.status_code,
            },
        )

        result = {"status": response.ok, "status_code": response.status_code}

        try:
            body = response.json()
        except JSONDecodeError:
            body = response.text

        result["body"] = body
        return result
