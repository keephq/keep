"""
SentryProvider is a class that provides a way to read data from Sentry.
"""
import dataclasses

import pydantic
import requests

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class SentryProviderAuthConfig:
    """Sentry authentication configuration."""

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Sentry Api Key",
            "sensitive": True,
            "hint": "https://docs.sentry.io/product/integrations/integration-platform/internal-integration/",
        }
    )
    organization_slug: str = dataclasses.field(
        metadata={"required": True, "description": "Sentry organization slug"}
    )
    project_slug: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Sentry project slug within the organization",
            "hint": "If you want to connect sentry to a specific project within an organization",
        },
        default=None,
    )


class SentryProvider(BaseProvider):
    SENTRY_API = "https://sentry.io/api/0"
    PROVIDER_SCOPES = [
        ProviderScope(
            "event:read",
            description="Read events and issues",
            mandatory=True,
            documentation_url="https://docs.sentry.io/api/events/list-a-projects-issues/?original_referrer=https%3A%2F%2Fdocs.sentry.io%2Fapi%2F",
        ),
        ProviderScope(
            "project:read",
            description="Read projects in organization",
            mandatory=True,
            documentation_url="https://docs.sentry.io/api/projects/list-your-projects/?original_referrer=https%3A%2F%2Fdocs.sentry.io%2Fapi%2F",
        ),
        ProviderScope(
            "project:write",
            description="Write permission for projects in organization",
            mandatory=False,
            mandatory_for_webhook=True,
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.sentry_org_slug = self.config.authentication.get("organization_slug")
        self.project_slug = self.config.authentication.get("project_slug")

    def get_events_url(self, project, date="14d"):
        return f"{self.SENTRY_API}/organizations/{self.sentry_org_slug}/events/?field=title&field=event.type&field=project&field=user.display&field=timestamp&field=replayId&per_page=50 \
                                  &query={project}&referrer=api.discover.query-table&sort=-timestamp&statsPeriod={date}"

    def dispose(self):
        return

    def validate_config(self):
        """Validates required configuration for Sentry's provider."""
        self.authentication_config = SentryProviderAuthConfig(
            **self.config.authentication
        )

    def _query(self, query: str, **kwargs: dict):
        """
        Query Sentry using the given query

        Args:
            query (str): query to execute

        Returns:
            list[tuple] | list[dict]: results of the query
        """
        headers = {
            "Authorization": f"Bearer {self.config.authentication['api_token']}",
        }
        time = kwargs.get("time", "14d")
        project = kwargs.get("project")

        params = {"limit": 100}
        response = requests.get(
            self.get_events_url(project, time), headers=headers, params=params
        )
        response.raise_for_status()

        events = response.json()
        return events.get("data")  # returns a list of events

    def get_template(self):
        pass

    def get_parameters(self):
        return {}

    def validate_scopes(self) -> dict[str, bool | str]:
        validated_scopes = {}
        project_slug = None
        for scope in self.PROVIDER_SCOPES:
            if scope.name == "event:read":
                if self.project_slug:
                    response = requests.get(
                        f"{self.SENTRY_API}/projects/{self.sentry_org_slug}/{self.project_slug}/issues/",
                        headers={
                            "Authorization": f"Bearer {self.authentication_config.api_key}"
                        },
                    )
                    if not response.ok:
                        response_json = response.json()
                        validated_scopes[scope.name] = response_json.get("detail")
                        continue
                else:
                    projects_response = requests.get(
                        f"{self.SENTRY_API}/projects/",
                        headers={
                            "Authorization": f"Bearer {self.authentication_config.api_key}"
                        },
                    )
                    if not projects_response.ok:
                        response_json = projects_response.json()
                        validated_scopes[scope.name] = response_json.get("detail")
                        continue
                    projects = projects_response.json()
                    project_slug = projects[0].get("slug")
                    response = requests.get(
                        f"{self.SENTRY_API}/projects/{self.sentry_org_slug}/{project_slug}/issues/",
                        headers={
                            "Authorization": f"Bearer {self.authentication_config.api_key}"
                        },
                    )
                    if not response.ok:
                        response_json = response.json()
                        validated_scopes[scope.name] = response_json.get("detail")
                        continue
                validated_scopes[scope.name] = True
            elif scope.name == "project:read":
                response = requests.get(
                    f"{self.SENTRY_API}/projects/",
                    headers={
                        "Authorization": f"Bearer {self.authentication_config.api_key}"
                    },
                )
                if not response.ok:
                    response_json = response.json()
                    validated_scopes[scope.name] = response_json.get("detail")
                    continue
                validated_scopes[scope.name] = True
            elif scope.name == "project:write":
                response = requests.post(
                    f"{self.SENTRY_API}/projects/{self.sentry_org_slug}/{self.project_slug or project_slug}/plugins/webhooks/",
                    headers={
                        "Authorization": f"Bearer {self.authentication_config.api_key}"
                    },
                )
                if not response.ok:
                    response_json = response.json()
                    validated_scopes[scope.name] = response_json.get("detail")
                    continue
                validated_scopes[scope.name] = True
        return validated_scopes

    @staticmethod
    def format_alert(event: dict) -> AlertDto | list[AlertDto]:
        print(event)

    def get_alerts(self, project_slug: str = None) -> list[AlertDto]:
        # get issues
        all_issues = []
        if self.authentication_config.project_slug or project_slug:
            response = requests.get(
                f"{self.SENTRY_API}/projects/{self.sentry_org_slug}/{self.project_slug or project_slug}/issues/",
                headers={
                    "Authorization": f"Bearer {self.authentication_config.api_key}"
                },
            )
            if not response.ok:
                raise Exception(response.json())
            all_issues = response.json()
            if project_slug:
                return all_issues
        else:
            projects_response = requests.get(
                f"{self.SENTRY_API}/projects/",
                headers={
                    "Authorization": f"Bearer {self.authentication_config.api_key}"
                },
            )
            if not projects_response.ok:
                raise Exception("Failed to get projects")
            projects = projects_response.json()
            for project in projects:
                all_issues.extend(self.get_alerts(project.get("slug")))

        # format issues
        formatted_issues = []
        for issue in all_issues:
            formatted_issues.append(
                AlertDto(
                    id=issue.pop("id"),
                    name=issue.pop("title"),
                    status=issue.pop("status"),
                    lastReceived=issue.pop("lastSeen"),
                    environment=issue.get("metadata", {}).get("filename"),
                    service=issue.get("metadata", {}).get("function"),
                    description=issue.pop("metadata", {}).get("value"),
                    url=issue.pop("permalink"),
                    source=["sentry"],
                    **issue,
                )
            )
        return formatted_issues


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

    sentry_api_token = os.environ.get("SENTRY_API_TOKEN")
    sentry_org_slug = os.environ.get("SENTRY_ORG_SLUG")
    sentry_project = "python"

    config = {
        "id": "sentry-prod",
        "authentication": {"api_token": sentry_api_token, "org_slug": sentry_org_slug},
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_type="sentry",
        provider_config=config,
        project=sentry_project,
    )
    result = provider.query("")
    print(result)
