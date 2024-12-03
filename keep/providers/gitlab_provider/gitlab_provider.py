"""
GitlabProvider is a class that implements the BaseProvider interface for GitLab updates.
"""

import dataclasses
import urllib.parse

import pydantic
import requests
from requests import HTTPError

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class GitlabProviderAuthConfig:
    """GitLab authentication configuration."""

    host: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "GitLab Host",
            "sensitive": False,
            "hint": "http://example.gitlab.com",
            "validation": "any_http_url"
        }
    )

    personal_access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "GitLab Personal Access Token",
            "sensitive": True,
            "documentation_url": "https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html",
        }
    )


class GitlabProvider(BaseProvider):
    """Enrich alerts with GitLab tickets."""

    PROVIDER_SCOPES = [
        ProviderScope(
            name="api",
            description="Authenticated with api scope",
            mandatory=True,
            alias="GitLab PAT with api scope",
        ),
    ]
    PROVIDER_TAGS = ["ticketing"]
    PROVIDER_DISPLAY_NAME = "GitLab"
    PROVIDER_CATEGORY = ["Developer Tools"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        self._host = None
        super().__init__(context_manager, provider_id, config)

    def validate_scopes(self):
        """
        Validate that the provider has the required scopes.
        """

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.authentication_config.personal_access_token}",
        }

        # first, validate user/api token are correct:
        resp = requests.get(
            f"{self.gitlab_host}/api/v4/personal_access_tokens/self",
            headers=headers,
            verify=False,
        )
        try:
            resp.raise_for_status()
            scopes = {
                "api": ("Missing api scope", True)["api" in resp.json()["scopes"]]
            }
        except HTTPError as e:
            scopes = {"api": str(e)}
        return scopes

    def validate_config(self):
        self.authentication_config = GitlabProviderAuthConfig(
            **self.config.authentication
        )

    @property
    def gitlab_host(self):
        # if not the first time, return the cached host
        if self._host:
            return self._host.rstrip("/")

        # if the user explicitly supplied a host with http/https, use it
        if self.authentication_config.host.startswith(
            "http://"
        ) or self.authentication_config.host.startswith("https://"):
            self._host = self.authentication_config.host
            return self.authentication_config.host.rstrip("/")

        # otherwise, try to use https:
        try:
            requests.get(
                f"https://{self.authentication_config.host}",
                verify=False,
            )
            self.logger.debug("Using https")
            self._host = f"https://{self.authentication_config.host}"
            return self._host.rstrip("/")
        except requests.exceptions.SSLError:
            self.logger.debug("Using http")
            self._host = f"http://{self.authentication_config.host}"
            return self._host.rstrip("/")
        # should happen only if the user supplied invalid host, so just let validate_config fail
        except Exception:
            return self.authentication_config.host.rstrip("/")

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def __get_auth_header(self):
        """
        Helper method to build the auth payload for gitlab api requests.
        """
        return {
            "Authorization": f"Bearer {self.authentication_config.personal_access_token}"
        }

    # @staticmethod
    def __build_params_from_kwargs(self, kwargs: dict):
        params = dict()
        for param in kwargs:
            if isinstance(kwargs[param], list):
                params[param] = ",".join(kwargs[param])
            else:
                params[param] = kwargs[param]
        return params

    def _notify(
        self,
        id: str,
        title: str,
        description: str = "",
        labels: str = "",
        issue_type: str = "issue",
        **kwargs: dict,
    ):
        id = urllib.parse.quote(id, safe="")
        print(id)
        params = self.__build_params_from_kwargs(
            kwargs={
                **kwargs,
                "title": title,
                "description": description,
                "labels": labels,
                "issue_type": issue_type,
            }
        )
        print(self.gitlab_host)
        resp = requests.post(
            f"{self.gitlab_host}/api/v4/projects/{id}/issues",
            headers=self.__get_auth_header(),
            params=params,
        )
        try:
            resp.raise_for_status()
        except HTTPError as e:
            raise Exception(f"Failed to create issue: {str(e)}")
        return resp.json()


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
    import os

    gitlab_pat = os.environ.get("GITLAB_PAT")
    gitlab_host = os.environ.get("GITLAB_HOST")

    # Initalize the provider and provider config
    config = ProviderConfig(
        description="GitLab Provider",
        authentication={
            "personal_access_token": gitlab_pat,
            "host": gitlab_host,
        },
    )
    provider = GitlabProvider(context_manager, provider_id="gitlab", config=config)
    scopes = provider.validate_scopes()
    # Create ticket
    provider.notify(
        board_name="KEEP board",
        issue_type="Task",
        summary="Test Alert",
        description="Test Alert Description",
    )
