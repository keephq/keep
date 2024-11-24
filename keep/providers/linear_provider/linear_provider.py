import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class LinearProviderAuthConfig:
    """Linear authentication configuration."""

    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Linear API Token",
            "sensitive": True,
        }
    )


class LinearProvider(BaseProvider):
    """Enrich alerts with Linear tickets."""

    PROVIDER_DISPLAY_NAME = "Linear"
    LINEAR_GRAPHQL_URL = "https://api.linear.app/graphql"
    PROVIDER_CATEGORY = ["Ticketing"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = LinearProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def __query_linear_projects(self, team_name=""):
        """Helper method to fetch the linear projects by team."""

        try:
            self.logger.info(f"Fetching projects for linear team:{team_name}...")

            query = f"""
                query {{
                    teams(filter: {{name: {{eq: "{team_name}"}}}}) {{
                        nodes {{
                            id
                            name
                            projects {{
                                nodes {{
                                    id
                                    name
                                }}
                            }}
                        }}
                    }}
                }}
            """

            response = requests.post(
                url=self.LINEAR_GRAPHQL_URL,
                json={"query": query},
                headers=self.__headers,
            )

            response.raise_for_status()

            data: dict = response.json().get("data")
            if data is None:
                # if data is None the response.json() has error details
                raise ProviderException(response.json())

            team_nodes = data.get("teams", {}).get("nodes", [])
            # note: "team_name" are unique, so it's ok to select the first team node
            team_node = team_nodes[0] if len(team_nodes) > 0 else {}

            projects = team_node.get("projects", {}).get("nodes", [])

            self.logger.info(f"Fetched projects for linear team:{team_name}!")

            return {"projects": projects}
        except Exception as e:
            raise ProviderException(f"Failed to fetch linear projects: {e}")

    def __query_linear_data(self, team_name="", project_name=""):
        """Helper method to fetch the linear team and project data."""

        try:
            self.logger.info(
                f"Fetching linear data for team: {team_name} and project: {project_name}..."
            )

            query = f"""
                    query {{
                        teams(filter: {{name: {{eq: "{team_name}"}}}}) {{
                            nodes {{
                                id
                                name
                                projects(filter: {{ name: {{ eq: "{project_name}" }} }}) {{
                                    nodes {{
                                        id
                                        name
                                    }}
                                }}
                            }}
                        }}
                    }}
                """

            response = requests.post(
                url=self.LINEAR_GRAPHQL_URL,
                json={"query": query},
                headers=self.__headers,
            )

            response.raise_for_status()

            data: dict = response.json().get("data")
            if data is None:
                # if data is None the response.json() has error details
                raise ProviderException(response.json())

            team_nodes = data.get("teams", {}).get("nodes", [])
            # note: "team_name" are unique, so it's ok to select the first team node
            team_node = team_nodes[0] if len(team_nodes) > 0 else {}
            team_id = team_node.get("id", "")

            project_nodes = team_node.get("projects", {}).get("nodes", [])
            # note: there can be multiple projects with same "project_name", so we select the first
            project_node = project_nodes[0] if len(project_nodes) > 0 else {}
            project_id = project_node.get("id", "")

            if project_id == "" or team_id == "":
                raise ProviderException(
                    f"Linear team:{team_name} or project:{project_name}, doesn't exists"
                )

            self.logger.info(
                f"Fetched linear data for team: {team_name} and project: {project_name}!"
            )

            return {"project_id": project_id, "team_id": team_id}
        except Exception as e:
            self.logger.error(e)
            raise ProviderException(
                f"Failed to fetch linear data for team:{team_name}, project:{project_name} : {e}"
            )

    def __create_issue(
        self,
        team_name="",
        project_name="",
        title="",
        description="",
        priority=0,
        **kwargs: dict,
    ):
        """
        Create an issue inside a linear project for given team.
        """
        try:
            self.logger.info(f"Creating an issue with title:{title} ...")

            linear_data = self.__query_linear_data(
                team_name=team_name, project_name=project_name
            )

            query = f"""
                mutation {{
                    issueCreate(
                        input: {{
                            title: "{title}"
                            description: "{description}"
                            priority: {priority}
                            teamId: "{linear_data["team_id"]}"
                            projectId: "{linear_data["project_id"]}"
                        }}
                    ) {{
                        success
                        issue {{
                            id
                            title
                        }}
                    }}
                }}
            """

            response = requests.post(
                url=self.LINEAR_GRAPHQL_URL,
                json={"query": query},
                headers=self.__headers,
            )

            response.raise_for_status()

            data: dict = response.json().get("data")

            if data is None:
                raise ProviderException(response.json())

            issue = data.get("issueCreate", {}).get("issue", {})

            self.logger.info(f"Created an issue with title:{title} !")

            return {"issue": issue}
        except Exception as e:
            raise ProviderException(f"Failed to create an issue in linear: {e}")

    def _notify(
        self,
        team_name: str,
        project_name: str,
        title: str,
        description="",
        priority=0,
        **kwargs: dict,
    ):
        """
        Notify linear by creating an issue.
        """
        try:
            self.logger.info("Notifying linear...")

            result = self.__create_issue(
                team_name=team_name,
                project_name=project_name,
                title=title,
                description=description,
                priority=priority,
            )

            self.logger.info("Notified linear!")

            return result
        except Exception as e:
            raise ProviderException(f"Failed to notify linear: {e}")

    def _query(self, team_name: str, **kwargs: dict):
        """
        Query linear data for given team.
        """
        try:
            self.logger.info("Querying from linear...")

            result = self.__query_linear_projects(team_name=team_name)

            self.logger.info("Queried from linear!")

            return result
        except Exception as e:
            raise ProviderException(f"Failed to query linear: {e}")


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

    linear_api_token = os.environ.get("LINEAR_API_TOKEN")
    linear_project_id = os.environ.get("LINEAR_PROJECT_ID")

    # Initialize the provider and provider config
    config = ProviderConfig(
        description="Linear Input Provider",
        authentication={
            "api_token": linear_api_token,
            "project_id": linear_project_id,
        },
    )
    provider = LinearProvider(context_manager, provider_id="linear", config=config)
    provider.query(team_name="Keep")
    provider.notify(
        team_name="Keep",
        project_name="keep",
        title="ISSUE1",
        description="some description",
        priority=2,
    )
