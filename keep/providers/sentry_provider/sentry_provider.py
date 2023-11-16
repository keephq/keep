"""
SentryProvider is a class that provides a way to read data from Sentry.
"""
import dataclasses
import datetime

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
    """Enrich alerts with data from Sentry."""

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
    DEFAULT_TIMEOUT = 600

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.sentry_org_slug = self.config.authentication.get("organization_slug")
        self.project_slug = self.config.authentication.get("project_slug")

    @property
    def __headers(self) -> dict:
        return {"Authorization": f"Bearer {self.authentication_config.api_key}"}

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

    def _query(self, project: str, time: str = "14d", **kwargs: dict):
        """
        Query Sentry using the given query

        Returns:
            list[tuple] | list[dict]: results of the query
        """
        headers = {
            "Authorization": f"Bearer {self.config.authentication['api_token']}",
        }

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
                        headers=self.__headers,
                    )
                    if not response.ok:
                        response_json = response.json()
                        validated_scopes[scope.name] = response_json.get("detail")
                        continue
                else:
                    projects_response = requests.get(
                        f"{self.SENTRY_API}/projects/",
                        headers=self.__headers,
                    )
                    if not projects_response.ok:
                        response_json = projects_response.json()
                        validated_scopes[scope.name] = response_json.get("detail")
                        continue
                    projects = projects_response.json()
                    project_slug = projects[0].get("slug")
                    response = requests.get(
                        f"{self.SENTRY_API}/projects/{self.sentry_org_slug}/{project_slug}/issues/",
                        headers=self.__headers,
                    )
                    if not response.ok:
                        response_json = response.json()
                        validated_scopes[scope.name] = response_json.get("detail")
                        continue
                validated_scopes[scope.name] = True
            elif scope.name == "project:read":
                response = requests.get(
                    f"{self.SENTRY_API}/projects/",
                    headers=self.__headers,
                )
                if not response.ok:
                    response_json = response.json()
                    validated_scopes[scope.name] = response_json.get("detail")
                    continue
                validated_scopes[scope.name] = True
            elif scope.name == "project:write":
                response = requests.post(
                    f"{self.SENTRY_API}/projects/{self.sentry_org_slug}/{self.project_slug or project_slug}/plugins/webhooks/",
                    headers=self.__headers,
                )
                if not response.ok:
                    response_json = response.json()
                    validated_scopes[scope.name] = response_json.get("detail")
                    continue
                validated_scopes[scope.name] = True
        return validated_scopes

    @staticmethod
    def format_alert(event: dict) -> AlertDto | list[AlertDto]:
        event_data: dict = event.get("event", {})
        tags_as_dict = {v[0]: v[1] for v in event_data.get("tags", [])}

        # Remove duplicate keys
        event_data.pop("id", None)
        tags_as_dict.pop("id", None)

        last_received = (
            datetime.datetime.fromtimestamp(event_data.get("received"))
            if "received" in event_data
            else event_data.get("datetime")
        )

        return AlertDto(
            id=event_data.pop("event_id"),
            name=event_data.get("title"),
            status=event.get("action", "triggered"),
            lastReceived=str(last_received),
            service=tags_as_dict.get("server_name"),
            source=["sentry"],
            environment=event_data.pop(
                "environment", tags_as_dict.pop("environment", "unknown")
            ),
            message=event_data.get("metadata", {}).get("value"),
            description=event.get("culprit", ""),
            pushed=True,
            severity=event.pop("level", tags_as_dict.get("level", "high")),
            url=event_data.pop("url", tags_as_dict.pop("url", None)),
            fingerprint=event.get("id"),
            tags=tags_as_dict,
        )

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        self.logger.info("Setting up Sentry webhook")
        # cannot install webhook with localhost
        if (
            "0.0.0.0" in keep_api_url
            or "127.0.0.1" in keep_api_url
            or "localhost" in keep_api_url
        ):
            raise ProviderConfigException(
                provider_id=self.provider_id,
                message="Cannot setup webhook with localhost, please use a public url",
            )

        if self.project_slug:
            project_slugs = [self.project_slug]
        else:
            # Get all projects if no project slug was given
            projects_response = requests.get(
                f"{self.SENTRY_API}/projects/",
                headers=self.__headers,
            )
            if not projects_response.ok:
                raise Exception("Failed to get projects")
            project_slugs = [
                project.get("slug") for project in projects_response.json()
            ]

        for project_slug in project_slugs:
            self.logger.info(f"Setting up webhook for project {project_slug}")
            webhooks_request = requests.get(
                f"{self.SENTRY_API}/projects/{self.sentry_org_slug}/{project_slug}/plugins/webhooks/",
                headers=self.__headers,
            )
            webhooks_request.raise_for_status()
            webhooks_response = webhooks_request.json()
            # Get existing urls so we won't override anything
            config = next(
                iter(
                    [
                        c
                        for c in webhooks_response.get("config")
                        if c.get("name") == "urls"
                    ]
                )
            )
            existing_webhooks_value: str = config.get("value", "") or ""
            existing_webhooks = existing_webhooks_value.split("\n")
            # tb: this is a resolution to a bug i pushed somewhere in the beginning of sentry provider
            #   TODO: remove this in the future
            if f"{keep_api_url}?api_key={api_key}" in existing_webhooks:
                existing_webhooks.remove(f"{keep_api_url}?api_key={api_key}")
            # This means we already installed in that project
            if f"{keep_api_url}&api_key={api_key}" in existing_webhooks:
                # TODO: we might got here but did not create the alert, we should fix that in the future
                #   e.g. make sure the alert exists and if not create it.
                self.logger.info(
                    f"Keep webhook already exists for project {project_slug}"
                )
                continue
            existing_webhooks.append(f"{keep_api_url}&api_key={api_key}")
            # Update the webhooks urls
            update_response = requests.put(
                f"{self.SENTRY_API}/projects/{self.sentry_org_slug}/{project_slug}/plugins/webhooks/",
                headers=self.__headers,
                json={"urls": "\n".join(existing_webhooks)},
            )
            update_response.raise_for_status()
            # Enable webhooks plugin for project
            requests.post(
                f"{self.SENTRY_API}/projects/{self.sentry_org_slug}/{project_slug}/plugins/webhooks/",
                headers=self.__headers,
            ).raise_for_status()
            # TODO: make sure keep alert does not exist and if it doesnt create it.
            alert_name = f"Keep Alert Rule - {project_slug}"
            alert_rules_response = requests.get(
                f"{self.SENTRY_API}/projects/{self.sentry_org_slug}/{project_slug}/rules/",
                headers=self.__headers,
            ).json()
            alert_exists = next(
                iter(
                    [
                        alert
                        for alert in alert_rules_response
                        if alert.get("name") == alert_name
                    ]
                ),
                None,
            )
            if not alert_exists:
                alert_payload = {
                    "conditions": [
                        {
                            "id": "sentry.rules.conditions.first_seen_event.FirstSeenEventCondition",
                        },
                        {
                            "id": "sentry.rules.conditions.regression_event.RegressionEventCondition",
                        },
                        {
                            "id": "sentry.rules.conditions.reappeared_event.ReappearedEventCondition",
                        },
                    ],
                    "filters": [],
                    "actions": [
                        {
                            "service": "webhooks",
                            "id": "sentry.rules.actions.notify_event_service.NotifyEventServiceAction",
                            "name": "Send a notification via webhooks",
                        },
                    ],
                    "actionMatch": "any",
                    "filterMatch": "any",
                    "frequency": 5,
                    "name": alert_name,
                    "dateCreated": "2023-10-09T13:40:37.144220Z",
                    "projects": [project_slug],
                    "status": "active",
                }

                requests.post(
                    f"{self.SENTRY_API}/projects/{self.sentry_org_slug}/{project_slug}/rules/",
                    headers=self.__headers,
                    json=alert_payload,
                ).raise_for_status()
                self.logger.info(f"Sentry webhook setup complete for {project_slug}")
            else:
                self.logger.info(f"Sentry webhook already exists for {project_slug}")
        self.logger.info("Sentry webhook setup complete")

    def __get_issues(self, project_slug: str) -> dict:
        """
        Get all issues for a project

        Args:
            project_slug (str): project slug

        Raises:
            Exception: if failed to get issues

        Returns:
            dict: issues by id
        """
        issues_response = requests.get(
            f"{self.SENTRY_API}/projects/{self.sentry_org_slug}/{project_slug}/issues/?query=*",
            headers=self.__headers,
        )
        if not issues_response.ok:
            raise Exception(issues_response.json())
        return {issue["id"]: issue for issue in issues_response.json()}

    def _get_alerts(self) -> list[AlertDto]:
        all_events_by_project = {}
        all_issues_by_project = {}
        if self.authentication_config.project_slug:
            response = requests.get(
                f"{self.SENTRY_API}/projects/{self.sentry_org_slug}/{self.project_slug}/events/",
                headers=self.__headers,
                timeout=SentryProvider.DEFAULT_TIMEOUT,
            )
            if not response.ok:
                raise Exception(response.json())
            all_events_by_project[self.project_slug] = response.json()
            all_issues_by_project[self.project_slug] = self.__get_issues(
                self.project_slug
            )
        else:
            projects_response = requests.get(
                f"{self.SENTRY_API}/projects/",
                headers=self.__headers,
                timeout=SentryProvider.DEFAULT_TIMEOUT,
            )
            if not projects_response.ok:
                raise Exception("Failed to get projects")
            projects = projects_response.json()
            for project in projects:
                project_slug = project.get("slug")
                response = requests.get(
                    f"{self.SENTRY_API}/projects/{self.sentry_org_slug}/{project_slug}/events/",
                    headers=self.__headers,
                    timeout=SentryProvider.DEFAULT_TIMEOUT,
                )
                if not response.ok:
                    error = response.json()
                    self.logger.warning(
                        "Failed to get events for project",
                        extra={"project_slug": project_slug, **error},
                    )
                    continue
                all_events_by_project[project_slug] = response.json()
                all_issues_by_project[project_slug] = self.__get_issues(project_slug)

        if not all_events_by_project:
            # We didn't manage to get any events for some reason
            self.logger.warning("Failed to get events from all projects")
            return []

        # format issues
        formatted_issues = []
        for project in all_events_by_project:
            for event in all_events_by_project[project]:
                id = event.pop("id")
                fingerprint = event.get("groupID")
                related_issue = all_issues_by_project.get(project, {}).get(
                    fingerprint, {}
                )
                tags = {tag["key"]: tag["value"] for tag in event.pop("tags", [])}
                last_received = datetime.datetime.fromisoformat(
                    event.get("dateCreated")
                ) + datetime.timedelta(minutes=1)
                formatted_issues.append(
                    AlertDto(
                        id=id,
                        name=event.pop("title"),
                        description=event.pop("culprit", ""),
                        message=event.get("message", ""),
                        status=related_issue.get(
                            "status", event.get("event.type", "unknown")
                        ),
                        lastReceived=last_received.isoformat(),
                        environment=tags.get("environment", "unknown"),
                        severity=tags.get("level", None),
                        url=event.pop("permalink", None),
                        project=project,
                        source=["sentry"],
                        fingerprint=fingerprint,
                        tags=tags,
                        payload=event,
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
