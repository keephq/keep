"""
FreshpingProvider integrates Keep with Freshping by Freshworks.
Freshping is an uptime monitoring service that checks website and API availability.
Supports receiving webhook notifications when checks go down or recover.
"""

import dataclasses
import datetime
from typing import Optional

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class FreshpingProviderAuthConfig:
    """
    FreshpingProviderAuthConfig holds the Freshping webhook secret for validating payloads.
    Freshping is primarily webhook-driven; there is no public REST API for pulling checks.
    """

    webhook_secret: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Freshping webhook secret token (optional, for signature validation)",
            "sensitive": True,
            "hint": "Set this in Freshping → Alerts → Webhook → Secret Token",
        },
    )


class FreshpingProvider(BaseProvider):
    """Receive uptime check alerts from Freshping via webhooks."""

    PROVIDER_DISPLAY_NAME = "Freshping"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="webhook",
            description="Receive Freshping webhook alerts",
            mandatory=True,
        ),
    ]

    # Freshping check_status → Keep AlertStatus
    STATUS_MAP = {
        "available": AlertStatus.RESOLVED,
        "unavailable": AlertStatus.FIRING,
        "unknown": AlertStatus.FIRING,
    }

    # Freshping check_status → Keep AlertSeverity
    SEVERITY_MAP = {
        "available": AlertSeverity.INFO,
        "unavailable": AlertSeverity.CRITICAL,
        "unknown": AlertSeverity.WARNING,
    }

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To receive Freshping alerts in Keep, set up a webhook alert contact in Freshping:

1. Log in to [freshping.io](https://www.freshping.io/) and navigate to **Alerts** in the sidebar.
2. Click **Alert Contacts** → **New Alert Contact**.
3. Select **Webhook** as the contact type.
4. Enter `{keep_webhook_api_url}` as the webhook URL.
5. In the **Custom Headers** section, add:
   - Key: `X-API-KEY`
   - Value: `{api_key}`
6. Optionally set a **Secret Token** (and store the same value as `webhook_secret` in the Keep provider configuration).
7. Save the alert contact.
8. Assign the contact to your checks: **Checks** → select a check → **Alert Contacts** → add the webhook contact.
"""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = FreshpingProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def validate_scopes(self) -> dict[str, bool | str]:
        # Freshping has no REST API for pulling data, so scope validation is always true
        return {"webhook": True}

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format a Freshping webhook payload into an AlertDto.

        Freshping sends a JSON payload with check details and the current status.
        Key fields:
          - check_id: unique check identifier
          - check_name: human-readable name
          - check_url: the monitored URL
          - check_status: "available" | "unavailable" | "unknown"
          - report_generated_at: ISO timestamp
          - response_time: response time in ms (when available)
          - summary: short description of the event
        """
        check_id = str(event.get("check_id", ""))
        check_name = event.get("check_name", "Unknown check")
        check_url = event.get("check_url", "")
        check_status = event.get("check_status", "unknown").lower()
        report_generated_at = event.get(
            "report_generated_at", datetime.datetime.utcnow().isoformat()
        )
        summary = event.get("summary", f"Check is {check_status}")
        response_time = event.get("response_time")

        labels = {
            "check_url": check_url,
        }
        if response_time is not None:
            labels["response_time_ms"] = str(response_time)

        return AlertDto(
            id=f"{check_id}-{report_generated_at}",
            name=check_name,
            description=summary,
            severity=FreshpingProvider.SEVERITY_MAP.get(check_status, AlertSeverity.HIGH),
            status=FreshpingProvider.STATUS_MAP.get(check_status, AlertStatus.FIRING),
            lastReceived=report_generated_at,
            url=check_url,
            source=["freshping"],
            labels=labels,
        )


if __name__ == "__main__":
    # Freshping is webhook-only, so this is just a test of _format_alert
    sample_event = {
        "check_id": 12345,
        "check_name": "Production API",
        "check_url": "https://api.example.com/health",
        "check_status": "unavailable",
        "report_generated_at": "2024-03-15T10:30:00Z",
        "summary": "Check is unavailable - connection timed out",
        "response_time": None,
    }

    alert = FreshpingProvider._format_alert(sample_event)
    print(f"Alert: {alert.name} - {alert.status} - {alert.severity}")
