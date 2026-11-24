"""
JiracloudProvider is a class that implements the BaseProvider interface for Jira updates.
"""

import dataclasses
import json
from typing import List, Optional
from urllib.parse import urlencode, urljoin

import pydantic
import requests
from requests.auth import HTTPBasicAuth

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.validation.fields import HttpsUrl


@pydantic.dataclasses.dataclass
class JiraProviderAuthConfig:
    """Jira Cloud authentication configuration."""

    email: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Atlassian Jira Email",
            "sensitive": False,
            "documentation_url": "https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/#Create-an-API-token",
        }
    )

    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Atlassian Jira API Token",
            "sensitive": True,
            "documentation_url": "https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/#Create-an-API-token",
        }
    )
    host: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Atlassian Jira Host",
            "sensitive": False,
            "documentation_url": "https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/#Create-an-API-token",
            "hint": "https://keephq.atlassian.net",
            "validation": "https_url",
        }
    )

    ticket_creation_url: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "URL for creating new tickets (optional, will use default if not provided)",
            "sensitive": False,
            "hint": "https://keephq.atlassian.net/secure/CreateIssue.jspa",
        },
        default="",
    )


class JiraProvider(BaseProvider):
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
        ProviderScope(
            name="TRANSITION_ISSUES",
            description="Transition Jira Issues",
            mandatory=False,
            alias="Transition issues",
        ),
    ]
    PROVIDER_TAGS = ["ticketing"]
    PROVIDER_DISPLAY_NAME = "Jira Cloud"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._host = None

    def validate_scopes(self):
        """
        Validate that the provider has the required scopes.
        """

        headers = {"Accept": "application/json"}
        auth = requests.auth.HTTPBasicAuth(
            self.authentication_config.email, self.authentication_config.api_token
        )

        # first, validate user/api token are correct:
        resp = requests.get(
            f"{self.jira_host}/rest/api/3/myself",
            headers={"Accept": "application/json"},
            auth=auth,
            verify=False,
        )
        try:
            resp.raise_for_status()
        except Exception:
            scopes = {
                scope.name: "Failed to authenticate with Jira - wrong credentials"
                for scope in JiraProvider.PROVIDER_SCOPES
            }
            return scopes

        params = {
            "permissions": ",".join(
                [scope.name for scope in JiraProvider.PROVIDER_SCOPES]
            )
        }
        resp = requests.get(
            f"{self.jira_host}/rest/api/3/mypermissions",
            headers=headers,
            auth=auth,
            params=params,
            verify=False,
        )
        try:
            resp.raise_for_status()
        except Exception as e:
            scopes = {
                scope.name: f"Failed to authenticate with Jira: {e}"
                for scope in JiraProvider.PROVIDER_SCOPES
            }
            return scopes
        permissions = resp.json().get("permissions", [])
        scopes = {
            scope: scope_result.get("havePermission", False)
            for scope, scope_result in permissions.items()
        }
        return scopes

    def validate_config(self):
        self.authentication_config = JiraProviderAuthConfig(
            **self.config.authentication
        )

    @property
    def jira_host(self) -> str:
        if self._host is not None:
            return self._host
        host = (
            self.authentication_config.host
            if self.authentication_config.host.startswith("https://")
            or self.authentication_config.host.startswith("http://")
            else f"https://{self.authentication_config.host}"
        )
        self._host = host
        return self._host

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

    def __get_auth(self):
        """
        Helper method to build the auth payload for jira api requests.
        """
        return HTTPBasicAuth(
            self.authentication_config.email, self.authentication_config.api_token
        )

    def __get_createmeta(self, project_key: str):
        try:
            self.logger.info("Fetching create meta data...")

            url = self.__get_url(
                paths=["issue", "createmeta"],
                query_params={"projectKeys": project_key},
            )

            response = requests.get(url=url, auth=self.__get_auth(), verify=False)

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

    def __get_available_transitions(self, issue_id: str):
        """
        Get available transitions for an issue.

        Args:
            issue_id: The Jira issue ID or key

        Returns:
            List of available transitions with their IDs and names
        """
        try:
            self.logger.info(f"Fetching available transitions for issue {issue_id}...")

            url = self.__get_url(paths=["issue", issue_id, "transitions"])

            response = requests.get(url=url, auth=self.__get_auth(), verify=False)
            response.raise_for_status()

            transitions = response.json().get("transitions", [])

            self.logger.info(
                f"Found {len(transitions)} available transitions for issue {issue_id}"
            )

            return transitions
        except Exception as e:
            raise ProviderException(
                f"Failed to fetch transitions for issue {issue_id}: {e}"
            )

    def __transition_issue(
            self, issue_id: str, transition_name: Optional[str] = None, transition_id: Optional[str] = None
    ):
        """
        Transition an issue to a new status.

        Args:
            issue_id: The Jira issue ID or key
            transition_name: Name of the transition (e.g., "Done", "Resolved", "In Progress")
            transition_id: Direct transition ID (if known, skips lookup)

        Returns:
            dict with transition result
        """
        try:
            self.logger.info(f"Transitioning issue {issue_id}...")

            # If transition_id is not provided, look it up by name
            if not transition_id:
                if not transition_name:
                    raise ProviderException(
                        "Either transition_name or transition_id must be provided"
                    )

                transitions = self.__get_available_transitions(issue_id)

                # Find transition by name (case-insensitive)
                transition_id = None
                for transition in transitions:
                    if transition["name"].lower() == transition_name.lower():
                        transition_id = transition["id"]
                        self.logger.info(
                            f"Found transition '{transition_name}' with ID {transition_id}"
                        )
                        break

                if not transition_id:
                    available_names = [t["name"] for t in transitions]
                    raise ProviderException(
                        f"Transition '{transition_name}' not found. "
                        f"Available transitions: {', '.join(available_names)}"
                    )

            # Execute the transition
            url = self.__get_url(paths=["issue", issue_id, "transitions"])

            request_body = {"transition": {"id": transition_id}}

            response = requests.post(
                url=url, json=request_body, auth=self.__get_auth(), verify=False
            )

            if response.status_code != 204:
                response.raise_for_status()

            self.logger.info(f"Successfully transitioned issue {issue_id}!")

            return {
                "issue_id": issue_id,
                "transition_id": transition_id,
                "transition_name": transition_name,
                "success": True,
            }

        except Exception as e:
            raise ProviderException(f"Failed to transition issue {issue_id}: {e}")

    def __create_issue(
        self,
        project_key: str,
        summary: str,
        description: str = "",
        issue_type: str = "",
        labels: List[str] = None,
        components: List[str] = None,
        custom_fields: dict = None,
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
            }

            if labels:
                fields["labels"] = labels

            if components:
                fields["components"] = [{"name": component} for component in components]

            if custom_fields:
                # Filter out priority field if it's set to "none" or empty
                filtered_fields = {}
                for key, value in custom_fields.items():
                    if key == "priority" and (not value or str(value).lower() in ["none", "", "null"]):
                        self.logger.info(f"Skipping priority field with value '{value}' as it may not be available on the issue screen")
                        continue
                    filtered_fields[key] = value
                fields.update(filtered_fields)
            
            # Also handle priority that might come through kwargs
            # Filter out Keep-internal workflow fields that should not be passed to Jira API
            if kwargs:
                # Keep-internal fields that are not valid Jira fields
                keep_internal_fields = {
                    "enrich_alert",
                    "enrich_incident",
                    "dispose_on_new_alert",
                    "audit_enabled",
                    "if",
                    "name",
                    "condition",
                    "foreach",
                    "throttle",
                    "provider",
                }
                filtered_kwargs = {}
                for key, value in kwargs.items():
                    # Skip Keep-internal fields
                    if key in keep_internal_fields:
                        self.logger.debug(f"Skipping Keep-internal field '{key}' - not a valid Jira field")
                        continue
                    if key == "priority" and (not value or str(value).lower() in ["none", "", "null"]):
                        self.logger.info(f"Skipping priority field from kwargs with value '{value}' as it may not be available on the issue screen")
                        continue
                    filtered_kwargs[key] = value
                fields.update(filtered_kwargs)

            request_body = {"fields": fields}

            response = requests.post(
                url=url, json=request_body, auth=self.__get_auth(), verify=False
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
        summary: str,
        description: str = "",
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

            if components:
                update["components"] = [{"set": component} for component in components]

            if labels:
                update["labels"] = [{"set": label} for label in labels]

            if custom_fields:
                # Format custom fields properly for Jira API
                for field_name, field_value in custom_fields.items():
                    update[field_name] = [{"set": field_value}]

            request_body = {"update": update}

            response = requests.put(
                url=url, json=request_body, auth=self.__get_auth(), verify=False
            )

            try:
                if response.status_code != 204:
                    response.raise_for_status()
            except Exception:
                self.logger.exception("Failed to update an issue", extra=response.text)
                raise ProviderException("Failed to update an issue")
            self.logger.info("Updated an issue!")
            return {
                "issue": {
                    "id": issue_id,
                    "key": self._extract_issue_key_from_issue_id(issue_id),
                    "self": self.__get_url(paths=["issue", issue_id]),
                }
            }

        except Exception as e:
            raise ProviderException(f"Failed to update an issue: {e}")

    def _extract_project_key_from_board_name(self, board_name: str):
        boards_response = requests.get(
            f"{self.jira_host}/rest/agile/1.0/board",
            auth=self.__get_auth(),
            headers={"Accept": "application/json"},
            verify=False,
        )
        if boards_response.status_code == 200:
            boards = boards_response.json()["values"]
            for board in boards:
                if board["name"].lower() == board_name.lower():
                    self.logger.info(
                        f"Found board {board_name} with project key {board['location']['projectKey']}"
                    )
                    return board["location"]["projectKey"]

            # if we got here, we didn't find the board name so let's throw an indicative exception
            board_names = [board["name"] for board in boards]
            raise Exception(
                f"Could not find board {board_name} - please verify your board name is in this list: {board_names}."
            )
        else:
            raise Exception("Could not fetch boards: " + boards_response.text)

    def _extract_issue_key_from_issue_id(self, issue_id: str):
        issue_key = requests.get(
            f"{self.jira_host}/rest/api/2/issue/{issue_id}",
            auth=self.__get_auth(),
            headers={"Accept": "application/json"},
            verify=False,
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
        transition_to: Optional[str] = None,
        **kwargs: dict,
    ):
        """
        Notify jira by creating an issue.
        Args:
            summary (str): The summary of the issue.
            description (str): The description of the issue.
            issue_type (str): The type of the issue.
            project_key (str): The project key of the issue.
            board_name (str): The board name of the issue.
            issue_id (str): The issue id of the issue.
            labels (List[str]): The labels of the issue.
            components (List[str]): The components of the issue.
            custom_fields (dict): The custom fields of the issue.
            transition_to (str): Optional transition name (e.g., "Done", "Resolved") to apply after update/create.
        """
        issue_type = (
            issue_type
            if issue_type
            else (
                kwargs.get("issuetype", "Task") if isinstance(kwargs, dict) else "Task"
            )
        )
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
                    **kwargs,
                )

                issue_key = self._extract_issue_key_from_issue_id(issue_id)

                result["ticket_url"] = f"{self.jira_host}/browse/{issue_key}"

                # Apply transition if requested
                if transition_to:
                    self.logger.info(f"Applying transition '{transition_to}' to issue {issue_id}")
                    transition_result = self.__transition_issue(
                        issue_id=issue_id, transition_name=transition_to
                    )
                    result["transition"] = transition_result

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
                **kwargs,
            )
            result["ticket_url"] = f"{self.jira_host}/browse/{result['issue']['key']}"

            # Apply transition if requested (on newly created issue)
            if transition_to:
                created_issue_id = result["issue"]["key"]
                self.logger.info(f"Applying transition '{transition_to}' to newly created issue {created_issue_id}")
                transition_result = self.__transition_issue(
                    issue_id=created_issue_id, transition_name=transition_to
                )
                result["transition"] = transition_result

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
            ticket_id (str): The ticket id of the issue, optional.
            board_id (str): The board id of the issue.
        """
        if not ticket_id:
            request_url = f"{self.jira_host}/rest/agile/1.0/board/{board_id}/issue"
            response = requests.get(request_url, auth=self.__get_auth(), verify=False)
            if not response.ok:
                raise ProviderException(
                    f"{self.__class__.__name__} failed to fetch data from Jira: {response.text}"
                )
            issues = response.json()
            return {"number_of_issues": issues["total"]}
        else:
            request_url = self.__get_url(paths=["issue", ticket_id])
            response = requests.get(request_url, auth=self.__get_auth(), verify=False)
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

    jira_api_token = os.environ.get("JIRA_API_TOKEN")
    jira_email = os.environ.get("JIRA_EMAIL")
    jira_host = os.environ.get("JIRA_HOST")

    # Initalize the provider and provider config
    config = ProviderConfig(
        description="Jira Input Provider",
        authentication={
            "api_token": jira_api_token,
            "email": jira_email,
            "host": jira_host,
        },
    )
    provider = JiraProvider(context_manager, provider_id="jira", config=config)
    scopes = provider.validate_scopes()

    # Example 1: Create ticket
    result = provider.notify(
        board_name="ALERTS",
        issue_type="Task",
        summary="Test",
        description="Test",
    )

    # Example 2: Update ticket and transition to Done
    provider.notify(
        issue_id=result["issue"]["key"],
        summary="Test Alert - Updated",
        description="Alert has been resolved",
        transition_to="Done"
    )