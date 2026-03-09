"""
Nagios Provider is a class that provides a way to receive alerts from
Nagios XI and Nagios Core via webhooks and API polling.
"""

import dataclasses
import datetime
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    Authentication configuration for Nagios XI.

    Nagios XI exposes a REST API at /nagiosxi/api/v1/ authenticated
    via an API key that can be generated in Admin → Manage API Keys.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
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
            "description": "Nagios XI API Key (Admin → Manage API Keys)",
            "sensitive": True,
        }
    )


class NagiosProvider(BaseProvider):
    """
    Get alerts from Nagios XI into Keep via API polling or webhooks.

    Supports:
    - Polling host and service problems via Nagios XI REST API
    - Receiving webhook notifications from Nagios XI/Core
    - Mapping Nagios states to Keep alert status and severity
    """

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send alerts from Nagios to Keep, configure a webhook notification command:

**Nagios XI:**

1. Go to Admin → Manage API Keys and create a key (or use an existing one)
2. Configure a new notification command that POSTs to Keep:

```bash
/usr/bin/curl -s -X POST \\
  -H "Content-Type: application/json" \\
  -H "X-API-KEY: <your-keep-api-key>" \\
  -d '{
    "host_name": "$HOSTNAME$",
    "host_alias": "$HOSTALIAS$",
    "host_address": "$HOSTADDRESS$",
    "host_state": "$HOSTSTATE$",
    "host_state_id": "$HOSTSTATEID$",
    "service_description": "$SERVICEDESC$",
    "service_state": "$SERVICESTATE$",
    "service_state_id": "$SERVICESTATEID$",
    "service_output": "$SERVICEOUTPUT$",
    "long_service_output": "$LONGSERVICEOUTPUT$",
    "notification_type": "$NOTIFICATIONTYPE$",
    "timestamp": "$TIMET$",
    "attempt": "$SERVICEATTEMPT$",
    "max_attempts": "$MAXSERVICEATTEMPTS$",
    "downtime_depth": "$SERVICEDOWNTIMEDEPTH$",
    "acknowledged": "$SERVICEACKAUTHOR$"
  }' \\
  {keep_webhook_api_url}
```

3. Assign the command to host/service notification definitions
4. For detailed setup, see [Keep documentation](https://docs.keephq.dev/providers/documentation/nagios-provider)

**Nagios Core:**

The same curl-based command works for Nagios Core. Define it as a
`command` object in your Nagios configuration and reference it in
contact notification settings.
    """

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    WEBHOOK_INSTALLATION_REQUIRED = False
    PROVIDER_ICON = "nagios-icon.png"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read host and service alerts from Nagios XI API",
        ),
    ]

    # Nagios host states: 0=UP, 1=DOWN, 2=UNREACHABLE
    # Nagios service states: 0=OK, 1=WARNING, 2=CRITICAL, 3=UNKNOWN
    STATUS_MAP = {
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
    }

    # Map numeric state IDs as well (for webhook payloads)
    STATUS_ID_MAP = {
        # Host states
        (0, "host"): AlertStatus.RESOLVED,   # UP
        (1, "host"): AlertStatus.FIRING,     # DOWN
        (2, "host"): AlertStatus.FIRING,     # UNREACHABLE
        # Service states
        (0, "service"): AlertStatus.RESOLVED,  # OK
        (1, "service"): AlertStatus.FIRING,    # WARNING
        (2, "service"): AlertStatus.FIRING,    # CRITICAL
        (3, "service"): AlertStatus.FIRING,    # UNKNOWN
    }

    SEVERITY_MAP = {
        "UP": AlertSeverity.INFO,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.HIGH,
        "OK": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """
        Validates the Nagios XI provider configuration.
        """
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def _get_api_url(self, endpoint: str) -> str:
        """Build a Nagios XI API URL with the API key."""
        base = str(self.authentication_config.host_url).rstrip("/")
        separator = "&" if "?" in endpoint else "?"
        return f"{base}/nagiosxi/api/v1/{endpoint}{separator}apikey={self.authentication_config.api_key}"

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate scopes by querying the Nagios XI system status endpoint.
        """
        self.logger.info("Validating Nagios XI provider scopes")
        try:
            response = requests.get(
                self._get_api_url("system/status"),
                verify=True,
                timeout=10,
            )

            if response.ok:
                data = response.json()
                # Nagios XI returns {"instance_id": ..., "status": {...}} on success
                if "error" in data:
                    return {"read_alerts": f"API error: {data['error']}"}
                return {"read_alerts": True}
            else:
                return {
                    "read_alerts": f"HTTP {response.status_code}: {response.text[:200]}"
                }

        except Exception as e:
            self.logger.exception("Failed to validate Nagios XI scopes")
            return {"read_alerts": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        """
        Fetch current host and service problems from Nagios XI API.

        Returns:
            list[AlertDto]: Combined host and service alerts.
        """
        alerts = []

        try:
            alerts.extend(self._get_host_alerts())
        except Exception as e:
            self.logger.error("Error fetching Nagios host alerts: %s", e)

        try:
            alerts.extend(self._get_service_alerts())
        except Exception as e:
            self.logger.error("Error fetching Nagios service alerts: %s", e)

        return alerts

    def _get_host_alerts(self) -> list[AlertDto]:
        """Fetch host problems from Nagios XI."""
        response = requests.get(
            self._get_api_url("objects/hoststatus?hoststatustypes=12"),
            verify=True,
            timeout=30,
        )

        if not response.ok:
            self.logger.error(
                "Failed to get host status from Nagios XI: %s %s",
                response.status_code,
                response.text[:200],
            )
            raise Exception(f"Nagios XI API error: {response.status_code}")

        data = response.json()
        hosts = data.get("hoststatus", [])

        alerts = []
        for host in hosts:
            state_name = self._host_state_to_name(host.get("current_state", 0))
            last_check = host.get("last_check")
            timestamp = None
            if last_check:
                try:
                    timestamp = datetime.datetime.fromisoformat(last_check).isoformat()
                except (ValueError, TypeError):
                    timestamp = last_check

            alerts.append(
                AlertDto(
                    id=f"nagios-host-{host.get('host_object_id', host.get('name', 'unknown'))}",
                    name=host.get("name", "Unknown Host"),
                    status=self.STATUS_MAP.get(state_name, AlertStatus.FIRING),
                    severity=self.SEVERITY_MAP.get(state_name, AlertSeverity.INFO),
                    description=host.get("status_text", host.get("output", "")),
                    hostname=host.get("name"),
                    address=host.get("address"),
                    lastReceived=timestamp,
                    acknowledged=host.get("problem_acknowledged", 0) == 1,
                    source=["nagios"],
                    state=state_name,
                    attempt=host.get("current_attempt"),
                    max_attempts=host.get("max_attempts"),
                )
            )

        return alerts

    def _get_service_alerts(self) -> list[AlertDto]:
        """Fetch service problems from Nagios XI."""
        response = requests.get(
            self._get_api_url("objects/servicestatus?servicestatustypes=28"),
            verify=True,
            timeout=30,
        )

        if not response.ok:
            self.logger.error(
                "Failed to get service status from Nagios XI: %s %s",
                response.status_code,
                response.text[:200],
            )
            raise Exception(f"Nagios XI API error: {response.status_code}")

        data = response.json()
        services = data.get("servicestatus", [])

        alerts = []
        for svc in services:
            state_name = self._service_state_to_name(svc.get("current_state", 0))
            last_check = svc.get("last_check")
            timestamp = None
            if last_check:
                try:
                    timestamp = datetime.datetime.fromisoformat(last_check).isoformat()
                except (ValueError, TypeError):
                    timestamp = last_check

            alerts.append(
                AlertDto(
                    id=f"nagios-svc-{svc.get('service_object_id', 'unknown')}",
                    name=f"{svc.get('host_name', 'unknown')}/{svc.get('name', svc.get('service_description', 'unknown'))}",
                    status=self.STATUS_MAP.get(state_name, AlertStatus.FIRING),
                    severity=self.SEVERITY_MAP.get(state_name, AlertSeverity.INFO),
                    description=svc.get("status_text", svc.get("output", "")),
                    hostname=svc.get("host_name"),
                    service_name=svc.get("name", svc.get("service_description")),
                    lastReceived=timestamp,
                    acknowledged=svc.get("problem_acknowledged", 0) == 1,
                    source=["nagios"],
                    state=state_name,
                    attempt=svc.get("current_attempt"),
                    max_attempts=svc.get("max_attempts"),
                    check_command=svc.get("check_command"),
                )
            )

        return alerts

    @staticmethod
    def _host_state_to_name(state: int) -> str:
        return {0: "UP", 1: "DOWN", 2: "UNREACHABLE"}.get(int(state), "UNKNOWN")

    @staticmethod
    def _service_state_to_name(state: int) -> str:
        return {0: "OK", 1: "WARNING", 2: "CRITICAL", 3: "UNKNOWN"}.get(
            int(state), "UNKNOWN"
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: Optional["BaseProvider"] = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a Nagios webhook payload into a Keep AlertDto.

        Handles both host and service notifications. Service notifications
        include ``service_description`` while host-only notifications do not.

        Args:
            event: Raw webhook JSON payload from Nagios.
            provider_instance: Optional provider instance.

        Returns:
            AlertDto: Formatted alert.
        """
        is_service = bool(event.get("service_description"))
        notification_type = event.get("notification_type", "PROBLEM")

        # Determine state name and type
        if is_service:
            state_name = event.get("service_state", "UNKNOWN")
            state_id_str = event.get("service_state_id")
            alert_name = f"{event.get('host_name', 'unknown')}/{event.get('service_description', 'unknown')}"
            output = event.get("service_output", "")
            long_output = event.get("long_service_output", "")
        else:
            state_name = event.get("host_state", "UNKNOWN")
            state_id_str = event.get("host_state_id")
            alert_name = event.get("host_name", "Unknown Host")
            output = event.get("host_output", event.get("service_output", ""))
            long_output = event.get("long_host_output", "")

        # Handle RECOVERY notification type
        if notification_type == "RECOVERY":
            status = AlertStatus.RESOLVED
            severity = AlertSeverity.INFO
        else:
            status = NagiosProvider.STATUS_MAP.get(state_name, AlertStatus.FIRING)
            severity = NagiosProvider.SEVERITY_MAP.get(state_name, AlertSeverity.INFO)

        # Parse timestamp
        timestamp = None
        ts_raw = event.get("timestamp")
        if ts_raw:
            try:
                timestamp = datetime.datetime.fromtimestamp(int(ts_raw)).isoformat()
            except (ValueError, TypeError, OSError):
                timestamp = ts_raw

        description = output
        if long_output:
            description = f"{output}\n{long_output}"

        alert = AlertDto(
            id=f"nagios-{event.get('host_name', 'unknown')}-{event.get('service_description', 'host')}",
            name=alert_name,
            status=status,
            severity=severity,
            description=description,
            hostname=event.get("host_name"),
            address=event.get("host_address"),
            host_alias=event.get("host_alias"),
            service_name=event.get("service_description") if is_service else None,
            lastReceived=timestamp,
            source=["nagios"],
            state=state_name,
            notification_type=notification_type,
            attempt=event.get("attempt"),
            max_attempts=event.get("max_attempts"),
            downtime_depth=event.get("downtime_depth"),
            acknowledged=bool(event.get("acknowledged")),
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

    host_url = os.environ.get("NAGIOS_HOST_URL")
    api_key = os.environ.get("NAGIOS_API_KEY")

    if not host_url or not api_key:
        raise Exception("Set NAGIOS_HOST_URL and NAGIOS_API_KEY environment variables")

    config = ProviderConfig(
        description="Nagios Provider",
        authentication={
            "host_url": host_url,
            "api_key": api_key,
        },
    )

    provider = NagiosProvider(context_manager, "nagios", config)
    alerts = provider._get_alerts()
    print(f"Got {len(alerts)} alerts")
    for alert in alerts[:5]:
        print(f"  {alert.name}: {alert.status} ({alert.severity})")
