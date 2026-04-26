"""
AtatusProvider is a class that provides alerting integration with Atatus,
an APM (Application Performance Monitoring) and error tracking platform.
"""

import dataclasses
import datetime
from typing import List

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class AtatusProviderAuthConfig:
    """
    AtatusProviderAuthConfig holds authentication configuration for Atatus.
    """

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Atatus API Key",
            "hint": "Found in your Atatus account under Settings > API Keys",
            "sensitive": True,
        },
    )

    project_token: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Atatus Project Token (optional, for project-scoped requests)",
            "hint": "Found in your Atatus project settings",
            "sensitive": True,
        },
        default=None,
    )


class AtatusProvider(BaseProvider):
    """Receive error and performance alerts from Atatus APM platform."""

    PROVIDER_DISPLAY_NAME = "Atatus"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring", "Cloud Infrastructure"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="alerts:read",
            description="Read alerts and errors from Atatus",
            mandatory=True,
            alias="Read Alerts",
        ),
    ]

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "error": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "warn": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
    }

    STATUS_MAP = {
        "open": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "ignored": AlertStatus.SUPPRESSED,
    }

    FINGERPRINT_FIELDS = ["id", "error_type"]

    BASE_URL = "https://api.atatus.com/api/v1"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = AtatusProviderAuthConfig(
            **self.config.authentication
        )

    def __get_headers(self) -> dict:
        return {
            "X-Api-Key": self.authentication_config.api_key,
            "Content-Type": "application/json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate provider scopes by testing the projects endpoint."""
        scopes = {}
        try:
            response = requests.get(
                f"{self.BASE_URL}/projects",
                headers=self.__get_headers(),
                timeout=10,
            )
            if response.status_code == 200:
                scopes["alerts:read"] = True
            elif response.status_code == 401:
                scopes["alerts:read"] = "Invalid API key — unauthorized"
            elif response.status_code == 403:
                scopes["alerts:read"] = "Forbidden — insufficient permissions"
            else:
                scopes["alerts:read"] = (
                    f"Unable to connect to Atatus, status code: {response.status_code}"
                )
        except Exception as e:
            self.logger.exception("Failed to validate Atatus scopes")
            scopes["alerts:read"] = str(e)
        return scopes

    def _get_alerts(self) -> List[AlertDto]:
        """Pull error groups and alerts from Atatus."""
        self.logger.info("Fetching alerts from Atatus")
        alerts = []
        try:
            params: dict = {"status": "open", "limit": 100}
            if self.authentication_config.project_token:
                params["project_token"] = self.authentication_config.project_token

            response = requests.get(
                f"{self.BASE_URL}/errors",
                headers=self.__get_headers(),
                params=params,
                timeout=10,
            )
            if not response.ok:
                self.logger.error(
                    "Failed to fetch errors from Atatus: %s", response.text
                )
                raise Exception(
                    f"Failed to fetch errors from Atatus: {response.status_code}"
                )

            data = response.json()
            items = data.get("errors", data.get("data", [])) if isinstance(data, dict) else []
            if not isinstance(items, list):
                items = []

            for item in items:
                severity_raw = item.get("severity", item.get("level", "error")).lower()
                status_raw = item.get("status", "open").lower()

                occurred_at = item.get("last_seen") or item.get("first_seen") or item.get("created_at")
                if occurred_at:
                    try:
                        last_received = datetime.datetime.fromisoformat(
                            str(occurred_at).replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        last_received = datetime.datetime.utcnow()
                else:
                    last_received = datetime.datetime.utcnow()

                error_type = item.get("error_type", item.get("type", ""))
                alert = AlertDto(
                    id=str(item.get("id", "")),
                    name=item.get("message", error_type or "Atatus Error"),
                    severity=self.SEVERITIES_MAP.get(severity_raw, AlertSeverity.HIGH),
                    status=self.STATUS_MAP.get(status_raw, AlertStatus.FIRING),
                    lastReceived=last_received,
                    description=item.get("message", ""),
                    source=["atatus"],
                    url=item.get("url", ""),
                    fingerprint=str(item.get("id", "")),
                    error_type=error_type,
                    occurrences=item.get("occurrences", 0),
                    affected_users=item.get("affected_users", 0),
                    environment=item.get("environment", ""),
                    service=item.get("app_name", item.get("project_name", "")),
                )
                alerts.append(alert)
        except Exception as e:
            self.logger.error("Error fetching alerts from Atatus: %s", e)
        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """Format an Atatus webhook payload into an AlertDto."""
        # Atatus webhook payload structure
        severity_raw = event.get("severity", event.get("level", "error")).lower()
        status_raw = event.get("status", "open").lower()

        severity = AtatusProvider.SEVERITIES_MAP.get(severity_raw, AlertSeverity.HIGH)
        status = AtatusProvider.STATUS_MAP.get(status_raw, AlertStatus.FIRING)

        occurred_at = event.get("last_seen") or event.get("first_seen") or event.get("timestamp")
        if occurred_at:
            try:
                last_received = datetime.datetime.fromisoformat(
                    str(occurred_at).replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                last_received = datetime.datetime.utcnow()
        else:
            last_received = datetime.datetime.utcnow()

        error_type = event.get("error_type", event.get("type", ""))

        return AlertDto(
            id=str(event.get("id", "")),
            name=event.get("message", error_type or "Atatus Error"),
            severity=severity,
            status=status,
            lastReceived=last_received,
            description=event.get("message", ""),
            source=["atatus"],
            url=event.get("url", ""),
            fingerprint=str(event.get("id", "")),
            error_type=error_type,
            occurrences=event.get("occurrences", 0),
            affected_users=event.get("affected_users", 0),
            environment=event.get("environment", ""),
            service=event.get("app_name", event.get("project_name", "")),
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    api_key = os.environ.get("ATATUS_API_KEY")
    if not api_key:
        raise Exception("ATATUS_API_KEY must be set")

    config = ProviderConfig(
        description="Atatus Provider",
        authentication={
            "api_key": api_key,
        },
    )
    provider = AtatusProvider(
        context_manager, provider_id="atatus-test", config=config
    )
    alerts = provider._get_alerts()
    print(f"Fetched {len(alerts)} alerts from Atatus")
    for alert in alerts:
        print(f"  - {alert.name}: {alert.severity} ({alert.status})")
