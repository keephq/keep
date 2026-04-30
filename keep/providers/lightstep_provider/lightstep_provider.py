"""
LightstepProvider is a class that allows to pull alerts from Lightstep
(now ServiceNow Cloud Observability) and receive webhook notifications
when trace-based conditions trigger.
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
class LightstepProviderAuthConfig:
    """
    LightstepProviderAuthConfig holds the authentication configuration for Lightstep.
    """

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Lightstep API Key",
            "hint": "Generate at Account Settings → API Keys in your Lightstep dashboard",
            "sensitive": True,
        },
    )
    organization: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Lightstep Organization Slug",
            "hint": "Your organization slug, visible in the Lightstep URL",
            "sensitive": False,
        },
    )
    project: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "Lightstep Project Name (leave blank to pull from all projects)",
            "hint": "The project name as shown in Lightstep",
            "sensitive": False,
        },
        default=None,
    )


class LightstepProvider(BaseProvider):
    """Pull alerts from Lightstep and receive webhook notifications on condition triggers."""

    PROVIDER_DISPLAY_NAME = "Lightstep"
    PROVIDER_CATEGORY = ["Monitoring", "Developer Tools"]
    PROVIDER_TAGS = ["alert", "monitoring", "tracing"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read alerts from Lightstep projects.",
            mandatory=True,
            documentation_url="https://api-docs.lightstep.com/",
        ),
    ]

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "triggered": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "no_data": AlertStatus.PENDING,
    }

    FINGERPRINT_FIELDS = ["id"]

    API_BASE_URL = "https://api.lightstep.com/public/v0.2"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = LightstepProviderAuthConfig(
            **self.config.authentication
        )

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.authentication_config.api_key}",
            "Content-Type": "application/json",
        }

    def _get_projects(self) -> list[dict]:
        """Retrieve all projects for the organization."""
        response = requests.get(
            f"{self.API_BASE_URL}/{self.authentication_config.organization}/projects",
            headers=self._get_headers(),
            timeout=15,
        )
        response.raise_for_status()
        return response.json().get("data", [])

    def _get_alerts_for_project(self, project_name: str) -> list[dict]:
        """Retrieve all alerts for a given project."""
        alerts = []
        cursor = None
        while True:
            params = {"per-page": 100}
            if cursor:
                params["cursor"] = cursor
            response = requests.get(
                f"{self.API_BASE_URL}/{self.authentication_config.organization}/projects/{project_name}/alerts",
                headers=self._get_headers(),
                params=params,
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            batch = payload.get("data", [])
            alerts.extend(batch)
            # Check for next page cursor
            links = payload.get("links", {})
            next_link = links.get("next")
            if not next_link or not batch:
                break
            # Extract cursor from next link if paginated
            cursor = payload.get("meta", {}).get("next-cursor")
            if not cursor:
                break
        return alerts

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            projects = self._get_projects()
            if isinstance(projects, list):
                return {"read_alerts": True}
            return {"read_alerts": "Unexpected response format from Lightstep API"}
        except Exception as e:
            return {"read_alerts": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        alerts = []
        try:
            if self.authentication_config.project:
                target_projects = [self.authentication_config.project]
            else:
                projects = self._get_projects()
                target_projects = [p.get("id", "") for p in projects if p.get("id")]

            for project_name in target_projects:
                try:
                    raw_alerts = self._get_alerts_for_project(project_name)
                    for raw_alert in raw_alerts:
                        try:
                            alert = self._raw_to_alert_dto(raw_alert, project_name)
                            alerts.append(alert)
                        except Exception as e:
                            self.logger.warning(
                                f"Failed to convert alert to AlertDto: {e}"
                            )
                except Exception as e:
                    self.logger.error(
                        f"Failed to get alerts for project {project_name}: {e}"
                    )
        except Exception as e:
            self.logger.error(f"Failed to get alerts from Lightstep: {e}")

        return alerts

    def _raw_to_alert_dto(self, raw: dict, project_name: str) -> AlertDto:
        attrs = raw.get("attributes", {})
        alert_id = raw.get("id", "")
        status_str = attrs.get("status", "triggered")
        status = self.STATUS_MAP.get(status_str, AlertStatus.FIRING)

        # Determine severity from current value vs thresholds
        thresholds = attrs.get("thresholds", {})
        current_value = attrs.get("current-value")
        severity = AlertSeverity.WARNING
        if current_value is not None and thresholds:
            critical_threshold = thresholds.get("critical")
            if critical_threshold is not None and current_value >= critical_threshold:
                severity = AlertSeverity.CRITICAL

        triggered_at = attrs.get("triggered-at")
        resolved_at = attrs.get("resolved-at")
        ts_str = resolved_at if resolved_at else triggered_at
        if ts_str:
            try:
                last_received = datetime.datetime.fromisoformat(
                    ts_str.replace("Z", "+00:00")
                ).isoformat()
            except ValueError:
                last_received = datetime.datetime.now(datetime.timezone.utc).isoformat()
        else:
            last_received = datetime.datetime.now(datetime.timezone.utc).isoformat()

        return AlertDto(
            id=alert_id,
            name=attrs.get("name", "Lightstep Alert"),
            description=attrs.get("condition-label", ""),
            severity=severity,
            status=status,
            lastReceived=last_received,
            source=["lightstep"],
            fingerprint=alert_id,
            url=attrs.get("alert-url", ""),
            project=attrs.get("project-name", project_name),
            stream=attrs.get("stream-name", ""),
            current_value=current_value,
            thresholds=thresholds,
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format a Lightstep webhook payload into an AlertDto.

        Lightstep sends alert objects when conditions are triggered or resolved.
        The payload wraps the alert in a 'data' key following JSON:API conventions.
        """
        data = event.get("data", event)
        attrs = data.get("attributes", {})
        alert_id = data.get("id", "")

        status_str = attrs.get("status", "triggered")
        status = LightstepProvider.STATUS_MAP.get(status_str, AlertStatus.FIRING)

        thresholds = attrs.get("thresholds", {})
        current_value = attrs.get("current-value")
        severity = AlertSeverity.WARNING
        if current_value is not None and thresholds:
            critical_threshold = thresholds.get("critical")
            if critical_threshold is not None and current_value >= critical_threshold:
                severity = AlertSeverity.CRITICAL

        triggered_at = attrs.get("triggered-at")
        resolved_at = attrs.get("resolved-at")
        ts_str = resolved_at if resolved_at else triggered_at
        if ts_str:
            try:
                last_received = datetime.datetime.fromisoformat(
                    ts_str.replace("Z", "+00:00")
                ).isoformat()
            except ValueError:
                last_received = datetime.datetime.now(datetime.timezone.utc).isoformat()
        else:
            last_received = datetime.datetime.now(datetime.timezone.utc).isoformat()

        alert = AlertDto(
            id=alert_id,
            name=attrs.get("name", "Lightstep Alert"),
            description=attrs.get("condition-label", ""),
            severity=severity,
            status=status,
            lastReceived=last_received,
            source=["lightstep"],
            fingerprint=alert_id,
            url=attrs.get("alert-url", ""),
            project=attrs.get("project-name", ""),
            stream=attrs.get("stream-name", ""),
            current_value=current_value,
            thresholds=thresholds,
        )
        alert.fingerprint = (
            LightstepProvider.get_alert_fingerprint(
                alert, LightstepProvider.FINGERPRINT_FIELDS
            )
            if alert_id
            else None
        )
        return alert


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    api_key = os.environ.get("LIGHTSTEP_API_KEY")
    organization = os.environ.get("LIGHTSTEP_ORG")

    if not api_key or not organization:
        raise Exception(
            "LIGHTSTEP_API_KEY and LIGHTSTEP_ORG environment variables are required"
        )

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    config = ProviderConfig(
        description="Lightstep Provider",
        authentication={
            "api_key": api_key,
            "organization": organization,
        },
    )
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="lightstep-keephq",
        provider_type="lightstep",
        provider_config=config,
    )
    scopes = provider.validate_scopes()
    print("Scopes:", scopes)
    alerts = provider.get_alerts()
    print(f"Got {len(alerts)} alerts")
