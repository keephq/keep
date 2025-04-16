"""
HttpProvider is a class that provides a way to send HTTP requests.
"""

import copy
import json
import typing

import requests
from requests.exceptions import JSONDecodeError

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class HttpProvider(BaseProvider):
    """Enrich alerts with data from HTTP."""

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
        for endpoint in HttpProvider.BLACKLISTED_ENDPOINTS:
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
        method: typing.Literal["GET", "POST", "PUT", "DELETE"],
        headers: dict = None,
        body: dict = None,
        params: dict = None,
        proxies: dict = None,
        verify: bool = True,
        **kwargs,
    ):
        """
        Send a HTTP request to the given url.
        """
        return self.query(
            url=url,
            method=method,
            headers=headers,
            body=body,
            params=params,
            proxies=proxies,
            verify=verify,
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
        fail_on_error: bool = True,
        verify: bool = True,
        **kwargs: dict,
    ) -> dict:
        """
        Send a HTTP request to the given url.
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

        extra_args = copy.deepcopy(kwargs)
        extra_args.pop("enrich_alert", None)

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
                url,
                headers=headers,
                params=params,
                proxies=proxies,
                verify=verify,
                **extra_args,
            )
        elif method == "POST":
            response = requests.post(
                url,
                headers=headers,
                json=body,
                proxies=proxies,
                verify=verify,
                **extra_args,
            )
        elif method == "PUT":
            response = requests.put(
                url,
                headers=headers,
                json=body,
                proxies=proxies,
                verify=verify,
                **extra_args,
            )
        elif method == "DELETE":
            response = requests.delete(
                url,
                headers=headers,
                json=body,
                proxies=proxies,
                verify=verify,
                **extra_args,
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

        if fail_on_error:
            self.logger.info(
                f"HTTP response: {response.status_code} {response.reason}",
                extra={"body": body},
            )
            response.raise_for_status()

        result = {"status": response.ok, "status_code": response.status_code}

        try:
            body = response.json()
        except JSONDecodeError:
            body = response.text

        result["body"] = body

        return result
