"""
BetterstackProvider integrates Keep with Betterstack (formerly Better Uptime).
Supports pulling incidents from the Betterstack API and receiving real-time
webhook notifications when monitors go down or incidents are created.
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
class BetterstackProviderAuthConfig:
    """
    BetterstackProviderAuthConfig holds the Betterstack API token.
    """

    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Betterstack API Token",
            "sensitive": True,
            "hint": "Found at betterstack.com → Uptime → Settings → API",
        },
    )

    team_name: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Betterstack team name (subdomain), e.g. 'myteam' for myteam.betteruptime.com",
            "sensitive": False,
        },
    )


class BetterstackProvider(BaseProvider):
    """Pull incidents and monitor status from Betterstack Uptime and receive webhook alerts."""

    PROVIDER_DISPLAY_NAME = "Betterstack"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_incidents",
            description="Read incidents from Betterstack",
            mandatory=True,
        ),
    ]

    BETTERSTACK_API_URL = "https://uptime.betterstack.com/api/v2"

    # Betterstack incident status → Keep AlertStatus
    STATUS_MAP = {
        "started": AlertStatus.FIRING,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "resolved": AlertStatus.RESOLVED,
    }

    # Betterstack cause → Keep AlertSeverity
    SEVERITY_MAP = {
        "down": AlertSeverity.CRITICAL,
        "paused": AlertSeverity.LOW,
        "ssl_expiring": AlertSeverity.WARNING,
        "ssl_expired": AlertSeverity.CRITICAL,
        "domain_expiring": AlertSeverity.WARNING,
        "domain_expired": AlertSeverity.CRITICAL,
        "maintenance": AlertSeverity.INFO,
    }

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send alerts from Betterstack to Keep, configure an on-call policy with a webhook escalation:

1. Log in to [Betterstack](https://betterstack.com/) and navigate to **Uptime**.
2. In the left sidebar, go to **On-call** → **Alert destinations**.
3. Click **New alert destination** and choose **Webhook**.
4. Set the **Webhook URL** to `{keep_webhook_api_url}`.
5. Add a request header: key `X-API-KEY`, value `{api_key}`.
6. Save the alert destination.
7. Attach the destination to an **on-call policy** under **On-call → Policies**.
8. Assign that policy to the monitors you want to track.
"""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = BetterstackProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.authentication_config.api_token}",
            "Content-Type": "application/json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            response = requests.get(
                f"{self.BETTERSTACK_API_URL}/incidents",
                headers=self._get_headers(),
                timeout=10,
            )
            if response.status_code == 200:
                return {"read_incidents": True}
            return {
                "read_incidents": f"HTTP {response.status_code}: {response.text[:200]}"
            }
        except Exception as e:
            self.logger.error("Error validating Betterstack scopes: %s", e)
            return {"read_incidents": str(e)}

    def _get_alerts(self) -> List[AlertDto]:
        alerts = []
        try:
            self.logger.info("Pulling incidents from Betterstack")
            url = f"{self.BETTERSTACK_API_URL}/incidents"
            while url:
                response = requests.get(
                    url, headers=self._get_headers(), timeout=30
                )
                if not response.ok:
                    self.logger.error(
                        "Failed to fetch Betterstack incidents: %s", response.text
                    )
                    break
                data = response.json()
                for item in data.get("data", []):
                    attrs = item.get("attributes", {})
                    monitor_attrs = (
                        item.get("relationships", {})
                        .get("monitor", {})
                        .get("data", {})
                    )
                    cause = attrs.get("cause", "down")
                    status = attrs.get("status", "started")
                    started_at = attrs.get("started_at")
                    resolved_at = attrs.get("resolved_at")
                    last_received = resolved_at or started_at or datetime.datetime.utcnow().isoformat()
                    alerts.append(
                        AlertDto(
                            id=str(item.get("id", "")),
                            name=f"Monitor incident: {attrs.get('name', 'Unknown')}",
                            description=f"Monitor is {cause}",
                            severity=self.SEVERITY_MAP.get(cause, AlertSeverity.HIGH),
                            status=self.STATUS_MAP.get(status, AlertStatus.FIRING),
                            lastReceived=last_received,
                            startedAt=started_at,
                            url=attrs.get("url", ""),
                            source=["betterstack"],
                            labels={"cause": cause, "monitor_id": str(monitor_attrs.get("id", ""))},
                        )
                    )
                # Handle pagination
                pagination = data.get("pagination", {})
                url = pagination.get("next")
        except Exception as e:
            self.logger.error("Error pulling Betterstack incidents: %s", e)
        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format a Betterstack webhook payload into an AlertDto.
        Betterstack sends webhook payloads with incident data nested under "data".
        """
        data = event.get("data", event)
        attrs = data.get("attributes", data)

        monitor_name = attrs.get("monitor_summary", attrs.get("name", "Unknown monitor"))
        cause = attrs.get("cause", "down")
        status = attrs.get("status", "started")
        started_at = attrs.get("started_at") or attrs.get("started_time")
        resolved_at = attrs.get("resolved_at") or attrs.get("resolved_time")
        last_received = resolved_at or started_at or datetime.datetime.utcnow().isoformat()

        return AlertDto(
            id=str(data.get("id", "")),
            name=f"Monitor incident: {monitor_name}",
            description=f"Monitor is {cause}",
            severity=BetterstackProvider.SEVERITY_MAP.get(cause, AlertSeverity.HIGH),
            status=BetterstackProvider.STATUS_MAP.get(status, AlertStatus.FIRING),
            lastReceived=last_received,
            startedAt=started_at,
            url=attrs.get("url", ""),
            source=["betterstack"],
            labels={
                "cause": cause,
                "monitor_url": attrs.get("monitor_url", ""),
                "team": attrs.get("team_name", ""),
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

    api_token = os.environ.get("BETTERSTACK_API_TOKEN")
    if not api_token:
        raise Exception("BETTERSTACK_API_TOKEN is not set")

    config = ProviderConfig(
        description="Betterstack Provider",
        authentication={"api_token": api_token},
    )

    provider = BetterstackProvider(
        context_manager,
        provider_id="betterstack-test",
        config=config,
    )

    incidents = provider._get_alerts()
    print(f"Found {len(incidents)} incidents")
    for inc in incidents:
        print(inc)
