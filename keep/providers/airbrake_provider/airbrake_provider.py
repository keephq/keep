"""
AirbrakeProvider is a class that provides a way to receive error alerts from
Airbrake via webhooks. Airbrake is an error and performance monitoring platform
that captures exceptions and crashes from web applications.
"""

import dataclasses

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class AirbrakeProviderAuthConfig:
    """
    AirbrakeProviderAuthConfig holds authentication information for the
    Airbrake provider. The project key and project ID are needed to validate
    the connection and pull error groups.
    """

    project_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Airbrake Project ID",
            "hint": "Found in your Airbrake project settings",
            "sensitive": False,
        }
    )

    project_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Airbrake Project Key (API key)",
            "hint": "Found in your Airbrake project settings under API Keys",
            "sensitive": True,
        }
    )


class AirbrakeProvider(BaseProvider):
    """Get error alerts from Airbrake into Keep."""

    PROVIDER_DISPLAY_NAME = "Airbrake"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring", "Application Performance"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_errors",
            description="Read error groups from Airbrake",
            mandatory=True,
            alias="Read Errors",
        )
    ]
    FINGERPRINT_FIELDS = ["id"]

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
💡 For more details on Airbrake webhooks, refer to the [Airbrake documentation](https://airbrake.io/docs/integrations/webhooks/).

### Connecting Airbrake to Keep

1. Log in to your [Airbrake dashboard](https://airbrake.io).
2. Navigate to your project and click **Settings** → **Integrations**.
3. Select **Webhook** from the list of integrations.
4. Set the **URL** to: `{keep_webhook_api_url}`
5. Add a custom HTTP header:
   - **Header**: `X-API-KEY: {api_key}`
6. Click **Save** to activate the webhook.

Airbrake will now forward new and resolved errors to Keep.
"""

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "warning": AlertSeverity.MEDIUM,
        "notice": AlertSeverity.LOW,
        "info": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "open": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "wontfix": AlertStatus.RESOLVED,
        "ignored": AlertStatus.RESOLVED,
    }

    AIRBRAKE_API_BASE = "https://api.airbrake.io/api/v4/projects"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AirbrakeProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            url = f"{self.AIRBRAKE_API_BASE}/{self.authentication_config.project_id}/groups"
            response = requests.get(
                url,
                params={"key": self.authentication_config.project_key, "limit": 1},
                timeout=10,
            )
            if response.status_code == 200:
                return {"read_errors": True}
            else:
                return {
                    "read_errors": f"HTTP {response.status_code}: {response.text[:200]}"
                }
        except Exception as e:
            return {"read_errors": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        """Pull open error groups from Airbrake."""
        self.logger.info("Pulling error groups from Airbrake")
        alerts = []
        page = 1

        while True:
            url = f"{self.AIRBRAKE_API_BASE}/{self.authentication_config.project_id}/groups"
            response = requests.get(
                url,
                params={
                    "key": self.authentication_config.project_key,
                    "resolved": False,
                    "limit": 25,
                    "page": page,
                },
                timeout=10,
            )
            if not response.ok:
                self.logger.error(
                    "Error fetching alerts from Airbrake: %s", response.text
                )
                break

            data = response.json()
            groups = data.get("groups", [])

            for group in groups:
                alert = self._group_to_alert(group)
                alerts.append(alert)

            # Stop if we've reached the last page
            if len(groups) < 25:
                break
            page += 1

        self.logger.info("Fetched %d error groups from Airbrake", len(alerts))
        return alerts

    def _group_to_alert(self, group: dict) -> AlertDto:
        errors = group.get("errors", [{}])
        first_error = errors[0] if errors else {}

        name = first_error.get("type") or group.get("context", {}).get("component", "Unknown Error")
        description = first_error.get("message", "")
        status_raw = group.get("resolved", False)
        status = AlertStatus.RESOLVED if status_raw else AlertStatus.FIRING

        severity = self.SEVERITIES_MAP.get(
            group.get("context", {}).get("severity", "error"), AlertSeverity.HIGH
        )

        alert = AlertDto(
            id=str(group.get("id", "")),
            name=name,
            description=description,
            status=status,
            severity=severity,
            occurrences=group.get("noticeCount", 0),
            environment=group.get("context", {}).get("environment"),
            url=group.get("url"),
            lastReceived=group.get("lastNoticeAt"),
            source=["airbrake"],
        )

        alert.fingerprint = AirbrakeProvider.get_alert_fingerprint(
            alert,
            fingerprint_fields=AirbrakeProvider.FINGERPRINT_FIELDS,
        )
        return alert

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format an Airbrake webhook payload into a Keep AlertDto.

        Airbrake webhook payload example:
        {
          "error": {
            "id": 12345,
            "error_message": "undefined method 'foo'",
            "error_class": "NoMethodError",
            "created_at": "2024-01-01T00:00:00Z",
            "environment": "production",
            "url": "https://airbrake.io/...",
            "action": "create"
          }
        }
        """
        error = event.get("error", event)

        action = error.get("action", "create")
        status = (
            AlertStatus.RESOLVED
            if action in ("resolve", "resolved")
            else AlertStatus.FIRING
        )

        name = (
            error.get("error_class")
            or error.get("type")
            or error.get("exception")
            or "Airbrake Error"
        )
        description = error.get("error_message") or error.get("message", "")
        alert_id = str(error.get("id", ""))
        environment = error.get("environment", "")
        url = error.get("url") or error.get("airbrake_url")

        alert = AlertDto(
            id=alert_id,
            name=name,
            description=description,
            status=status,
            severity=AlertSeverity.HIGH,
            environment=environment,
            url=url,
            source=["airbrake"],
            lastReceived=error.get("created_at"),
        )

        alert.fingerprint = AirbrakeProvider.get_alert_fingerprint(
            alert,
            fingerprint_fields=AirbrakeProvider.FINGERPRINT_FIELDS,
        )
        return alert


if __name__ == "__main__":
    pass
