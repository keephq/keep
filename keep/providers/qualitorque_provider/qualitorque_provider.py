"""
QualiTorque (Torque) provider for Keep.

QualiTorque is a cloud infrastructure automation platform that orchestrates
environment deployments. This provider receives webhook notifications from
Torque for environment lifecycle events (launch, deploy, teardown, drift,
errors, etc.) and optionally pulls environment/notification data via the
Torque REST API.

Docs: https://docs.qtorque.io/admin-guide/notifications
API:  https://docs.qtorque.io/api-reference/
"""

import dataclasses
import typing

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class QualitorqueProviderAuthConfig:
    """
    QualiTorque authentication configuration.
    """

    torque_host: str = dataclasses.field(
        default="https://portal.qtorque.io",
        metadata={
            "required": False,
            "description": "Torque API host URL",
            "hint": "https://portal.qtorque.io (default) or your self-hosted URL",
        },
    )

    torque_space: str = dataclasses.field(
        default="",
        metadata={
            "required": True,
            "description": "Torque Space name",
            "hint": "The Torque space to monitor",
        },
    )

    torque_token: str = dataclasses.field(
        default="",
        metadata={
            "required": True,
            "description": "Torque API token",
            "hint": "Long-lived API token generated in Torque",
            "sensitive": True,
        },
    )


class QualitorqueProvider(BaseProvider):
    """Receive environment lifecycle notifications from QualiTorque."""

    PROVIDER_DISPLAY_NAME = "QualiTorque"
    PROVIDER_CATEGORY = ["Cloud Infrastructure", "Orchestration"]
    PROVIDER_TAGS = ["alert"]
    FINGERPRINT_FIELDS = ["id"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated to the Torque API",
            mandatory=False,
            alias="Authenticated",
        ),
    ]

    # QualiTorque environment status → Keep severity
    SEVERITIES_MAP = {
        # Error / failure states
        "error": AlertSeverity.CRITICAL,
        "failed": AlertSeverity.CRITICAL,
        "force_ended": AlertSeverity.HIGH,
        "ending_failed": AlertSeverity.HIGH,
        "drift_detected": AlertSeverity.WARNING,
        # Transitional states
        "launching": AlertSeverity.INFO,
        "deploying": AlertSeverity.INFO,
        "ending": AlertSeverity.INFO,
        "terminating": AlertSeverity.INFO,
        # Active / healthy states
        "active": AlertSeverity.INFO,
        "active_with_error": AlertSeverity.WARNING,
        "ended": AlertSeverity.INFO,
    }

    # QualiTorque environment status → Keep alert status
    STATUS_MAP = {
        # Firing (needs attention)
        "error": AlertStatus.FIRING,
        "failed": AlertStatus.FIRING,
        "ending_failed": AlertStatus.FIRING,
        "force_ended": AlertStatus.FIRING,
        "drift_detected": AlertStatus.FIRING,
        "active_with_error": AlertStatus.FIRING,
        # Acknowledged / transitional
        "launching": AlertStatus.ACKNOWLEDGED,
        "deploying": AlertStatus.ACKNOWLEDGED,
        "ending": AlertStatus.ACKNOWLEDGED,
        "terminating": AlertStatus.ACKNOWLEDGED,
        # Resolved
        "active": AlertStatus.RESOLVED,
        "ended": AlertStatus.RESOLVED,
    }

    webhook_description = "Receive environment lifecycle notifications from QualiTorque"
    webhook_markdown = """
To configure QualiTorque to send notifications to Keep:

1. Log in to your QualiTorque portal.
2. Navigate to **Administration > Notifications**.
3. Click **Add Notification Target** and choose **Webhook**.
4. Set the Webhook URL to: `{keep_webhook_api_url}`
5. Add a custom header: `X-API-KEY` with value `{api_key}`.
6. Select the event types you want to receive (e.g., Environment Launched, Environment Error, Drift Detected).
7. Save the notification target.

QualiTorque will now send environment lifecycle events to Keep.
"""

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = QualitorqueProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate connectivity to the Torque API."""
        try:
            host = str(self.authentication_config.torque_host).rstrip("/")
            space = self.authentication_config.torque_space
            token = self.authentication_config.torque_token

            # Try listing environments to verify credentials
            response = requests.get(
                f"{host}/api/spaces/{space}/environments",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                timeout=10,
            )

            if response.status_code == 200:
                return {"authenticated": True}
            elif response.status_code in (401, 403):
                return {
                    "authenticated": f"Authentication failed ({response.status_code})"
                }
            else:
                return {
                    "authenticated": (
                        f"Unexpected response from Torque API: {response.status_code}"
                    )
                }
        except requests.exceptions.ConnectionError:
            return {"authenticated": "Could not connect to Torque API"}
        except Exception as e:
            return {"authenticated": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        """Pull environment data from the Torque API and return alerts for
        environments in error/warning states."""
        host = str(self.authentication_config.torque_host).rstrip("/")
        space = self.authentication_config.torque_space
        token = self.authentication_config.torque_token

        response = requests.get(
            f"{host}/api/spaces/{space}/environments",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            timeout=30,
        )

        if not response.ok:
            self.logger.error(
                "Failed to fetch environments from Torque",
                extra={"status_code": response.status_code},
            )
            raise Exception(
                f"Failed to fetch Torque environments: {response.status_code}"
            )

        environments = response.json()
        alerts: list[AlertDto] = []

        for env in environments:
            status = (env.get("computed_status") or env.get("status", "")).lower()
            # Only report environments in problematic states
            if status in (
                "error",
                "failed",
                "ending_failed",
                "force_ended",
                "drift_detected",
                "active_with_error",
            ):
                alerts.append(
                    AlertDto(
                        id=env.get("id", ""),
                        name=env.get("definition_name", env.get("name", "")),
                        description=(
                            f"Environment '{env.get('name', '')}' is in "
                            f"'{status}' state"
                        ),
                        status=self.STATUS_MAP.get(status, AlertStatus.FIRING),
                        severity=self.SEVERITIES_MAP.get(
                            status, AlertSeverity.WARNING
                        ),
                        environment=env.get("name", ""),
                        owner=env.get("owner", {}).get("email", ""),
                        source=["qualitorque"],
                        blueprint=env.get("definition_name", ""),
                        lastReceived=env.get("last_used", ""),
                    )
                )

        return alerts

    @staticmethod
    def _format_alert(
        event: dict,
        provider_instance: typing.Optional["BaseProvider"] = None,
    ) -> AlertDto | list[AlertDto]:
        """Format a QualiTorque webhook notification payload into an AlertDto.

        Torque webhooks send JSON payloads with environment lifecycle
        information.  The payload structure varies by event type but
        typically includes:
          - event_type / notification_type: e.g. "EnvironmentError"
          - environment_id / id
          - environment_name / name
          - status / computed_status
          - owner / initiated_by
          - blueprint / definition_name
          - message / details / error_message
        """
        # Torque webhook payloads can use varying key names
        event_type = (
            event.get("event_type")
            or event.get("notification_type")
            or event.get("type")
            or "unknown"
        )
        env_name = (
            event.get("environment_name")
            or event.get("name")
            or event.get("sandbox_name")
            or ""
        )
        env_id = (
            event.get("environment_id")
            or event.get("id")
            or event.get("sandbox_id")
            or ""
        )
        status_raw = (
            event.get("computed_status")
            or event.get("status")
            or ""
        ).lower()
        description = (
            event.get("message")
            or event.get("details")
            or event.get("error_message")
            or event.get("description")
            or f"QualiTorque event: {event_type}"
        )
        owner = event.get("owner") or event.get("initiated_by") or ""
        if isinstance(owner, dict):
            owner = owner.get("email", str(owner))
        blueprint = (
            event.get("blueprint")
            or event.get("definition_name")
            or event.get("blueprint_name")
            or ""
        )
        space = event.get("space") or event.get("space_name") or ""

        # Map to severity and status based on event type keywords
        severity = QualitorqueProvider.SEVERITIES_MAP.get(
            status_raw, AlertSeverity.INFO
        )
        alert_status = QualitorqueProvider.STATUS_MAP.get(
            status_raw, AlertStatus.FIRING
        )

        # If status_raw is empty, infer from event_type
        event_lower = event_type.lower()
        if not status_raw:
            if "error" in event_lower or "fail" in event_lower:
                severity = AlertSeverity.CRITICAL
                alert_status = AlertStatus.FIRING
            elif "drift" in event_lower:
                severity = AlertSeverity.WARNING
                alert_status = AlertStatus.FIRING
            elif "end" in event_lower or "terminat" in event_lower:
                severity = AlertSeverity.INFO
                alert_status = AlertStatus.RESOLVED
            elif "launch" in event_lower or "deploy" in event_lower:
                severity = AlertSeverity.INFO
                alert_status = AlertStatus.ACKNOWLEDGED
            elif "active" in event_lower:
                severity = AlertSeverity.INFO
                alert_status = AlertStatus.RESOLVED

        return AlertDto(
            id=str(env_id),
            name=env_name or event_type,
            description=description,
            status=alert_status,
            severity=severity,
            environment=env_name,
            owner=owner,
            source=["qualitorque"],
            event_type=event_type,
            blueprint=blueprint,
            space=space,
            lastReceived=event.get("timestamp") or event.get("created_at") or "",
        )
