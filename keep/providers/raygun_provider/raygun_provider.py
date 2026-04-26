"""
RaygunProvider is a class that allows to get crash reports and performance data from Raygun.
"""

import dataclasses
import datetime
from typing import List
from urllib.parse import urljoin

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class RaygunProviderAuthConfig:
    """
    RaygunProviderAuthConfig is a class that allows to authenticate in Raygun.
    """

    external_access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Raygun External Access Token",
            "hint": "Found in your Raygun account under User → API Keys (External access tokens)",
            "sensitive": True,
        },
    )

    application_api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Raygun Application API Key",
            "hint": "Found in your Raygun application settings → Application API key",
            "sensitive": True,
        },
    )


class RaygunProvider(BaseProvider):
    """Pull error groups and crash reports from Raygun."""

    PROVIDER_DISPLAY_NAME = "Raygun"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated with Raygun API",
            mandatory=True,
            alias="authenticated",
        ),
    ]

    SEVERITIES_MAP = {
        "error": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
    }

    BASE_URL = "https://api.raygun.com"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = RaygunProviderAuthConfig(
            **self.config.authentication
        )

    def __get_headers(self):
        return {
            "Authorization": f"Bearer {self.authentication_config.external_access_token}",
            "Content-Type": "application/json",
        }

    def __get_url(self, path: str) -> str:
        return urljoin(self.BASE_URL + "/", path.lstrip("/"))

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {}
        try:
            response = requests.get(
                self.__get_url("/v3/applications"),
                headers=self.__get_headers(),
                timeout=10,
            )
            if response.status_code == 200:
                scopes["authenticated"] = True
            elif response.status_code == 401:
                scopes["authenticated"] = "Invalid external access token"
            else:
                scopes["authenticated"] = (
                    f"Unexpected status code: {response.status_code}"
                )
        except Exception as e:
            self.logger.error("Error validating Raygun scopes: %s", e)
            scopes["authenticated"] = str(e)
        return scopes

    def __get_error_groups(self) -> List[AlertDto]:
        """Fetch active error groups for the configured application."""
        try:
            response = requests.get(
                self.__get_url(
                    f"/v3/applications/{self.authentication_config.application_api_key}/groups"
                ),
                headers=self.__get_headers(),
                params={"count": 100, "status": "Active"},
                timeout=15,
            )
            if not response.ok:
                self.logger.error(
                    "Failed to get error groups from Raygun: %s", response.text
                )
                return []

            data = response.json()
            groups = data.get("data", [])
            alerts = []

            for group in groups:
                severity = AlertSeverity.HIGH  # errors are always HIGH by default
                last_occurrence = group.get("lastOccurredOn", "")
                if last_occurrence:
                    try:
                        last_occurrence = datetime.datetime.fromisoformat(
                            last_occurrence.replace("Z", "+00:00")
                        ).isoformat()
                    except Exception:
                        pass

                first_occurrence = group.get("firstOccurredOn", "")

                alerts.append(
                    AlertDto(
                        id=group.get("identifier", ""),
                        name=group.get("message", "Raygun Error"),
                        description=group.get("message", ""),
                        severity=severity,
                        status=AlertStatus.FIRING,
                        lastReceived=last_occurrence,
                        source=["raygun"],
                        labels={
                            "total_occurrences": str(
                                group.get("totalOccurences", 0)
                            ),
                            "users_affected": str(group.get("usersAffected", 0)),
                            "first_occurred": first_occurrence,
                            "application_name": group.get("applicationName", ""),
                        },
                    )
                )
            return alerts

        except Exception as e:
            self.logger.error("Error getting error groups from Raygun: %s", e)
            return []

    def _get_alerts(self) -> List[AlertDto]:
        self.logger.info("Collecting error groups from Raygun")
        return self.__get_error_groups()

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """Format a Raygun webhook payload into an AlertDto."""
        error = event.get("Error", {})
        application = event.get("Application", {})

        # Raygun webhook sends individual error occurrences
        last_received = event.get("OccurredOn", "")
        if last_received:
            try:
                last_received = datetime.datetime.fromisoformat(
                    last_received.replace("Z", "+00:00")
                ).isoformat()
            except Exception:
                pass

        message = error.get("Message", "Raygun Error")
        class_name = error.get("ClassName", "")
        if class_name and message:
            name = f"{class_name}: {message}"
        else:
            name = message or class_name or "Raygun Error"

        tags = event.get("Tags", [])
        user = event.get("User", {})

        return AlertDto(
            id=event.get("identifier", event.get("groupingKey", "")),
            name=name,
            description=message,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.FIRING,
            lastReceived=last_received,
            source=["raygun"],
            labels={
                "application": application.get("Name", ""),
                "user_identifier": user.get("Identifier", ""),
                "tags": ", ".join(tags),
                "machine_name": event.get("MachineName", ""),
                "environment": event.get("Details", {})
                .get("Environment", {})
                .get("ProcessorCount", ""),
            },
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    external_token = os.environ.get("RAYGUN_EXTERNAL_ACCESS_TOKEN")
    app_api_key = os.environ.get("RAYGUN_APPLICATION_API_KEY")

    if not external_token or not app_api_key:
        raise Exception(
            "RAYGUN_EXTERNAL_ACCESS_TOKEN and RAYGUN_APPLICATION_API_KEY must be set"
        )

    config = ProviderConfig(
        description="Raygun Provider",
        authentication={
            "external_access_token": external_token,
            "application_api_key": app_api_key,
        },
    )

    provider = RaygunProvider(
        context_manager,
        provider_id="raygun",
        config=config,
    )

    alerts = provider._get_alerts()
    print(alerts)
