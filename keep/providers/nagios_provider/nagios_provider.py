"""
Nagios Provider is a class that allows receiving alerts from Nagios (Core and XI)
via webhooks and pulling alerts from Nagios XI via its REST API.
"""

import dataclasses
import hashlib

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    Authentication configuration for the Nagios provider.

    Requires a Nagios XI base URL and an API key for pull-mode access.
    For webhook-only (push) mode, authentication is optional.
    """

    nagios_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI Base URL",
            "hint": "e.g. https://nagios.example.com",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI API Key",
            "sensitive": True,
        }
    )

    verify: bool = dataclasses.field(
        metadata={
            "required": False,
            "description": "Verify SSL certificates",
            "sensitive": False,
        },
        default=True,
    )


class NagiosProvider(BaseProvider):
    """
    Get alerts from Nagios (Core and XI) into Keep.

    Supports:
    - Webhook (push) mode: receives alerts via Nagios notification commands
    - Pull mode: fetches non-OK service and host states from Nagios XI API
    """

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send alerts from Nagios to Keep, configure a notification command:

1. Add the following command definition to your Nagios configuration:

```
define command {{
    command_name    notify_keep
    command_line    /usr/bin/curl -s -X POST \\
        -H "Content-Type: application/json" \\
        -H "X-API-KEY: your_keep_api_key" \\
        -d '{{ \\
            "host_name": "$HOSTNAME$", \\
            "service_description": "$SERVICEDESC$", \\
            "service_state": "$SERVICESTATE$", \\
            "host_state": "$HOSTSTATE$", \\
            "output": "$SERVICEOUTPUT$", \\
            "timestamp": "$LONGDATETIME$", \\
            "notification_type": "$NOTIFICATIONTYPE$" \\
        }}' \\
        {keep_webhook_api_url}
}}
```

2. Assign this command to your contact's `service_notification_commands` and
   `host_notification_commands`.

3. For host-only notifications, use `$HOSTOUTPUT$` instead of `$SERVICEOUTPUT$`.
    """

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["id"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated to the Nagios XI API",
        ),
    ]

    # --- Webhook (push) mode severity/status maps (string-keyed) ---

    SEVERITY_MAP = {
        "OK": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
        "UP": AlertSeverity.INFO,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.HIGH,
    }

    STATUS_MAP = {
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
    }

    NOTIFICATION_TYPE_TO_STATUS = {
        "PROBLEM": AlertStatus.FIRING,
        "RECOVERY": AlertStatus.RESOLVED,
        "ACKNOWLEDGEMENT": AlertStatus.ACKNOWLEDGED,
        "FLAPPINGSTART": AlertStatus.FIRING,
        "FLAPPINGSTOP": AlertStatus.RESOLVED,
        "DOWNTIMESTART": AlertStatus.SUPPRESSED,
        "DOWNTIMEEND": AlertStatus.RESOLVED,
    }

    # --- Pull mode severity/status maps (numeric-keyed) ---

    SERVICE_STATE_TO_SEVERITY = {
        0: AlertSeverity.INFO,
        1: AlertSeverity.WARNING,
        2: AlertSeverity.CRITICAL,
        3: AlertSeverity.INFO,
    }

    SERVICE_STATE_TO_STATUS = {
        0: AlertStatus.RESOLVED,
        1: AlertStatus.FIRING,
        2: AlertStatus.FIRING,
        3: AlertStatus.FIRING,
    }

    HOST_STATE_TO_SEVERITY = {
        0: AlertSeverity.INFO,
        1: AlertSeverity.CRITICAL,
        2: AlertSeverity.HIGH,
    }

    HOST_STATE_TO_STATUS = {
        0: AlertStatus.RESOLVED,
        1: AlertStatus.FIRING,
        2: AlertStatus.FIRING,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for the Nagios provider.
        """
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate provider scopes by testing Nagios XI API connectivity.
        """
        self.logger.info("Validating Nagios XI API connectivity")
        try:
            url = (
                f"{self.authentication_config.nagios_url}"
                f"/nagiosxi/api/v1/system/status"
                f"?apikey={self.authentication_config.api_key}"
            )
            response = requests.get(
                url=url,
                verify=self.authentication_config.verify,
            )
            if response.status_code != 200:
                response.raise_for_status()

            self.logger.info("Nagios XI API connectivity validated successfully")
            return {"authenticated": True}

        except Exception as e:
            self.logger.exception(
                "Failed to validate Nagios XI API connectivity",
                extra={"error": str(e)},
            )
            return {"authenticated": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull non-OK service and host statuses from the Nagios XI API.
        """
        self.logger.info("Pulling alerts from Nagios XI")
        alerts = []

        base_url = str(self.authentication_config.nagios_url).rstrip("/")
        api_key = self.authentication_config.api_key
        verify = self.authentication_config.verify

        # Fetch non-OK services (WARNING=1, CRITICAL=2, UNKNOWN=3)
        try:
            service_url = (
                f"{base_url}/nagiosxi/api/v1/objects/servicestatus"
                f"?apikey={api_key}&current_state=in:1,2,3"
            )
            response = requests.get(url=service_url, verify=verify)
            response.raise_for_status()
            data = response.json()
            service_records = data.get("servicestatus", [])

            # Nagios XI returns a dict instead of a list when recordcount == 1
            if isinstance(service_records, dict):
                service_records = [service_records]

            for svc in service_records:
                current_state = int(svc.get("current_state", 3))
                host_name = svc.get("host_name", "unknown")
                service_desc = svc.get("name", svc.get("service_description", "unknown"))
                alert_id = hashlib.sha256(
                    f"{host_name}:{service_desc}".encode()
                ).hexdigest()[:16]

                alerts.append(
                    AlertDto(
                        id=alert_id,
                        name=f"{service_desc} on {host_name}",
                        status=self.SERVICE_STATE_TO_STATUS.get(
                            current_state, AlertStatus.FIRING
                        ),
                        severity=self.SERVICE_STATE_TO_SEVERITY.get(
                            current_state, AlertSeverity.INFO
                        ),
                        description=svc.get("status_text", ""),
                        hostname=host_name,
                        service=service_desc,
                        source=["nagios"],
                        lastReceived=svc.get("last_check"),
                        current_state=current_state,
                    )
                )

        except Exception as e:
            self.logger.exception(
                "Failed to fetch service statuses from Nagios XI",
                extra={"error": str(e)},
            )

        # Fetch non-UP hosts (DOWN=1, UNREACHABLE=2)
        try:
            host_url = (
                f"{base_url}/nagiosxi/api/v1/objects/hoststatus"
                f"?apikey={api_key}&current_state=in:1,2"
            )
            response = requests.get(url=host_url, verify=verify)
            response.raise_for_status()
            data = response.json()
            host_records = data.get("hoststatus", [])

            # Nagios XI returns a dict instead of a list when recordcount == 1
            if isinstance(host_records, dict):
                host_records = [host_records]

            for host in host_records:
                current_state = int(host.get("current_state", 1))
                host_name = host.get("host_name", host.get("name", "unknown"))
                alert_id = hashlib.sha256(
                    f"{host_name}:HOST".encode()
                ).hexdigest()[:16]

                alerts.append(
                    AlertDto(
                        id=alert_id,
                        name=f"Host {host_name}",
                        status=self.HOST_STATE_TO_STATUS.get(
                            current_state, AlertStatus.FIRING
                        ),
                        severity=self.HOST_STATE_TO_SEVERITY.get(
                            current_state, AlertSeverity.CRITICAL
                        ),
                        description=host.get("status_text", ""),
                        hostname=host_name,
                        source=["nagios"],
                        lastReceived=host.get("last_check"),
                        current_state=current_state,
                    )
                )

        except Exception as e:
            self.logger.exception(
                "Failed to fetch host statuses from Nagios XI",
                extra={"error": str(e)},
            )

        self.logger.info(
            "Finished pulling alerts from Nagios XI",
            extra={"alert_count": len(alerts)},
        )
        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format a Nagios webhook payload into a Keep AlertDto.

        Handles both service notifications (contain service_description /
        service_state) and host notifications (contain host_state).
        """
        host_name = event.get("host_name", "unknown")
        notification_type = event.get("notification_type", "")
        output = event.get("output", "")
        timestamp = event.get("timestamp")

        # Determine if this is a service or host notification
        service_description = event.get("service_description")
        service_state = event.get("service_state")
        host_state = event.get("host_state")

        is_service = service_description is not None and service_state is not None

        if is_service:
            state = service_state
            name = f"{service_description} on {host_name}"
            fingerprint_source = f"{host_name}:{service_description}"
        else:
            state = host_state if host_state else "DOWN"
            name = f"Host {host_name}"
            fingerprint_source = f"{host_name}:HOST"

        alert_id = hashlib.sha256(fingerprint_source.encode()).hexdigest()[:16]

        # Map severity from state string
        severity = NagiosProvider.SEVERITY_MAP.get(state, AlertSeverity.INFO)

        # Map status: prefer notification_type, fall back to state-based mapping
        status = NagiosProvider.NOTIFICATION_TYPE_TO_STATUS.get(
            notification_type,
            NagiosProvider.STATUS_MAP.get(state, AlertStatus.FIRING),
        )

        service_value = service_description if is_service else None

        alert = AlertDto(
            id=alert_id,
            name=name,
            status=status,
            severity=severity,
            description=output,
            hostname=host_name,
            service=service_value,
            source=["nagios"],
            lastReceived=timestamp,
            notification_type=notification_type,
            state=state,
        )

        return alert


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    nagios_url = os.getenv("NAGIOS_URL", "https://nagios.example.com")
    api_key = os.getenv("NAGIOS_API_KEY", "")

    config = ProviderConfig(
        description="Nagios Provider",
        authentication={
            "nagios_url": nagios_url,
            "api_key": api_key,
        },
    )

    provider = NagiosProvider(context_manager, "nagios", config)
