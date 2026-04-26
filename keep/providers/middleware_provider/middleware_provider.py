"""
MiddlewareProvider is a class that provides alerting and observability integration
with Middleware.io (middleware.io), a full-stack observability platform.
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
class MiddlewareProviderAuthConfig:
    """
    MiddlewareProviderAuthConfig holds authentication configuration for Middleware.io.
    """

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Middleware.io API Key",
            "hint": "Found in your Middleware.io account under Settings > API Keys",
            "sensitive": True,
        },
    )

    account_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Middleware.io Account ID",
            "hint": "Your unique Middleware.io account identifier, found in the account settings",
        },
    )


class MiddlewareProvider(BaseProvider):
    """Receive and manage alerts from Middleware.io full-stack observability platform."""

    PROVIDER_DISPLAY_NAME = "Middleware.io"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring", "Cloud Infrastructure"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="alerts:read",
            description="Read alerts from Middleware.io",
            mandatory=True,
            alias="Read Alerts",
        ),
    ]

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
    }

    STATUS_MAP = {
        "firing": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
    }

    FINGERPRINT_FIELDS = ["id", "alert_rule_id"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = MiddlewareProviderAuthConfig(
            **self.config.authentication
        )

    def __get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.authentication_config.api_key}",
            "Content-Type": "application/json",
        }

    def __get_base_url(self) -> str:
        return f"https://app.middleware.io/api/v1"

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate provider scopes by testing the alerts endpoint."""
        scopes = {}
        try:
            response = requests.get(
                f"{self.__get_base_url()}/alerts",
                headers=self.__get_headers(),
                params={"account_id": self.authentication_config.account_id, "limit": 1},
                timeout=10,
            )
            if response.status_code == 200:
                scopes["alerts:read"] = True
            else:
                scopes["alerts:read"] = (
                    f"Unable to read alerts from Middleware.io, status code: {response.status_code}"
                )
        except Exception as e:
            self.logger.exception("Failed to validate Middleware.io scopes")
            scopes["alerts:read"] = str(e)
        return scopes

    def _get_alerts(self) -> List[AlertDto]:
        """Pull alerts from Middleware.io."""
        self.logger.info("Fetching alerts from Middleware.io")
        alerts = []
        try:
            response = requests.get(
                f"{self.__get_base_url()}/alerts",
                headers=self.__get_headers(),
                params={
                    "account_id": self.authentication_config.account_id,
                    "limit": 100,
                },
                timeout=10,
            )
            if not response.ok:
                self.logger.error(
                    "Failed to fetch alerts from Middleware.io: %s", response.text
                )
                raise Exception(
                    f"Failed to fetch alerts from Middleware.io: {response.status_code}"
                )

            data = response.json()
            items = data.get("data", data) if isinstance(data, dict) else data
            if not isinstance(items, list):
                items = []

            for item in items:
                severity_raw = item.get("severity", "info").lower()
                status_raw = item.get("status", "firing").lower()
                alert = AlertDto(
                    id=str(item.get("id", "")),
                    name=item.get("name", item.get("alert_rule_name", "Middleware Alert")),
                    severity=self.SEVERITIES_MAP.get(severity_raw, AlertSeverity.INFO),
                    status=self.STATUS_MAP.get(status_raw, AlertStatus.FIRING),
                    lastReceived=datetime.datetime.fromisoformat(
                        item.get("created_at", datetime.datetime.utcnow().isoformat())
                    ),
                    description=item.get("description", ""),
                    source=["middleware"],
                    labels=item.get("labels", {}),
                    fingerprint=str(item.get("id", "")),
                    alert_rule_id=item.get("alert_rule_id"),
                )
                alerts.append(alert)
        except Exception as e:
            self.logger.error("Error fetching alerts from Middleware.io: %s", e)
        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """Format a Middleware.io webhook payload into an AlertDto."""
        severity_raw = event.get("severity", "info").lower()
        status_raw = event.get("status", "firing").lower()

        severity = MiddlewareProvider.SEVERITIES_MAP.get(severity_raw, AlertSeverity.INFO)
        status = MiddlewareProvider.STATUS_MAP.get(status_raw, AlertStatus.FIRING)

        created_at = event.get("created_at") or event.get("timestamp")
        if created_at:
            try:
                last_received = datetime.datetime.fromisoformat(created_at)
            except ValueError:
                last_received = datetime.datetime.utcnow()
        else:
            last_received = datetime.datetime.utcnow()

        return AlertDto(
            id=str(event.get("id", "")),
            name=event.get("name", event.get("alert_rule_name", "Middleware Alert")),
            severity=severity,
            status=status,
            lastReceived=last_received,
            description=event.get("description", ""),
            source=["middleware"],
            labels=event.get("labels", {}),
            fingerprint=str(event.get("id", "")),
            alert_rule_id=event.get("alert_rule_id"),
            service=event.get("service", ""),
            environment=event.get("environment", ""),
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    api_key = os.environ.get("MIDDLEWARE_API_KEY")
    account_id = os.environ.get("MIDDLEWARE_ACCOUNT_ID")
    if not api_key or not account_id:
        raise Exception("MIDDLEWARE_API_KEY and MIDDLEWARE_ACCOUNT_ID must be set")

    config = ProviderConfig(
        description="Middleware.io Provider",
        authentication={
            "api_key": api_key,
            "account_id": account_id,
        },
    )
    provider = MiddlewareProvider(
        context_manager, provider_id="middleware-test", config=config
    )
    alerts = provider._get_alerts()
    print(f"Fetched {len(alerts)} alerts from Middleware.io")
    for alert in alerts:
        print(f"  - {alert.name}: {alert.severity} ({alert.status})")
