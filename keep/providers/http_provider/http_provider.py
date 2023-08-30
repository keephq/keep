"""
HttpProvider is a class that provides a way to send HTTP requests.
"""
import json
import typing

import requests
from requests.exceptions import JSONDecodeError

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class HttpProvider(BaseProvider):
    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Nothing to do here.
        """
        pass

    def validate_config(self):
        """
        No configuration to validate here
        """

    def notify(
        self,
        url: str,
        method: typing.Literal["GET", "POST", "PUT", "DELETE"],
        headers: dict = None,
        body: dict = None,
        params: dict = None,
        proxies: dict = None,
        **kwargs,
    ):
        """
        Send a HTTP request to the given url.
        """
        self.query(
            url=url,
            method=method,
            headers=headers,
            body=body,
            params=params,
            proxies=proxies,
            **kwargs,
        )

    def _query(
        self,
        url: str,
        method: typing.Literal["GET", "POST", "PUT", "DELETE"],
        headers: dict = None,
        body: dict = None,
        params: dict = None,
        proxies: dict = None,
        **kwargs: dict,
    ) -> dict:
        """
        Send a HTTP request to the given url.
        """
        if headers is None:
            headers = {}
        if isinstance(headers, str):
            headers = json.loads(headers)
        if body is None:
            body = {}
        if params is None:
            params = {}

        # todo: this might be problematic if params/body/headers contain sensitive data
        # think about changing those debug messages or adding a flag to enable/disable them
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
                url, headers=headers, params=params, proxies=proxies, **kwargs
            )
        elif method == "POST":
            response = requests.post(
                url, headers=headers, json=body, proxies=proxies, **kwargs
            )
        elif method == "PUT":
            response = requests.put(
                url, headers=headers, json=body, proxies=proxies, **kwargs
            )
        elif method == "DELETE":
            response = requests.delete(
                url, headers=headers, json=body, proxies=proxies, **kwargs
            )
        else:
            raise Exception(f"Unsupported HTTP method: {method}")

        self.logger.debug(
            f"Sent {method} request to {url}",
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
