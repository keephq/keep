"""
GithubWorkflowProvider is a provider that interacts with Github Workflows API.
"""

import dataclasses
import pydantic
import requests
from requests.exceptions import JSONDecodeError

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GithubWorkflowsProviderAuthConfig:
    """
    GithubWorkflowsProviderAuthConfig is a class that represents the authentication configuration for the GithubWorkflowsProvider.
    """

    personal_access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Github Personal Access Token",
            "sensitive": True,
        }
    )


class GithubWorkflowsProvider(BaseProvider):
    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GithubWorkflowsProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _notify(
            self,
            github_url: str = "",
            github_method: str = "",
            **kwargs
            ):
        url = github_url
        method = github_method.upper()

        result = self.query(url=url, method=method, **kwargs)

        response_status = result["status"]

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
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": self.authentication_config.personal_access_token,
            "X--GitHub-Api-Version": "2022-11-28",
        }

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
        print(result)

        try:
            body = response.json()
        except JSONDecodeError:
            body = response.text

        result["body"] = body
        return result


if __name__ == "__main__":
    import os

    github_personal_access_token = os.environ.get("GITHUB_TOKEN") or ""

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    github_workflows_provider = GithubWorkflowsProvider(
        context_manager,
        "test",
        ProviderConfig(
            authentication={"personal_access_token": github_personal_access_token}
        ),
    )
    result = github_workflows_provider.notify(
        github_url="https://api.github.com/repos/TakshPanchal/keep/actions/workflows",
        github_method="get",
    )
    print(result)
