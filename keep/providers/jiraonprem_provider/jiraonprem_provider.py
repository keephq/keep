"""
JiraonpremProvider is a class that implements the BaseProvider interface for Jira updates.
"""

import dataclasses
import json
from typing import List
from urllib.parse import urlencode, urljoin

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class JiraonpremProviderAuthConfig:
    """Jira On Prem authentication configuration."""

    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Jira Host",
            "sensitive": False,
            "hint": "jira.onprem.com",
        }
    )

    personal_access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Jira PAT",
            "sensitive": True,
            "documentation_url": "https://confluence.atlassian.com/enterprise/using-personal-access-tokens-1026032365.html",
        }
    )


class JiraonpremProvider(BaseProvider):
    """Enrich alerts with Jira tickets."""

    PROVIDER_CATEGORY = ["Ticketing"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="BROWSE_PROJECTS",
            description="Browse Jira Projects",
            mandatory=True,
            alias="Browse projects",
        ),
        ProviderScope(
            name="CREATE_ISSUES",
            description="Create Jira Issues",
            mandatory=True,
            alias="Create issue",
        ),
        ProviderScope(
            name="CLOSE_ISSUES",
            description="Close Jira Issues",
            mandatory=False,
            alias="Close issues",
        ),
        ProviderScope(
            name="EDIT_ISSUES",
            description="Edit Jira Issues",
            mandatory=False,
            alias="Edit issues",
        ),
        ProviderScope(
            name="DELETE_ISSUES",
            description="Delete Jira Issues",
            mandatory=False,
            alias="Delete issues",
        ),
        ProviderScope(
            name="MODIFY_REPORTER",
            description="Modify Jira Issue Reporter",
            mandatory=False,
            alias="Modidy issue reporter",
        ),
    ]
    PROVIDER_TAGS = ["ticketing"]
    PROVIDER_DISPLAY_NAME = "Jira On-Prem"

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
        # Note: Jira On Prem does not support api/3
        resp = requests.get(
            f"{self.jira_host}/rest/api/2/myself",
            headers=headers,
            verify=False,
            timeout=10,
        )
        try:
            resp.raise_for_status()
        except Exception:
            scopes = {
                scope.name: "Failed to authenticate with Jira - wrong credentials"
                for scope in JiraonpremProvider.PROVIDER_SCOPES
            }
            return scopes

        params = {
            "permissions": ",".join(
                [scope.name for scope in JiraonpremProvider.PROVIDER_SCOPES]
            )
        }
        resp = requests.get(
            f"{self.jira_host}/rest/api/2/mypermissions",
            headers=headers,
            params=params,
            verify=False,
            timeout=10,
        )
        try:
            resp.raise_for_status()
        except Exception as e:
            scopes = {
                scope.name: f"Failed to authenticate with Jira: {e}"
                for scope in JiraonpremProvider.PROVIDER_SCOPES
            }
            return scopes
        permissions = resp.json().get("permissions", [])
        scopes = {
            scope: scope_result.get("havePermission", False)
            for scope, scope_result in permissions.items()
        }
        return scopes

    def validate_config(self):
        self.authentication_config = JiraonpremProviderAuthConfig(
            **self.config.authentication
        )

    @property
    def jira_host(self):
        # if not the first time, return the cached host
        if self._host:
            return self._host

        # if the user explicitly supplied a host with http/https, use it
        if self.authentication_config.host.startswith(
            "http://"
        ) or self.authentication_config.host.startswith("https://"):
            self._host = self.authentication_config.host
            return self.authentication_config.host

        # otherwise, try to use https:
        try:
            requests.get(
                f"https://{self.authentication_config.host}", verify=False, timeout=10
            )
            self.logger.debug("Using https")
            self._host = f"https://{self.authentication_config.host}"
            return self._host
        except requests.exceptions.SSLError:
            self.logger.debug("Using http")
            self._host = f"http://{self.authentication_config.host}"
            return self._host
        # should happen only if the user supplied invalid host, so just let validate_config fail
        except Exception:
            return self.authentication_config.host

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def __get_url(self, paths: List[str] = [], query_params: dict = None, **kwargs):
        """
        Helper method to build the url for jira api requests.

        Example:

        paths = ["issue", "createmeta"]
        query_params = {"projectKeys": "key1"}
        url = __get_url("test", paths, query_params)

        # url = https://test.atlassian.net/rest/api/2/issue/createmeta?projectKeys=key1
        """
        # add url path

        url = urljoin(
            f"{self.jira_host}/rest/api/2/",
            "/".join(str(path) for path in paths),
        )

        # add query params
        if query_params:
            url = f"{url}?{urlencode(query_params)}"

        return url

    def __get_auth_header(self):
        """
        Helper method to build the auth payload for jira api requests.
        """
        return {
            "Authorization": f"Bearer {self.authentication_config.personal_access_token}"
        }

    def __get_createmeta(self, project_key: str):
        try:
            self.logger.info("Fetching create meta data...")

            url = self.__get_url(
                paths=["issue", "createmeta"],
                query_params={"projectKeys": project_key},
            )
            headers = self.__get_auth_header()
            response = requests.get(url=url, headers=headers, verify=False, timeout=10)

            response.raise_for_status()

            self.logger.info("Fetched create meta data!")

            return response.json()
        except Exception as e:
            raise ProviderException(f"Failed to fetch createmeta: {e}")

    def __get_single_createmeta(self, project_key: str):
        """
        Helper method to get single createmeta. As the original createmeta api returns
        multiple issue types and other config.
        """
        try:
            self.logger.info("Fetching single createmeta...")

            createmeta = self.__get_createmeta(project_key)

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
        project_key: str,
        summary: str,
        description: str = "",
        issue_type: str = "",
        labels: List[str] = None,
        components: List[str] = None,
        custom_fields: dict = None,
        priority: str = "Medium",
        **kwargs: dict,
    ):
        """
        Helper method to create an issue in jira.
        """
        try:
            self.logger.info("Creating an issue...")

            if not issue_type:
                create_meta = self.__get_single_createmeta(project_key=project_key)
                issue_type = create_meta.get("issue_type_name", "")

            url = self.__get_url(paths=["issue"])

            fields = {
                "summary": summary,
                "description": description,
                "project": {"key": project_key},
                "issuetype": {"name": issue_type},
                "priority": {"name": priority},
            }

            if labels:
                fields["labels"] = labels

            if components:
                fields["components"] = [{"name": component} for component in components]

            if custom_fields:
                fields.update(custom_fields)

            request_body = {"fields": fields}

            response = requests.post(
                url=url,
                json=request_body,
                headers=self.__get_auth_header(),
                verify=False,
                timeout=10,
            )
            try:
                response.raise_for_status()
            except Exception:
                self.logger.exception(
                    "Failed to create an issue", extra=response.json()
                )
                raise ProviderException(f"Failed to create an issue: {response.json()}")
            self.logger.info("Created an issue!")

            return {"issue": response.json()}
        except Exception as e:
            raise ProviderException(f"Failed to create an issue: {e}")

    def __update_issue(
        self,
        issue_id: str,
        summary: str = "",
        description: str = "",
        priority: str = "Medium",
        labels: List[str] = None,
        components: List[str] = None,
        custom_fields: dict = None,
        **kwargs: dict,
    ):
        """
        Helper method to update an issue in jira.
        """
        try:
            self.logger.info("Updating an issue...")

            url = self.__get_url(paths=["issue", issue_id])

            update = {}

            if summary:
                update["summary"] = [{"set": summary}]

            if description:
                update["description"] = [{"set": description}]

            if priority:
                update["priority"] = [{"set": {"name": priority}}]

            if components:
                update["components"] = [
                    {"set": [{"name": component} for component in components]}
                ]

            if labels:
                update["labels"] = [{"set": label} for label in labels]

            if custom_fields:
                update.update(custom_fields)

            request_body = {"update": update}

            response = requests.put(
                url=url,
                json=request_body,
                headers=self.__get_auth_header(),
                verify=False,
                timeout=10,
            )

            try:
                if response.status_code != 204:
                    response.raise_for_status()
            except Exception:
                self.logger.exception("Failed to update an issue", extra=response.text)
                raise ProviderException("Failed to update an issue")

            result = {
                "issue": {
                    "id": issue_id,
                    "key": self._extract_issue_key_from_issue_id(issue_id),
                    "self": self.__get_url(paths=["issue", issue_id]),
                }
            }

            self.logger.info("Updated an issue!")
            return result

        except Exception as e:
            raise ProviderException(f"Failed to update an issue: {e}")

    def _extract_project_key_from_board_name(self, board_name: str):
        headers = {
            "Accept": "application/json",
        }
        headers.update(self.__get_auth_header())

        boards_response = requests.get(
            f"{self.jira_host}/rest/agile/1.0/board",
            headers=headers,
            verify=False,
            timeout=10,
        )
        if boards_response.status_code == 200:
            boards = boards_response.json()["values"]
            for board in boards:
                if board["name"].lower() == board_name.lower():
                    # Jira On Prem does not have the "location" in its response so we need to figure it out
                    board_id = board["id"]
                    # get the filter
                    board_configuration = requests.get(
                        f"{self.jira_host}/rest/agile/1.0/board/{board_id}/configuration",
                        headers=headers,
                        verify=False,
                        timeout=10,
                    )
                    if board_configuration.status_code != 200:
                        raise Exception(
                            f"Could not fetch board configuration for board {board_name}"
                        )
                    # get the filter id
                    filter_id = board_configuration.json()["filter"]["id"]
                    # get the filter
                    filter_response = requests.get(
                        f"{self.jira_host}/rest/api/2/filter/{filter_id}",
                        headers=headers,
                        verify=False,
                        timeout=10,
                    )
                    if filter_response.status_code != 200:
                        raise Exception(
                            f"Could not fetch filter for board {board_name}"
                        )
                    # get the project key
                    # todo: should be more robust way but that's enough for now. note that the user can use projectKey directly
                    project_key = (
                        filter_response.json()["jql"]
                        .split("project = ")[1]
                        .split(" ")[0]
                    )
                    self.logger.info(
                        f"Found board {board_name} with project key {project_key}"
                    )
                    return project_key

            # if we got here, we didn't find the board name so let's throw an indicative exception
            board_names = [board["name"] for board in boards]
            raise Exception(
                f"Could not find board {board_name} - please verify your board name is in this list: {board_names}."
            )
        else:
            raise Exception("Could not fetch boards: " + boards_response.text)

    def _extract_issue_key_from_issue_id(self, issue_id: str):
        headers = {
            "Accept": "application/json",
        }
        headers.update(self.__get_auth_header())

        issue_key = requests.get(
            f"{self.jira_host}/rest/api/2/issue/{issue_id}",
            headers=headers,
            verify=False,
            timeout=10,
        )

        if issue_key.status_code == 200:
            return issue_key.json()["key"]
        else:
            raise Exception("Could not fetch issue key: " + issue_key.text)

    def _notify(
        self,
        summary: str,
        description: str = "",
        issue_type: str = "",
        project_key: str = "",
        board_name: str = "",
        issue_id: str = None,
        labels: List[str] = None,
        components: List[str] = None,
        custom_fields: dict = None,
        priority: str = "Medium",
        **kwargs: dict,
    ):
        """
        Notify jira by creating an issue.
        """
        # if the user didn't provider a project_key, try to extract it from the board name
        issue_type = issue_type if issue_type else kwargs.get("issuetype", "Task")
        if labels and isinstance(labels, str):
            labels = json.loads(labels.replace("'", '"'))
        try:
            self.logger.info("Notifying jira...")

            if issue_id:
                result = self.__update_issue(
                    issue_id=issue_id,
                    summary=summary,
                    description=description,
                    labels=labels,
                    components=components,
                    custom_fields=custom_fields,
                    priority=priority,
                    **kwargs,
                )

                issue_key = self._extract_issue_key_from_issue_id(issue_id)

                result["ticket_url"] = f"{self.jira_host}/browse/{issue_key}"

                self.logger.info("Updated a jira issue: " + str(result))
                return result

            if not project_key:
                project_key = self._extract_project_key_from_board_name(board_name)
            if not project_key or not summary or not issue_type or not description:
                raise ProviderException(
                    f"Project key and summary are required! - {project_key}, {summary}, {issue_type}, {description}"
                )

            result = self.__create_issue(
                project_key=project_key,
                summary=summary,
                description=description,
                issue_type=issue_type,
                labels=labels,
                components=components,
                custom_fields=custom_fields,
                priority=priority,
                **kwargs,
            )
            result["ticket_url"] = f"{self.jira_host}/browse/{result['issue']['key']}"
            self.logger.info("Notified jira!")

            return result
        except Exception as e:
            context = {
                "summary": summary,
                "description": description,
                "issue_type": issue_type,
                "project_key": project_key,
            }
            raise ProviderException(f"Failed to notify jira: {e} - Params: {context}")

    def _query(self, ticket_id="", board_id="", **kwargs: dict):
        """
        API for fetching issues:
        https://developer.atlassian.com/cloud/jira/software/rest/api-group-board/#api-rest-agile-1-0-board-boardid-issue-get

        Args:
            kwargs (dict): The providers with context
        """
        if not ticket_id:
            request_url = (
                f"https://{self.jira_host}/rest/agile/1.0/board/{board_id}/issue"
            )
            response = requests.get(
                request_url, headers=self.__get_auth_header(), verify=False, timeout=10
            )
            if not response.ok:
                raise ProviderException(
                    f"{self.__class__.__name__} failed to fetch data from Jira: {response.text}"
                )
            issues = response.json()
            return {"number_of_issues": issues["total"]}
        else:
            request_url = self.__get_url(paths=["issue", ticket_id])
            response = requests.get(
                request_url, headers=self.__get_auth_header(), verify=False, timeout=10
            )
            if not response.ok:
                raise ProviderException(
                    f"{self.__class__.__name__} failed to fetch data from Jira: {response.text}"
                )
            issue = response.json()
            return {"issue": issue}


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

    jira_pat = os.environ.get("JIRA_PAT")
    jira_host = os.environ.get("JIRA_HOST")

    # Initalize the provider and provider config
    config = ProviderConfig(
        description="Jira On Prem Provider",
        authentication={
            "personal_access_token": jira_pat,
            "host": jira_host,
        },
    )
    provider = JiraonpremProvider(context_manager, provider_id="jira", config=config)
    scopes = provider.validate_scopes()
    # Create ticket
    provider.notify(
        board_name="KEEP board",
        issue_type="Task",
        summary="Test Alert",
        description="Test Alert Description",
    )
