"""
CronitorProvider integrates Keep with Cronitor.io.
Cronitor monitors cron jobs, heartbeats, and uptime checks.
Supports pulling monitor alerts via the Cronitor API and receiving
webhook notifications when monitors fail or recover.
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
class CronitorProviderAuthConfig:
    """
    CronitorProviderAuthConfig holds the Cronitor API key.
    """

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Cronitor API Key",
            "sensitive": True,
            "hint": "Found at cronitor.io → Settings → API Access",
        },
    )

    environment: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Filter monitors by environment name (e.g. 'production')",
            "sensitive": False,
        },
    )


class CronitorProvider(BaseProvider):
    """Pull failing monitors from Cronitor and receive webhook alerts for job failures."""

    PROVIDER_DISPLAY_NAME = "Cronitor"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_monitors",
            description="Read monitor status from Cronitor",
            mandatory=True,
        ),
    ]

    CRONITOR_API_URL = "https://cronitor.io/api"

    # Cronitor monitor state → Keep AlertStatus
    STATUS_MAP = {
        "healthy": AlertStatus.RESOLVED,
        "failing": AlertStatus.FIRING,
        "degraded": AlertStatus.FIRING,
        "unknown": AlertStatus.FIRING,
        "paused": AlertStatus.SUPPRESSED,
    }

    # Cronitor monitor state → Keep AlertSeverity
    SEVERITY_MAP = {
        "healthy": AlertSeverity.INFO,
        "failing": AlertSeverity.CRITICAL,
        "degraded": AlertSeverity.WARNING,
        "unknown": AlertSeverity.WARNING,
        "paused": AlertSeverity.LOW,
    }

    # Cronitor webhook event type → Keep AlertStatus
    EVENT_STATUS_MAP = {
        "monitor.failure": AlertStatus.FIRING,
        "monitor.recovery": AlertStatus.RESOLVED,
        "monitor.degraded": AlertStatus.FIRING,
        "monitor.alert": AlertStatus.FIRING,
        "heartbeat.missed": AlertStatus.FIRING,
    }

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send alerts from Cronitor to Keep, set up a webhook notification channel:

1. Log in to [Cronitor](https://cronitor.io/) and click your account icon in the top right.
2. Go to **Settings** → **Integrations**.
3. Under **Custom Webhooks**, click **Add Webhook**.
4. Set the **URL** to `{keep_webhook_api_url}`.
5. Add a custom header: key `X-API-KEY`, value `{api_key}`.
6. Save the webhook.
7. Assign the webhook to a monitor: open a monitor → **Notifications** → select the webhook.
"""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = CronitorProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _get_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
        }

    def _get_auth(self):
        """Cronitor uses HTTP Basic Auth with API key as username."""
        return (self.authentication_config.api_key, "")

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            response = requests.get(
                f"{self.CRONITOR_API_URL}/monitors",
                auth=self._get_auth(),
                headers=self._get_headers(),
                params={"limit": 1},
                timeout=10,
            )
            if response.status_code == 200:
                return {"read_monitors": True}
            return {
                "read_monitors": f"HTTP {response.status_code}: {response.text[:200]}"
            }
        except Exception as e:
            self.logger.error("Error validating Cronitor scopes: %s", e)
            return {"read_monitors": str(e)}

    def _get_alerts(self) -> List[AlertDto]:
        alerts = []
        try:
            self.logger.info("Pulling failing monitors from Cronitor")
            params = {"limit": 100}
            if self.authentication_config.environment:
                params["environment"] = self.authentication_config.environment

            page = 1
            while True:
                params["page"] = page
                response = requests.get(
                    f"{self.CRONITOR_API_URL}/monitors",
                    auth=self._get_auth(),
                    headers=self._get_headers(),
                    params=params,
                    timeout=30,
                )
                if not response.ok:
                    self.logger.error(
                        "Failed to fetch Cronitor monitors: %s", response.text
                    )
                    break

                data = response.json()
                monitors = data.get("monitors", [])
                for monitor in monitors:
                    state = monitor.get("status", "unknown")
                    # Only surface non-healthy monitors as active alerts
                    if state == "healthy":
                        continue
                    latest_event = monitor.get("latest_event", {})
                    last_received = (
                        latest_event.get("happened_at")
                        or monitor.get("updated_at")
                        or datetime.datetime.utcnow().isoformat()
                    )
                    alerts.append(
                        AlertDto(
                            id=monitor.get("key", str(monitor.get("id", ""))),
                            name=monitor.get("name", "Unknown monitor"),
                            description=monitor.get("schedule", ""),
                            severity=self.SEVERITY_MAP.get(state, AlertSeverity.HIGH),
                            status=self.STATUS_MAP.get(state, AlertStatus.FIRING),
                            lastReceived=last_received,
                            url=f"https://cronitor.io/monitors/{monitor.get('key', '')}",
                            source=["cronitor"],
                            labels={
                                "type": monitor.get("type", ""),
                                "environment": self.authentication_config.environment or "",
                                "key": monitor.get("key", ""),
                            },
                        )
                    )

                # Pagination
                total_count = data.get("total_count", 0)
                if page * 100 >= total_count:
                    break
                page += 1

        except Exception as e:
            self.logger.error("Error pulling Cronitor monitors: %s", e)
        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format a Cronitor webhook payload into an AlertDto.
        Cronitor sends JSON payloads with monitor and event information.
        """
        monitor = event.get("monitor", {})
        event_type = event.get("event_type", "monitor.failure")
        happened_at = event.get("happened_at") or datetime.datetime.utcnow().isoformat()

        monitor_name = monitor.get("name", "Unknown monitor")
        monitor_key = monitor.get("key", "")
        state = monitor.get("status", "failing")

        return AlertDto(
            id=f"{monitor_key}-{happened_at}",
            name=monitor_name,
            description=event.get("message", f"Monitor event: {event_type}"),
            severity=CronitorProvider.SEVERITY_MAP.get(state, AlertSeverity.CRITICAL),
            status=CronitorProvider.EVENT_STATUS_MAP.get(event_type, AlertStatus.FIRING),
            lastReceived=happened_at,
            url=f"https://cronitor.io/monitors/{monitor_key}",
            source=["cronitor"],
            labels={
                "event_type": event_type,
                "monitor_key": monitor_key,
                "type": monitor.get("type", ""),
                "environment": event.get("environment", ""),
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

    api_key = os.environ.get("CRONITOR_API_KEY")
    if not api_key:
        raise Exception("CRONITOR_API_KEY is not set")

    config = ProviderConfig(
        description="Cronitor Provider",
        authentication={"api_key": api_key},
    )

    provider = CronitorProvider(
        context_manager,
        provider_id="cronitor-test",
        config=config,
    )

    monitors = provider._get_alerts()
    print(f"Found {len(monitors)} failing monitors")
    for m in monitors:
        print(m)
