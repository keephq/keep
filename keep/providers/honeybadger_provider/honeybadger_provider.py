"""
HoneybadgerProvider is a class that integrates with Honeybadger error and uptime
monitoring, allowing Keep to pull faults as alerts and receive webhook notifications.
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
class HoneybadgerProviderAuthConfig:
    """
    HoneybadgerProviderAuthConfig holds authentication for the Honeybadger provider.
    """

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Honeybadger Personal Auth Token",
            "hint": "Found at https://app.honeybadger.io/users/auth_token",
            "sensitive": True,
        },
    )
    project_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Honeybadger Project ID",
            "hint": "Found in the project URL: app.honeybadger.io/projects/<project_id>",
        },
    )


class HoneybadgerProvider(BaseProvider):
    """Pull error faults and uptime alerts from Honeybadger monitoring platform."""

    PROVIDER_DISPLAY_NAME = "Honeybadger"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated",
            mandatory=True,
            alias="authenticated",
        ),
    ]

    # Honeybadger fault states → Keep AlertStatus
    FAULT_STATUS_MAP = {
        "resolved": AlertStatus.RESOLVED,
        "ignored": AlertStatus.SUPPRESSED,
        "unresolved": AlertStatus.FIRING,
    }

    # Map Honeybadger notice/fault kinds to severity
    SEVERITY_MAP = {
        "error": AlertSeverity.HIGH,
        "notice": AlertSeverity.INFO,
        "warning": AlertSeverity.WARNING,
        "critical": AlertSeverity.CRITICAL,
    }

    BASE_URL = "https://app.honeybadger.io/v2"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """Validate the provider configuration."""
        self.authentication_config = HoneybadgerProviderAuthConfig(
            **self.config.authentication
        )

    def __get_headers(self) -> dict:
        return {
            "X-Api-Key": self.authentication_config.api_key,
            "Accept": "application/json",
        }

    def __get_project_url(self, path: str) -> str:
        return f"{self.BASE_URL}/projects/{self.authentication_config.project_id}/{path}"

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate API key by fetching project details."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/projects/{self.authentication_config.project_id}",
                headers=self.__get_headers(),
                timeout=10,
            )
            if response.status_code == 200:
                return {"authenticated": True}
            elif response.status_code == 401:
                return {"authenticated": "Invalid or missing API key"}
            elif response.status_code == 403:
                return {"authenticated": "Access denied — check project ID and permissions"}
            elif response.status_code == 404:
                return {"authenticated": "Project not found — check project ID"}
            else:
                return {
                    "authenticated": f"Unexpected status code: {response.status_code}"
                }
        except Exception as e:
            self.logger.error("Error validating Honeybadger scopes: %s", e)
            return {"authenticated": f"Error connecting to Honeybadger: {e}"}

    def _get_alerts(self) -> List[AlertDto]:
        """Pull unresolved faults from Honeybadger and return as AlertDto objects."""
        alerts = []
        try:
            self.logger.info("Fetching faults from Honeybadger project %s", self.authentication_config.project_id)
            page = 1

            while True:
                response = requests.get(
                    self.__get_project_url("faults"),
                    headers=self.__get_headers(),
                    params={
                        "q": "-is:resolved",
                        "page": page,
                    },
                    timeout=30,
                )

                if not response.ok:
                    self.logger.error(
                        "Failed to fetch faults from Honeybadger: %s", response.text
                    )
                    break

                data = response.json()
                faults = data.get("results", [])

                if not faults:
                    break

                for fault in faults:
                    alerts.append(self.__fault_to_alert(fault))

                # Honeybadger paginates with links
                links = data.get("links", {})
                if not links.get("next"):
                    break
                page += 1

        except Exception as e:
            self.logger.error("Error fetching faults from Honeybadger: %s", e)

        return alerts

    def __fault_to_alert(self, fault: dict) -> AlertDto:
        """Convert a Honeybadger fault dict to an AlertDto."""
        fault_id = str(fault.get("id", "unknown"))
        klass = fault.get("klass", "UnknownError")
        message = fault.get("message", "")
        component = fault.get("component", "")
        action = fault.get("action", "")
        resolved = fault.get("resolved", False)
        ignored = fault.get("ignored", False)

        if resolved:
            status = AlertStatus.RESOLVED
        elif ignored:
            status = AlertStatus.SUPPRESSED
        else:
            status = AlertStatus.FIRING

        # Determine severity from error class name heuristic
        lower_klass = klass.lower()
        if any(w in lower_klass for w in ["fatal", "critical", "panic"]):
            severity = AlertSeverity.CRITICAL
        elif any(w in lower_klass for w in ["error", "exception", "fail"]):
            severity = AlertSeverity.HIGH
        elif "warning" in lower_klass:
            severity = AlertSeverity.WARNING
        else:
            severity = AlertSeverity.HIGH

        last_notice = fault.get("last_notice_at", fault.get("created_at"))
        if last_notice:
            try:
                last_received = datetime.datetime.fromisoformat(
                    last_notice.replace("Z", "+00:00")
                ).isoformat()
            except (ValueError, AttributeError):
                last_received = datetime.datetime.utcnow().isoformat()
        else:
            last_received = datetime.datetime.utcnow().isoformat()

        project_id = self.authentication_config.project_id
        url = f"https://app.honeybadger.io/projects/{project_id}/faults/{fault_id}"

        description = message
        if component:
            description = f"{component}#{action}: {message}" if action else f"{component}: {message}"

        return AlertDto(
            id=fault_id,
            name=klass,
            severity=severity,
            status=status,
            lastReceived=last_received,
            description=description,
            source=["honeybadger"],
            url=url,
            labels={
                "component": component,
                "action": action,
                "notices_count": str(fault.get("notices_count", 0)),
                "environment": fault.get("environment", ""),
            },
            fingerprint=fault_id,
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """Format a Honeybadger webhook payload into an AlertDto."""
        fault = event.get("fault", event)
        fault_id = str(fault.get("id", event.get("id", "unknown")))
        klass = fault.get("klass", "UnknownError")
        message = fault.get("message", "")
        component = fault.get("component", "")
        action = fault.get("action", "")
        trigger = event.get("trigger", "occurrence")

        # Map webhook trigger to status
        if trigger in ("resolved", "resolve"):
            status = AlertStatus.RESOLVED
        elif trigger in ("ignored", "ignore"):
            status = AlertStatus.SUPPRESSED
        else:
            status = AlertStatus.FIRING

        # Severity from class name
        lower_klass = klass.lower()
        if any(w in lower_klass for w in ["fatal", "critical", "panic"]):
            severity = AlertSeverity.CRITICAL
        elif "warning" in lower_klass:
            severity = AlertSeverity.WARNING
        else:
            severity = AlertSeverity.HIGH

        project = event.get("project", {})
        project_id = project.get("id", "")
        url = f"https://app.honeybadger.io/projects/{project_id}/faults/{fault_id}"

        description = message
        if component:
            description = f"{component}#{action}: {message}" if action else f"{component}: {message}"

        return AlertDto(
            id=fault_id,
            name=klass,
            severity=severity,
            status=status,
            lastReceived=datetime.datetime.utcnow().isoformat(),
            description=description,
            source=["honeybadger"],
            url=url,
            labels={
                "component": component,
                "action": action,
                "trigger": trigger,
                "project": project.get("name", ""),
            },
            fingerprint=fault_id,
        )
