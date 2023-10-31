"""
JiraProvider is a class that implements the BaseProvider interface for Jira updates.
"""
import dataclasses

import pydantic
import requests
from requests.auth import HTTPBasicAuth
from typing import List, Dict, Literal
from urllib.parse import urlencode, urljoin

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class JiraProviderAuthConfig:
    """Jira authentication configuration."""

    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Atlassian Jira API Token",
            "sensitive": True,
        }
    )


class JiraProvider(BaseProvider):
    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = JiraProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def __get_url(
        self, host: str, paths: List[str] = [], query_params: dict = None, **kwargs
    ):
        """
        Helper method to build the url for jira api requests.

        BASE_URL = https://<YOUR_HOST>.atlassian.net/rest/api/2

        Example:

        paths = ["issue", "createmeta"]
        query_params = {"projectKeys": "key1"}
        url = __get_url("test", paths, query_params)

        # url = https://test.atlassian.net/rest/api/2/issue/createmeta?projectKeys=key1
        """
        # add url path
        url = urljoin(
            f"https://{host}.atlassian.net/rest/api/2/",
            "/".join(str(path) for path in paths),
        )

        # add query params
        if query_params:
            url = f"{url}?{urlencode(query_params)}"

        return url

    def __get_auth(self, email: str):
        """
        Helper method to build the auth payload for jira api requests.
        """
        return HTTPBasicAuth(email, self.authentication_config.api_token)

    def __get_createmeta(self, host: str, email: str, project_key: str):
        try:
            self.logger.info("Fetching create meta data...")

            url = self.__get_url(
                host=host,
                paths=["issue", "createmeta"],
                query_params={"projectKeys": project_key},
            )

            response = requests.get(url=url, auth=self.__get_auth(email))

            response.raise_for_status()

            self.logger.info("Fetched create meta data!")

            return response.json()
        except Exception as e:
            raise ProviderException(f"Failed to fetch createmeta: {e}")

    def __get_single_createmeta(self, host: str, email: str, project_key: str):
        """
        Helper method to get single createmeta. As the original createmeta api returns
        multiple issue types and other config.
        """
        try:
            self.logger.info("Fetching single createmeta...")

            createmeta = self.__get_createmeta(host, email, project_key)

            projects = createmeta.get("projects", [])
            project = projects[0] if len(project_key) > 0 else {}

            issuetypes = project.get("issuetypes", [])
            issuetype = issuetypes[0] if len(issuetypes) > 0 else {}

            issue_type_name = issuetype.get("name", "")
            if not issue_type_name:
                raise ProviderException("No issue types found!")

            self.logger.info("Fetched single createmeta!")

            return {"issue_type_name": issue_type_name}
        except Exception as e:
            raise ProviderException(f"Failed to fetch single createmeta: {e}")

    def __create_issue(
        self,
        host: str,
        email: str,
        project_key: str,
        summary: str,
        description: str = "",
        issue_type: str = "",
        **kwargs: dict,
    ):
        """
        Helper method to create an issue in jira.
        """
        try:
            self.logger.info("Creating an issue...")

            if not issue_type:
                create_meta = self.__get_single_createmeta(
                    host=host, email=email, project_key=project_key
                )
                issue_type = create_meta.get("issue_type_name", "")

            url = self.__get_url(host, paths=["issue"])

            request_body = {
                "fields": {
                    "summary": summary,
                    "description": description,
                    "project": {"key": project_key},
                    "issuetype": {"name": issue_type},
                }
            }

            response = requests.post(
                url=url, json=request_body, auth=self.__get_auth(email)
            )

            self.logger.info("Created an issue!")

            return {"issue": response.json()}
        except Exception as e:
            raise ProviderException(f"Failed to create an issue: {e}")

    def _notify(
        self,
        host: str,
        email: str,
        project_key: str,
        summary: str,
        description: str = "",
        issue_type: str = "",
        **kwargs: dict,
    ):
        """
        Notify jira by creating an issue.
        """
        try:
            self.logger.info("Notifying jira...")

            result = self.__create_issue(
                host=host,
                email=email,
                project_key=project_key,
                summary=summary,
                description=description,
                issue_type=issue_type,
            )

            self.logger.info("Notified jira!")

            return result
        except Exception as e:
            raise ProviderException(f"Failed to notify jira: {e}")

    def _query(self, host="", board_id="", email="", **kwargs: dict):
        """
        API for fetching issues:
        https://developer.atlassian.com/cloud/jira/software/rest/api-group-board/#api-rest-agile-1-0-board-boardid-issue-get

        Args:
            kwargs (dict): The providers with context
        """
        self.logger.debug("Fetching data from Jira")

        jira_api_token = self.authentication_config.api_token

        request_url = f"https://{host}/rest/agile/1.0/board/{board_id}/issue"
        response = requests.get(request_url, auth=(email, jira_api_token))
        if not response.ok:
            raise ProviderException(
                f"{self.__class__.__name__} failed to fetch data from Jira: {response.text}"
            )
        self.logger.debug("Fetched data from Jira")

        issues = response.json()
        return {"number_of_issues": issues["total"]}


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

    jira_api_token = os.environ.get("JIRA_API_TOKEN")

    # Initalize the provider and provider config
    config = ProviderConfig(
        description="Jira Input Provider",
        authentication={"api_token": jira_api_token},
    )
    provider = JiraProvider(context_manager, provider_id="jira", config=config)
    provider.query(host="JIRA HOST", board_id="1", email="YOUR EMAIL")
