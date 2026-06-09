"""SquadcastProvider - Squadcast incident management integration for Keep."""

import dataclasses
import typing

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SquadcastProviderAuthConfig:
    """Squadcast authentication configuration."""

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Squadcast API Refresh Token",
            "sensitive": True,
            "hint": "Obtain from Squadcast Settings > API Tokens",
        }
    )
    webhook_url: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "Squadcast Incident Webhook URL (for creating incidents without full API)",
            "sensitive": True,
            "hint": "e.g. https://api.squadcast.com/v2/incidents/api/...",
        },
    )
    api_url: str = dataclasses.field(
        default="https://api.squadcast.com",
        metadata={
            "required": False,
            "description": "Squadcast API Base URL",
        },
    )


class SquadcastProvider(BaseProvider):
    """Manage incidents and alerts in Squadcast."""

    PROVIDER_DISPLAY_NAME = "Squadcast"
    PROVIDER_CATEGORY = ["Incident Management"]
    PROVIDER_TAGS = ["alert", "incident-management", "oncall"]
    PROVIDER_COMING_SOON = False

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated to Squadcast",
            mandatory=True,
            alias="Authenticated",
        ),
    ]

    SEVERITIES_MAP = {
        "P1": AlertSeverity.CRITICAL,
        "P2": AlertSeverity.HIGH,
        "P3": AlertSeverity.WARNING,
        "P4": AlertSeverity.INFO,
        "P5": AlertSeverity.LOW,
    }

    STATUS_MAP = {
        "triggered": AlertStatus.FIRING,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "resolved": AlertStatus.RESOLVED,
        "suppressed": AlertStatus.SUPPRESSED,
    }

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self._access_token = None

    @property
    def access_token(self) -> str:
        if self._access_token is None:
            self._access_token = self._get_access_token()
        return self._access_token

    def _get_access_token(self) -> str:
        """Exchange refresh token for an access token."""
        url = f"{self.authentication_config.api_url}/v3/oauth/access-token"
        response = requests.get(
            url,
            headers={"X-Refresh-Token": self.authentication_config.api_key},
            timeout=10,
        )
        if response.status_code != 200:
            raise Exception(
                f"Failed to obtain Squadcast access token: {response.status_code} {response.text}"
            )
        data = response.json()
        token = data.get("data", {}).get("access_token", "")
        if not token:
            raise Exception("Empty access token received from Squadcast")
        return token

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def validate_config(self):
        self.authentication_config = SquadcastProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate provider scopes/authentication."""
        try:
            self._get_access_token()
            return {"authenticated": True}
        except Exception as e:
            self.logger.exception("Error validating Squadcast scopes")
            return {"authenticated": str(e)}

    def dispose(self):
        pass

    def _notify(
        self,
        message: str = "",
        description: str = "",
        tags: typing.Optional[dict] = None,
        priority: str = "",
        status: str = "trigger",
        event_id: str = "",
        service_id: str = "",
        escalation_policy_id: str = "",
        **kwargs: typing.Any,
    ) -> dict:
        """Create or update an incident in Squadcast.

        Args:
            message: Short summary of the incident.
            description: Detailed description.
            tags: Key-value tags to attach.
            priority: Priority level (P1-P5).
            status: One of trigger, acknowledge, resolve.
            event_id: Unique event ID for deduplication.
            service_id: Squadcast service ID (required for API mode).
            escalation_policy_id: Escalcast escalation policy ID (required for API mode).
        """
        self.logger.info(
            "Notifying Squadcast",
            extra={"message": message, "status": status},
        )

        # Prefer webhook URL if configured (simpler integration)
        if self.authentication_config.webhook_url:
            return self._notify_via_webhook(
                message=message,
                description=description,
                tags=tags,
                priority=priority,
                status=status,
                event_id=event_id,
            )

        return self._notify_via_api(
            message=message,
            description=description,
            tags=tags,
            priority=priority,
            status=status,
            event_id=event_id,
            service_id=service_id,
            escalation_policy_id=escalation_policy_id,
        )

    def _notify_via_webhook(
        self,
        message: str,
        description: str,
        tags: typing.Optional[dict],
        priority: str,
        status: str,
        event_id: str,
    ) -> dict:
        """Send incident via Squadcast incident webhook."""
        payload: dict[str, typing.Any] = {
            "message": message,
            "description": description or message,
        }
        if tags:
            payload["tags"] = tags
        if priority:
            payload["priority"] = priority
        if event_id:
            payload["event_id"] = event_id
        if status:
            payload["status"] = status

        response = requests.post(
            self.authentication_config.webhook_url,
            json=payload,
            timeout=10,
        )
        if response.status_code not in (200, 201, 202):
            raise Exception(
                f"Failed to create Squadcast incident via webhook: "
                f"{response.status_code} {response.text}"
            )
        self.logger.info("Successfully notified Squadcast via webhook")
        return response.json() if response.text else {"status": "ok"}

    def _notify_via_api(
        self,
        message: str,
        description: str,
        tags: typing.Optional[dict],
        priority: str,
        status: str,
        event_id: str,
        service_id: str,
        escalation_policy_id: str,
    ) -> dict:
        """Create incident via Squadcast REST API."""
        if not service_id:
            raise Exception(
                "service_id is required when using API mode (no webhook_url configured)"
            )
        if not escalation_policy_id:
            raise Exception(
                "escalation_policy_id is required when using API mode"
            )

        payload: dict[str, typing.Any] = {
            "message": message,
            "description": description or message,
            "service_id": service_id,
            "escalation_policy_id": escalation_policy_id,
        }
        if tags:
            payload["tags"] = tags
        if priority:
            payload["priority"] = priority
        if event_id:
            payload["event_id"] = event_id
        if status:
            payload["status"] = status

        response = requests.post(
            f"{self.authentication_config.api_url}/v3/incidents",
            headers=self._get_headers(),
            json=payload,
            timeout=10,
        )
        if response.status_code not in (200, 201, 202):
            raise Exception(
                f"Failed to create Squadcast incident via API: "
                f"{response.status_code} {response.text}"
            )
        self.logger.info("Successfully notified Squadcast via API")
        return response.json()

    def _query(
        self,
        query_type: str = "incidents",
        **kwargs: typing.Any,
    ) -> list[dict]:
        """Query Squadcast resources.

        Args:
            query_type: One of 'incidents', 'services', 'escalation_policies'.
        """
        if query_type == "incidents":
            return self._get_incidents(**kwargs)
        elif query_type == "services":
            return self._get_services(**kwargs)
        elif query_type == "escalation_policies":
            return self._get_escalation_policies(**kwargs)
        else:
            raise Exception(f"Unknown query type: {query_type}")

    def _get_incidents(self, **kwargs: typing.Any) -> list[dict]:
        """Retrieve incidents from Squadcast."""
        response = requests.get(
            f"{self.authentication_config.api_url}/v3/incidents",
            headers=self._get_headers(),
            params=kwargs,
            timeout=30,
        )
        if response.status_code != 200:
            raise Exception(
                f"Failed to get incidents: {response.status_code} {response.text}"
            )
        return response.json().get("data", [])

    def _get_services(self, **kwargs: typing.Any) -> list[dict]:
        """Retrieve services from Squadcast."""
        response = requests.get(
            f"{self.authentication_config.api_url}/v3/services",
            headers=self._get_headers(),
            params=kwargs,
            timeout=30,
        )
        if response.status_code != 200:
            raise Exception(
                f"Failed to get services: {response.status_code} {response.text}"
            )
        return response.json().get("data", [])

    def _get_escalation_policies(self, **kwargs: typing.Any) -> list[dict]:
        """Retrieve escalation policies from Squadcast."""
        response = requests.get(
            f"{self.authentication_config.api_url}/v3/escalation-policies",
            headers=self._get_headers(),
            params=kwargs,
            timeout=30,
        )
        if response.status_code != 200:
            raise Exception(
                f"Failed to get escalation policies: {response.status_code} {response.text}"
            )
        return response.json().get("data", [])

    @staticmethod
    def _format_alert(
        event: dict,
        provider_instance: typing.Optional["SquadcastProvider"] = None,
    ) -> AlertDto:
        """Format a Squadcast webhook event into a Keep AlertDto."""
        # Determine status from event
        event_type = event.get("event_type", event.get("status", "triggered"))
        status = SquadcastProvider.STATUS_MAP.get(
            event_type.replace("incident_", ""),
            AlertStatus.FIRING,
        )

        # Determine severity from priority
        priority = event.get("priority", event.get("event", {}).get("priority", ""))
        severity = SquadcastProvider.SEVERITIES_MAP.get(priority, AlertSeverity.INFO)

        # Extract service info
        service = event.get("service", {})
        service_name = service.get("name", "") if isinstance(service, dict) else str(service)

        # Build tags
        tags = event.get("tags", {})
        if isinstance(tags, list):
            tags_dict = {}
            for tag in tags:
                if isinstance(tag, dict):
                    key = tag.get("key", tag.get("label", ""))
                    value = tag.get("value", "")
                    if key:
                        tags_dict[key] = value
            tags = tags_dict

        alert = AlertDto(
            id=event.get("id", event.get("incident_id", "")),
            name=event.get("message", event.get("title", "Squadcast Incident")),
            status=status,
            severity=severity,
            description=event.get("description", ""),
            source=["squadcast"],
            url=event.get("url", event.get("incident_url", "")),
            service=service_name,
            tags=tags if tags else {},
            lastReceived=event.get("created_at", event.get("timestamp", "")),
        )
        return alert

    @classmethod
    def webhook_example(cls) -> dict:
        return {
            "id": "60c6b0a4e4b0a2001c9a1234",
            "event_type": "incident_triggered",
            "message": "High CPU usage on prod-web-01",
            "description": "CPU has been above 95% for 5 minutes",
            "priority": "P2",
            "status": "triggered",
            "service": {
                "id": "svc123",
                "name": "Production Web",
            },
            "tags": [
                {"key": "environment", "value": "production"},
                {"key": "host", "value": "prod-web-01"},
            ],
            "created_at": "2023-10-01T12:00:00Z",
            "url": "https://app.squadcast.com/incident/60c6b0a4e4b0a2001c9a1234",
        }


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    config = ProviderConfig(
        description="Squadcast Provider Test",
        authentication={
            "api_key": "test-refresh-token",
        },
    )

    provider = SquadcastProvider(context_manager, "squadcast-test", config)
    print("Provider created successfully")
