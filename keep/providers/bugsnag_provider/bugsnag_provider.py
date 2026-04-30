"""
BugsnagProvider is a class that allows to pull errors from Bugsnag and receive
webhook notifications when new exceptions are detected.
"""

import dataclasses
import datetime
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class BugsnagProviderAuthConfig:
    """
    BugsnagProviderAuthConfig holds the authentication configuration for Bugsnag.
    """

    personal_auth_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Bugsnag Personal Auth Token",
            "hint": "Generate at https://app.bugsnag.com/settings/my-account under 'Personal auth tokens'",
            "sensitive": True,
        },
    )
    organization_slug: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Bugsnag Organization Slug",
            "hint": "Found in your Bugsnag organization URL: bugsnag.com/organizations/<slug>",
            "sensitive": False,
        },
    )
    project_slug: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "Bugsnag Project Slug (leave blank to pull from all projects)",
            "hint": "Found in your project URL: bugsnag.com/<org>/<project>",
            "sensitive": False,
        },
        default=None,
    )


class BugsnagProvider(BaseProvider):
    """Pull errors from Bugsnag and receive webhook alerts on new exceptions."""

    PROVIDER_DISPLAY_NAME = "Bugsnag"
    PROVIDER_CATEGORY = ["Monitoring", "Developer Tools"]
    PROVIDER_TAGS = ["alert", "error-tracking", "monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_errors",
            description="Read error events from Bugsnag projects.",
            mandatory=True,
            documentation_url="https://bugsnagapiv2.docs.apiary.io/",
        ),
    ]

    SEVERITIES_MAP = {
        "error": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "debug": AlertSeverity.LOW,
    }

    STATUS_MAP = {
        "open": AlertStatus.FIRING,
        "fixed": AlertStatus.RESOLVED,
        "ignored": AlertStatus.SUPPRESSED,
        "in_progress": AlertStatus.ACKNOWLEDGED,
    }

    FINGERPRINT_FIELDS = ["id"]

    API_BASE_URL = "https://api.bugsnag.com"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = BugsnagProviderAuthConfig(
            **self.config.authentication
        )

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"token {self.authentication_config.personal_auth_token}",
            "X-Version": "2",
            "Content-Type": "application/json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            response = requests.get(
                f"{self.API_BASE_URL}/user",
                headers=self._get_headers(),
                timeout=10,
            )
            if response.status_code == 200:
                return {"read_errors": True}
            else:
                return {
                    "read_errors": f"HTTP {response.status_code}: {response.text}"
                }
        except Exception as e:
            return {"read_errors": str(e)}

    def _get_projects(self) -> list[dict]:
        """Retrieve all projects for the organization."""
        projects = []
        page = 1
        while True:
            response = requests.get(
                f"{self.API_BASE_URL}/organizations/{self.authentication_config.organization_slug}/projects",
                headers=self._get_headers(),
                params={"per_page": 100, "page": page},
                timeout=10,
            )
            response.raise_for_status()
            batch = response.json()
            if not batch:
                break
            projects.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return projects

    def _get_errors_for_project(self, project_id: str) -> list[dict]:
        """Retrieve open errors for a given project."""
        errors = []
        page = 1
        while True:
            response = requests.get(
                f"{self.API_BASE_URL}/projects/{project_id}/errors",
                headers=self._get_headers(),
                params={"per_page": 100, "page": page, "status": "open"},
                timeout=10,
            )
            response.raise_for_status()
            batch = response.json()
            if not batch:
                break
            errors.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return errors

    def _get_alerts(self) -> list[AlertDto]:
        alerts = []
        try:
            if self.authentication_config.project_slug:
                # If project slug is specified, find that project's ID
                projects = self._get_projects()
                project = next(
                    (p for p in projects if p.get("slug") == self.authentication_config.project_slug),
                    None,
                )
                if project is None:
                    self.logger.warning(
                        f"Project '{self.authentication_config.project_slug}' not found"
                    )
                    return []
                target_projects = [project]
            else:
                target_projects = self._get_projects()

            for project in target_projects:
                project_id = project.get("id")
                project_name = project.get("name", project_id)
                try:
                    errors = self._get_errors_for_project(project_id)
                    for error in errors:
                        alert = self._error_to_alert_dto(error, project_name)
                        alerts.append(alert)
                except Exception as e:
                    self.logger.error(
                        f"Failed to get errors for project {project_name}: {e}"
                    )
        except Exception as e:
            self.logger.error(f"Failed to get alerts from Bugsnag: {e}")

        return alerts

    def _error_to_alert_dto(self, error: dict, project_name: str) -> AlertDto:
        error_id = error.get("id", "")
        severity_str = error.get("severity", "error")
        status_str = error.get("status", "open")

        severity = self.SEVERITIES_MAP.get(severity_str, AlertSeverity.HIGH)
        status = self.STATUS_MAP.get(status_str, AlertStatus.FIRING)

        last_seen = error.get("last_seen")
        if last_seen:
            try:
                last_received = datetime.datetime.fromisoformat(
                    last_seen.replace("Z", "+00:00")
                ).isoformat()
            except ValueError:
                last_received = datetime.datetime.now(datetime.timezone.utc).isoformat()
        else:
            last_received = datetime.datetime.now(datetime.timezone.utc).isoformat()

        return AlertDto(
            id=error_id,
            name=f"{error.get('error_class', 'Error')}: {error.get('message', '')}",
            description=error.get("message", ""),
            severity=severity,
            status=status,
            lastReceived=last_received,
            source=["bugsnag"],
            fingerprint=error_id,
            url=error.get("url", ""),
            project=project_name,
            error_class=error.get("error_class", ""),
            occurrences=error.get("occurrences", 0),
            users_affected=error.get("users_affected", 0),
            first_seen=error.get("first_seen"),
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format a Bugsnag webhook payload into an AlertDto.

        Bugsnag webhook payload structure:
        https://docs.bugsnag.com/product/integrations/data-forwarding/webhook/
        """
        error = event.get("error", {})
        trigger_event = event.get("event", {})
        project = event.get("project", {})

        error_id = error.get("id", trigger_event.get("id", ""))
        exceptions = trigger_event.get("exceptions", [{}])
        first_exception = exceptions[0] if exceptions else {}

        error_class = first_exception.get("errorClass", error.get("errorClass", "Error"))
        message = first_exception.get("message", error.get("message", ""))

        severity_str = trigger_event.get("severity", error.get("severity", "error"))
        severity = BugsnagProvider.SEVERITIES_MAP.get(severity_str, AlertSeverity.HIGH)

        error_status = error.get("status", "open")
        status = BugsnagProvider.STATUS_MAP.get(error_status, AlertStatus.FIRING)

        last_seen = error.get("lastSeen") or error.get("last_seen")
        if last_seen:
            try:
                last_received = datetime.datetime.fromisoformat(
                    last_seen.replace("Z", "+00:00")
                ).isoformat()
            except ValueError:
                last_received = datetime.datetime.now(datetime.timezone.utc).isoformat()
        else:
            last_received = datetime.datetime.now(datetime.timezone.utc).isoformat()

        alert = AlertDto(
            id=error_id,
            name=f"{error_class}: {message}",
            description=message,
            severity=severity,
            status=status,
            lastReceived=last_received,
            source=["bugsnag"],
            fingerprint=error_id,
            url=error.get("url", ""),
            project=project.get("name", ""),
            project_slug=project.get("slug", ""),
            error_class=error_class,
            context=trigger_event.get("context", ""),
            trigger=event.get("trigger", ""),
            occurrences=error.get("occurrences", 0),
            users_affected=error.get("usersAffected", error.get("users_affected", 0)),
            app_version=trigger_event.get("app", {}).get("version", ""),
            release_stage=trigger_event.get("app", {}).get("releaseStage", "production"),
        )
        alert.fingerprint = (
            BugsnagProvider.get_alert_fingerprint(
                alert, BugsnagProvider.FINGERPRINT_FIELDS
            )
            if error_id
            else None
        )
        return alert


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    token = os.environ.get("BUGSNAG_PERSONAL_AUTH_TOKEN")
    org_slug = os.environ.get("BUGSNAG_ORG_SLUG")

    if not token or not org_slug:
        raise Exception(
            "BUGSNAG_PERSONAL_AUTH_TOKEN and BUGSNAG_ORG_SLUG environment variables are required"
        )

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    config = ProviderConfig(
        description="Bugsnag Provider",
        authentication={
            "personal_auth_token": token,
            "organization_slug": org_slug,
        },
    )
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="bugsnag-keephq",
        provider_type="bugsnag",
        provider_config=config,
    )
    scopes = provider.validate_scopes()
    print("Scopes:", scopes)
    alerts = provider.get_alerts()
    print(f"Got {len(alerts)} alerts")
