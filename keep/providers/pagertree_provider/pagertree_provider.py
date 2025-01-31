"""
PagetreeProvider is a class that provides a way to read get alerts from Pagetree.
"""

import dataclasses
from typing import Literal

import pydantic
import requests

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class PagertreeProviderAuthConfig:
    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Your pagertree APIToken",
            "sensitive": True,
        },
        default=None,
    )


class PagertreeProvider(BaseProvider):
    """Get all alerts from pagertree"""

    PROVIDER_DISPLAY_NAME = "PagerTree"
    PROVIDER_CATEGORY = ["Incident Management"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="The user can connect to the server and is authenticated using their API_Key",
            mandatory=True,
            alias="Authenticated with pagertree",
        )
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def __get_headers(self):
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.authentication_config.api_token}",
        }

    def validate_scopes(self):
        """
        Validates that the user has the required scopes to use the provider.
        """
        try:
            response = requests.get(
                "https://api.pagertree.com/api/v4/alerts", headers=self.__get_headers()
            )

            if response.status_code == 200:
                scopes = {
                    "authenticated": True,
                }
            else:
                self.logger.error("Unable to authenticate user")
                scopes = {
                    "authenticated": f"User not authorized, StatusCode: {response.status_code}",
                }
        except Exception as e:
            self.logger.error("Error validating scopes", extra={"error": str(e)})
            scopes = {
                "authenticated": str(e),
            }
        return scopes

    def dispose(self):
        pass

    def validate_config(self):
        """
        Validates required configuration for pgartree's provider.
        """
        self.authentication_config = PagertreeProviderAuthConfig(
            **self.config.authentication
        )

    def _get_alerts(self) -> list[AlertDto]:
        try:
            response = requests.get(
                "https://api.pagertree.com/api/v4/alerts", headers=self.__get_headers()
            )
            if not response.ok:
                self.logger.error("Failed to get alerts", extra=response.json())
                raise Exception("Could not get alerts")
            return [
                AlertDto(
                    id=alert["id"],
                    status=alert["status"],
                    severity=alert["urgency"],
                    source=alert["source"],
                    message=alert["title"],
                    startedAt=alert["created_at"],
                    description=alert["description"],
                )
                for alert in response.json()["alerts"]
            ]

        except Exception as e:
            self.logger.error(
                "Error while getting PagerTree alerts", extra={"error": str(e)}
            )
            raise e

    def __send_alert(
        self,
        title: str,
        description: str,
        urgency: Literal["low", "medium", "high", "critical"],
        destination_team_ids: list[str],
        destination_router_ids: list[str],
        destination_account_user_ids: list[str],
        status: Literal["queued", "open", "acknowledged", "resolved", "dropped"],
        **kwargs: dict,
    ):
        """
        Sends PagerDuty Alert

        Args:
            title: Title of the alert.
            description: UTF-8 string of custom message for alert. Shown in incident description
            urgency: low|medium|high|critical
            destination_team_ids: destination team_ids to send alert to
            destination_router_ids: destination router_ids to send alert to
            destination_account_user_ids: destination account_users_ids to send alert to
            status: alert status to send
        """
        response = requests.post(
            "https://api.pagertree.com/api/v4/alerts",
            headers=self.__get_headers(),
            data={
                "title": title,
                "description": description,
                "urgency": urgency,
                "destination_team_ids": destination_team_ids,
                "destination_router_ids": destination_router_ids,
                "destination_account_user_ids": destination_account_user_ids,
                "status": status,
                **kwargs,
            },
        )
        if not response.ok:
            self.logger.error("Failed to send alert", extra={"error": response.json()})
        self.logger.info("Alert status: %s", response.status_code)
        self.logger.info("Alert created successfully", response.json())

    def __send_incident(
        self,
        title: str,
        incident_severity: str,
        incident_message: str,
        urgency: Literal["low", "medium", "high", "critical"],
        destination_team_ids: list[str],
        destination_router_ids: list[str],
        destination_account_user_ids: list[str],
        **kwargs: dict,
    ):
        """
        Marking an alert as an incident communicates to your team members this alert is a greater degree of severity than a normal alert.

        Args:
            title: Title of the alert.
            description: UTF-8 string of custom message for alert. Shown in incident description
            urgency: low|medium|high|critical
            destination_team_ids: destination team_ids to send alert to
            destination_router_ids: destination router_ids to send alert to
            destination_account_user_ids: destination account_users_ids to send alert to

        """
        response = requests.post(
            "https://api.pagertree.com/api/v4/alerts",
            headers=self.__get_headers(),
            data={
                "title": title,
                "meta": {
                    "incident": True,
                    "incident_severity": incident_severity,
                    "incident_message": incident_message,
                },
                "urgency": urgency,
                "destination_team_ids": destination_team_ids,
                "destination_router_ids": destination_router_ids,
                "destination_account_user_ids": destination_account_user_ids,
                **kwargs,
            },
        )
        if not response.ok:
            self.logger.error(
                "Failed to send incident", extra={"error": response.json()}
            )
        self.logger.info("Incident status: %s", response.status_code)
        self.logger.info("Incident created successfully", response.json())

    def _notify(
        self,
        title: str,
        urgency: Literal["low", "medium", "high", "critical"],
        incident: bool = False,
        severities: Literal[
            "SEV-1", "SEV-2", "SEV-3", "SEV-4", "SEV-5", "SEV_UNKNOWN"
        ] = "SEV-5",
        incident_message: str = "",
        description: str = "",
        status: Literal[
            "queued", "open", "acknowledged", "resolved", "dropped"
        ] = "queued",
        destination_team_ids: list[str] = [],
        destination_router_ids: list[str] = [],
        destination_account_user_ids: list[str] = [],
        **kwargs: dict,
    ):
        if (
            len(destination_team_ids)
            + len(destination_router_ids)
            + len(destination_account_user_ids)
            == 0
        ):
            raise Exception(
                "at least 1 destination (Team, Router, or Account User) is required"
            )
        if not incident:
            self.__send_alert(
                title,
                description,
                urgency,
                destination_team_ids,
                destination_router_ids,
                destination_account_user_ids,
                status,
                **kwargs,
            )
        else:
            self.__send_incident(
                incident_message,
                severities,
                title,
                urgency,
                destination_team_ids,
                destination_router_ids,
                destination_account_user_ids,
                **kwargs,
            )
