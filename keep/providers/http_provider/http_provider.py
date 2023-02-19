"""
HttpProvider is a class that provides a way to send HTTP requests.
"""
import typing

import requests
from requests.exceptions import JSONDecodeError

from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class HttpProvider(BaseProvider):
    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)

    def dispose(self):
        """
        Nothing to do here.
        """
        pass

    def validate_config(self):
        """
        Not configuration to validate here
        """

    def query(
        self,
        url: str,
        method: typing.Literal["GET", "POST", "PUT", "DELETE"],
        headers: dict = None,
        body: dict = None,
        params: dict = None,
        **kwargs: dict,
    ) -> dict | str:
        """
        Send a HTTP request to the given url.
        """
        if headers is None:
            headers = {}
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
            response = requests.get(url, headers=headers, params=params)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=body)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=body)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, json=body)
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

        try:
            return response.json()
        except JSONDecodeError:
            return response.text


if __name__ == "__main__":
    config = ProviderConfig(authentication={})
    mysql_provider = HttpProvider("simple-http", config)
    results = mysql_provider.query()
    print(results)
