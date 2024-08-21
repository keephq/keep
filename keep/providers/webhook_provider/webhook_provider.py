"""
WebhookProvider is a class that provides a way to notify a 3rd party service using a webhook.
"""
import json
import base64
import typing

import requests
from requests.exceptions import JSONDecodeError

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class WebhookProvider(BaseProvider):
    """Enrich alerts with data from Webhook."""

    BLACKLISTED_ENDPOINTS = [
        "metadata.google.internal",
        "metadata.internal",
        "169.254.169.254",
        "localhost",
        "googleapis.com",
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def __validate_url(self, url: str):
        """
        Validate that the url is not blacklisted.
        """
        for endpoint in WebhookProvider.BLACKLISTED_ENDPOINTS:
            if endpoint in url:
                raise Exception(f"URL {url} is blacklisted")

    def dispose(self):
        """
        Nothing to do here.
        """
        pass

    def validate_config(self):
        """
        No configuration to validate here
        """

    def _notify(
        self,
        url: str,
        method: typing.Literal["GET", "POST", "PUT", "DELETE"] = "POST",
        http_basic_authentication_username: str = None,
        http_basic_authentication_password: str = None,
        api_key: str = None,
        headers: dict = None,
        body: dict = None,
        params: dict = None,
        **kwargs,
    ):
        """
        Send a HTTP request to the given url.
        """
        self.query(
            url=url,
            method=method,
            http_basic_authentication_username=http_basic_authentication_username,
            http_basic_authentication_password=http_basic_authentication_password,
            api_key=api_key,
            headers=headers,
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
        headers: dict = None,
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
            headers = json.loads(headers)
        if body is None:
            body = {}
        if params is None:
            params = {}

        if http_basic_authentication_username and http_basic_authentication_password:
            credentials = f"{http_basic_authentication_username}:{http_basic_authentication_password}"
            encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
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
            response = requests.get(
                url, headers=headers, params=params, **kwargs
            )
        elif method == "POST":
            response = requests.post(
                url, headers=headers, json=body, **kwargs
            )
        elif method == "PUT":
            response = requests.put(
                url, headers=headers, json=body, **kwargs
            )
        elif method == "DELETE":
            response = requests.delete(
                url, headers=headers, json=body, **kwargs
            )

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
