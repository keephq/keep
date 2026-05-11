"""
Nagios Provider is a class that provides a way to receive alerts from Nagios via webhooks.
"""

import dataclasses
import datetime
import logging

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    Nagios authentication configuration.
    All fields are optional for webhook-only usage.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": False,
            "description": "Nagios Host URL (required for API pulling)",
            "hint": "e.g. https://nagios.example.com",
            "sensitive": False,
            "validation": "any_http_url",
        },
        default=None,
    )

    api_user: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Nagios API Username (required for API pulling)",
            "sensitive": False,
        },
        default=None,
    )

    api_password: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Nagios API Password or API Key (required for API pulling)",
            "sensitive": True,
        },
        default=None,
    )


class NagiosProvider(BaseProvider):
    """
    Get alerts from Nagios into Keep via webhooks or API polling.

    Nagios sends alerts through notification commands. To configure webhooks:
    1. Create a notification command that POSTs JSON to Keep's webhook URL
    2. Add X-API-KEY header with your Keep API key
    3. Assign the command to host/service notification rules
    """

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(name="read_alerts", description="Read alerts from Nagios"),
    ]

    webhook_description = "Nagios webhook alerts"
    webhook_template = ""
    webhook_markdown = """
To send alerts from Nagios to Keep, configure a notification command:

1. In Nagios, create a new notification command (e.g., `notify-host-by-keep`, `notify-service-by-keep`)
2. Set the webhook URL as: {keep_webhook_api_url}
3. Add header "X-API-KEY" with your Keep API key (webhook role)
4. Configure host/service notification rules to use this command
5. For detailed setup instructions, see [Keep documentation](https://docs.keephq.dev/providers/documentation/nagios-provider)
    """

    # Nagios state mapping to Keep alert status
    STATUS_MAP = {
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
    }

    # Nagios state mapping to Keep alert severity
    SEVERITY_MAP = {
        "OK": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
        "UP": AlertSeverity.INFO,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.WARNING,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose of the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Nagios provider.
        All auth fields are optional for webhook-only usage.
        """
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate provider scopes by testing API connectivity.
        If no host_url is configured, returns a note that webhook-only mode is active.
        """
        if not self.authentication_config.host_url:
            return {"read_alerts": "No host_url configured (webhook-only mode)"}

        try:
            response = requests.get(
                f"{self.authentication_config.host_url}/",
                auth=(
                    self.authentication_config.api_user or "",
                    self.authentication_config.api_password or "",
                ),
                timeout=10,
            )
            if response.status_code < 500:
                return {"read_alerts": True}
            else:
                return {"read_alerts": f"Server error: {response.status_code}"}
        except Exception as e:
            return {"read_alerts": str(e)}

    @staticmethod
    def _state_to_text(state, is_service=True):
        """Convert numeric Nagios state to text label."""
        if is_service:
            mapping = {"0": "OK", "1": "WARNING", "2": "CRITICAL", "3": "UNKNOWN"}
        else:
            mapping = {"0": "UP", "1": "DOWN", "2": "UNREACHABLE"}
        return mapping.get(str(state), "UNKNOWN")

    def _get_alerts(self) -> list[AlertDto]:
        """
        Optional: Pull alerts from Nagios XI API.
        Returns empty list if host_url is not configured.
        """
        if not self.authentication_config.host_url:
            self.logger.info("No host_url configured, skipping alert pulling")
            return []

        try:
            # Nagios XI API endpoint for service status
            url = f"{self.authentication_config.host_url}/nagiosxi/api/v1/objects/servicestatus"
            params = {"apikey": self.authentication_config.api_password or ""}
            response = requests.get(url, params=params, timeout=30)

            if not response.ok:
                self.logger.warning(
                    "Failed to pull alerts from Nagios: %s", response.status_code
                )
                return []

            data = response.json()
            service_records = (
                data.get("servicestatus", {}).get("recordlist", {}).get("record", [])
            )
            if not isinstance(service_records, list):
                service_records = [service_records] if service_records else []

            alerts = []
            for record in service_records:
                state = record.get("current_state", "UNKNOWN")
                state_text = self._state_to_text(state, is_service=True)
                alerts.append(
                    AlertDto(
                        id=record.get("service_id", record.get("name")),
                        name=record.get("name", "Unknown Service"),
                        status=self.STATUS_MAP.get(state_text, AlertStatus.FIRING),
                        severity=self.SEVERITY_MAP.get(
                            state_text, AlertSeverity.INFO
                        ),
                        lastReceived=datetime.datetime.now(
                            datetime.timezone.utc
                        ).isoformat(),
                        description=record.get("status_text", ""),
                        source=["nagios"],
                        hostname=record.get("host_name"),
                        service_name=record.get("name"),
                    )
                )

            return alerts

        except Exception as e:
            self.logger.exception("Failed to get alerts from Nagios")
            return []

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format Nagios webhook payload into Keep alert format.

        Supports both host and service notifications.
        Handles numeric and text state representations.
        """
        notification_type = event.get("notification_type", "PROBLEM")
        host_name = event.get("host_name", event.get("host", "unknown"))
        host_address = event.get("host_address", "")
        host_state = event.get("host_state", "")
        host_output = event.get("host_output", "")

        service_description = event.get(
            "service_description", event.get("service", "")
        )
        service_state = event.get("service_state", "")
        service_output = event.get("service_output", "")

        # Determine if this is a host or service alert
        is_service_alert = bool(service_description)

        if is_service_alert:
            raw_state = service_state
            output = service_output
            name = f"{host_name}/{service_description}"
            alert_id = f"{host_name}:{service_description}"
        else:
            raw_state = host_state
            output = host_output
            name = host_name
            alert_id = host_name

        # Convert numeric state to text label
        if raw_state and str(raw_state).isdigit():
            state_upper = NagiosProvider._state_to_text(raw_state, is_service_alert)
        else:
            state_upper = str(raw_state).upper() if raw_state else "UNKNOWN"

        # Handle RECOVERY / ACKNOWLEDGEMENT / FLAPPINGSTOP notifications
        if notification_type in ("RECOVERY", "ACKNOWLEDGEMENT", "FLAPPINGSTOP"):
            state_upper = "OK" if is_service_alert else "UP"
        elif notification_type in ("FLAPPINGSTART", "DOWNTIMESTART"):
            # Keep current state but ensure firing status
            pass

        status = NagiosProvider.STATUS_MAP.get(state_upper, AlertStatus.FIRING)
        severity = NagiosProvider.SEVERITY_MAP.get(state_upper, AlertSeverity.INFO)

        last_received = event.get(
            "last_check",
            event.get(
                "last_state_change",
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
            ),
        )

        return AlertDto(
            id=alert_id,
            name=name,
            status=status,
            severity=severity,
            lastReceived=last_received,
            description=output,
            source=["nagios"],
            hostname=host_name,
            host_address=host_address,
            service_name=service_description,
            notification_type=notification_type,
            state=state_upper,
            pushed=True,
        )


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")
    config = ProviderConfig(description="Nagios Provider", authentication={})
    provider = NagiosProvider(context_manager, "nagios", config)
