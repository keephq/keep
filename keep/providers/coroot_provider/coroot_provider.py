"""
CorootProvider is a class that provides a way to read data from Coroot.
"""

import dataclasses
import datetime
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider, ProviderHealthMixin
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class CorootProviderAuthConfig:
    url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Coroot server URL",
            "hint": "https://coroot.example.com",
            "validation": "any_http_url",
        }
    )
    api_key: str = dataclasses.field(
        metadata={
            "description": "Coroot API key (if authentication is enabled)",
            "sensitive": True,
        },
        default="",
    )
    project_id: str = dataclasses.field(
        metadata={
            "description": "Coroot project ID",
            "hint": "Leave empty for default project",
        },
        default="",
    )
    verify: bool = dataclasses.field(
        metadata={
            "description": "Verify SSL certificates",
            "hint": "Set to false to allow self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )


class CorootProvider(BaseProvider, ProviderHealthMixin):
    """Get alerts from Coroot into Keep."""

    PROVIDER_DISPLAY_NAME = "Coroot"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connectivity",
            description="Connectivity Test",
            mandatory=True,
        )
    ]

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "warn": AlertSeverity.WARNING,
        "medium": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
    }

    STATUS_MAP = {
        "firing": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "open": AlertStatus.FIRING,
        "closed": AlertStatus.RESOLVED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for Coroot's provider.
        """
        self.authentication_config = CorootProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        validated_scopes = {"connectivity": True}
        try:
            self._get_alerts()
        except Exception as e:
            validated_scopes["connectivity"] = str(e)
        return validated_scopes

    def _get_auth_headers(self) -> dict:
        """Get authentication headers if API key is provided."""
        headers = {"Content-Type": "application/json"}
        if self.authentication_config.api_key:
            headers["Authorization"] = f"Bearer {self.authentication_config.api_key}"
        return headers

    def _get_project_param(self) -> dict:
        """Get project query parameter if project_id is provided."""
        params = {}
        if self.authentication_config.project_id:
            params["project"] = self.authentication_config.project_id
        return params

    def _get_alerts(self) -> list[AlertDto]:
        """Fetch alerts from Coroot API."""
        url = f"{self.authentication_config.url}/api/alerts"
        headers = self._get_auth_headers()
        params = self._get_project_param()

        response = requests.get(
            url,
            headers=headers,
            params=params,
            verify=self.authentication_config.verify,
            timeout=30,
        )
        response.raise_for_status()

        alerts_data = response.json()
        alert_dtos = self._format_alerts(alerts_data)
        return alert_dtos

    @staticmethod
    def _format_alerts(
        data: dict | list, provider_instance: Optional["CorootProvider"] = None
    ) -> list[AlertDto]:
        """Format Coroot alerts into Keep AlertDto format."""
        alert_dtos = []

        # Handle both dict and list responses
        if isinstance(data, dict):
            alerts = data.get("alerts", data.get("items", []))
        elif isinstance(data, list):
            alerts = data
        else:
            return alert_dtos

        for alert in alerts:
            if not isinstance(alert, dict):
                continue

            # Extract alert fields
            alert_id = alert.get("id") or alert.get("alert_id") or alert.get("name")
            name = alert.get("name") or alert.get("alertname") or alert_id
            description = alert.get("description") or alert.get("summary") or alert.get("message", name)

            # Extract labels/annotations
            labels = alert.get("labels", {})
            if isinstance(labels, dict):
                labels = {k.lower(): v for k, v in labels.items()}

            # Map severity
            severity_str = (
                alert.get("severity")
                or labels.get("severity", "info")
            ).lower()
            severity = CorootProvider.SEVERITIES_MAP.get(severity_str, AlertSeverity.INFO)

            # Map status
            status_str = (
                alert.get("status")
                or alert.get("state")
                or labels.get("status", "firing")
            ).lower()
            status = CorootProvider.STATUS_MAP.get(status_str, AlertStatus.FIRING)

            # Extract service name
            service = (
                labels.get("service")
                or labels.get("application")
                or labels.get("app")
                or alert.get("service")
                or alert.get("application")
            )

            # Extract timestamp
            timestamp_str = alert.get("timestamp") or alert.get("created_at") or alert.get("starts_at")
            try:
                if timestamp_str:
                    timestamp = datetime.datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                else:
                    timestamp = datetime.datetime.now(datetime.timezone.utc)
            except (ValueError, TypeError):
                timestamp = datetime.datetime.now(datetime.timezone.utc)

            # Build AlertDto
            alert_dto = AlertDto(
                id=str(alert_id) if alert_id else None,
                name=name,
                description=description,
                status=status,
                severity=severity,
                service=service,
                timestamp=timestamp,
                source=["coroot"],
                labels=labels,
                annotations=alert.get("annotations", {}),
                raw_payload=alert,
            )
            alert_dtos.append(alert_dto)

        return alert_dtos

    def dispose(self):
        """
        Dispose of the provider.
        """
        pass

