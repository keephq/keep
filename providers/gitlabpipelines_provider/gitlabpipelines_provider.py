"""
GitlabPipelinesProvider is a provider that interacts with GitLab Pipelines API.
"""

import dataclasses

import pydantic
import requests
from requests.exceptions import JSONDecodeError

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GitlabpipelinesProviderAuthConfig:
    """
    GitlabpipelinesProviderAuthConfig is a class that represents the authentication configuration for the GitlabPipelinesProvider.
    """

    access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "GitLab Access Token",
            "sensitive": True,
        }
    )


class GitlabpipelinesProvider(BaseProvider):
    """Enrich alerts with data from GitLab Pipelines."""

    PROVIDER_DISPLAY_NAME = "GitLab Pipelines"
    PROVIDER_CATEGORY = ["Developer Tools"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GitlabpipelinesProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _notify(self, gitlab_url: str = "", gitlab_method: str = "", **kwargs):
        url = gitlab_url
        method = gitlab_method.upper()

        result = self.query(url=url, method=method, **kwargs)

        response_status = result["status"]

        print(f"Sent {method} request to {url} with status {response_status}")

        self.logger.debug(
            f"Sent {method} request to {url} with status {response_status}",
            extra={
                "body": result["body"],
                "headers": result["headers"],
                "status_code": result["status"],
            },
        )

        return result

    def _query(self, url: str, method: str, **kwargs: dict):
        headers = {"PRIVATE-TOKEN": self.authentication_config.access_token}

        if method == "GET":
            response = requests.get(url, headers=headers, **kwargs)
        elif method == "POST":
            response = requests.post(url, headers=headers, **kwargs)
        elif method == "PUT":
            response = requests.put(url, headers=headers, **kwargs)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, **kwargs)
        else:
            raise Exception(f"Unsupported HTTP method: {method}")

        result = {
            "status": response.ok,
            "status_code": response.status_code,
            "method": method,
            "url": url,
            "headers": headers,
        }

        try:
            body = response.json()
        except JSONDecodeError:
            body = response.text

        result["body"] = body
        return result


if __name__ == "__main__":
    import os

    gitlab_private_access_token = os.environ.get("GITLAB_PAT") or ""

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    gitlab_pipelines_provider = GitlabpipelinesProvider(
        context_manager,
        "test",
        ProviderConfig(authentication={"access_token": gitlab_private_access_token}),
    )
    result = gitlab_pipelines_provider.notify()
    print(result)
