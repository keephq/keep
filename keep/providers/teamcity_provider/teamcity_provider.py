"""
TeamCityProvider is a class that integrates with JetBrains TeamCity CI/CD server,
allowing Keep to pull build failures as alerts and receive webhook notifications.
"""

import dataclasses
import datetime
from typing import List, Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class TeamCityProviderAuthConfig:
    """
    TeamCityProviderAuthConfig holds the authentication configuration
    for the TeamCity provider.
    """

    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "TeamCity server URL (e.g. https://teamcity.example.com)",
            "hint": "The base URL of your TeamCity server",
        },
    )
    token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "TeamCity Access Token",
            "hint": "Generate at Profile > Access Tokens in TeamCity",
            "sensitive": True,
        },
    )


class TeamCityProvider(BaseProvider):
    """Pull build failures and alerts from JetBrains TeamCity CI/CD server."""

    PROVIDER_DISPLAY_NAME = "TeamCity"
    PROVIDER_CATEGORY = ["Monitoring", "Development Tools"]
    PROVIDER_TAGS = ["alert"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated",
            mandatory=True,
            alias="authenticated",
        ),
    ]

    # Map TeamCity build statuses to Keep severity
    BUILD_STATUS_SEVERITY = {
        "FAILURE": AlertSeverity.HIGH,
        "ERROR": AlertSeverity.CRITICAL,
        "SUCCESS": AlertSeverity.INFO,
        "UNKNOWN": AlertSeverity.WARNING,
    }

    BUILD_STATUS_ALERT_STATUS = {
        "FAILURE": AlertStatus.FIRING,
        "ERROR": AlertStatus.FIRING,
        "SUCCESS": AlertStatus.RESOLVED,
        "UNKNOWN": AlertStatus.FIRING,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """Validate the provider configuration."""
        self.authentication_config = TeamCityProviderAuthConfig(
            **self.config.authentication
        )
        # Strip trailing slash from host
        self.authentication_config.host = self.authentication_config.host.rstrip("/")

    def __get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.authentication_config.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def __get_url(self, path: str) -> str:
        return f"{self.authentication_config.host}/app/rest/{path}"

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate that the token is valid by fetching server info."""
        try:
            response = requests.get(
                self.__get_url("server"),
                headers=self.__get_headers(),
                timeout=10,
            )
            if response.status_code == 200:
                return {"authenticated": True}
            elif response.status_code == 401:
                return {"authenticated": "Invalid or expired access token"}
            else:
                return {
                    "authenticated": f"Unexpected status code: {response.status_code}"
                }
        except Exception as e:
            self.logger.error("Error validating TeamCity scopes: %s", e)
            return {"authenticated": f"Error connecting to TeamCity: {e}"}

    def _get_alerts(self) -> List[AlertDto]:
        """Pull failed builds from TeamCity and return as AlertDto objects."""
        alerts = []
        try:
            self.logger.info("Fetching failed builds from TeamCity")
            response = requests.get(
                self.__get_url("builds"),
                headers=self.__get_headers(),
                params={
                    "locator": "status:FAILURE,count:100",
                    "fields": "build(id,number,status,state,buildTypeId,buildType(name,projectName),branchName,startDate,finishDate,statusText,webUrl)",
                },
                timeout=30,
            )

            if not response.ok:
                self.logger.error(
                    "Failed to fetch builds from TeamCity: %s", response.text
                )
                return alerts

            data = response.json()
            builds = data.get("build", [])

            for build in builds:
                alert = self.__build_to_alert(build)
                alerts.append(alert)

            self.logger.info("Fetched %d failed builds from TeamCity", len(alerts))

        except Exception as e:
            self.logger.error("Error fetching builds from TeamCity: %s", e)

        return alerts

    def __build_to_alert(self, build: dict) -> AlertDto:
        """Convert a TeamCity build dict to an AlertDto."""
        build_id = str(build.get("id", "unknown"))
        status = build.get("status", "UNKNOWN").upper()
        state = build.get("state", "finished")

        build_type = build.get("buildType", {})
        build_name = build_type.get("name", build.get("buildTypeId", "Unknown Build"))
        project_name = build_type.get("projectName", "")

        branch = build.get("branchName", "default")
        status_text = build.get("statusText", "")
        web_url = build.get("webUrl", "")

        # Determine last received time
        finish_date = build.get("finishDate") or build.get("startDate")
        if finish_date:
            try:
                # TeamCity date format: 20240315T102300+0000
                last_received = datetime.datetime.strptime(
                    finish_date[:15], "%Y%m%dT%H%M%S"
                ).isoformat()
            except (ValueError, TypeError):
                last_received = datetime.datetime.utcnow().isoformat()
        else:
            last_received = datetime.datetime.utcnow().isoformat()

        severity = self.BUILD_STATUS_SEVERITY.get(status, AlertSeverity.WARNING)
        alert_status = self.BUILD_STATUS_ALERT_STATUS.get(status, AlertStatus.FIRING)

        return AlertDto(
            id=build_id,
            name=f"{project_name} :: {build_name}" if project_name else build_name,
            severity=severity,
            status=alert_status,
            lastReceived=last_received,
            description=status_text or f"Build #{build.get('number', build_id)} {status.lower()}",
            source=["teamcity"],
            url=web_url,
            labels={
                "build_id": build_id,
                "build_number": str(build.get("number", "")),
                "project": project_name,
                "branch": branch,
                "state": state,
            },
            fingerprint=f"{build.get('buildTypeId', '')}-{branch}",
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """Format a TeamCity webhook notification into an AlertDto."""
        build = event.get("build", event)

        build_id = str(build.get("buildId", build.get("id", "unknown")))
        status = build.get("buildResult", build.get("status", "UNKNOWN")).upper()
        if status == "FAILED":
            status = "FAILURE"

        build_name = build.get("buildName", build.get("buildTypeName", "Unknown Build"))
        project_name = build.get("projectName", "")
        branch = build.get("branchName", build.get("branch", "default"))
        build_url = build.get("buildUrl", build.get("webUrl", ""))
        reason = build.get("buildStatusMessage", build.get("statusText", ""))

        severity = TeamCityProvider.BUILD_STATUS_SEVERITY.get(
            status, AlertSeverity.WARNING
        )
        alert_status = TeamCityProvider.BUILD_STATUS_ALERT_STATUS.get(
            status, AlertStatus.FIRING
        )

        return AlertDto(
            id=build_id,
            name=f"{project_name} :: {build_name}" if project_name else build_name,
            severity=severity,
            status=alert_status,
            lastReceived=datetime.datetime.utcnow().isoformat(),
            description=reason or f"Build {status.lower()}",
            source=["teamcity"],
            url=build_url,
            labels={
                "build_id": build_id,
                "project": project_name,
                "branch": branch,
            },
            fingerprint=f"{build.get('buildTypeId', build_name)}-{branch}",
        )
