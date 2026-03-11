"""
Nagios is a monitoring tool for Infrastructure and Application Monitoring.
Supports both Nagios Core (webhook push) and Nagios XI (REST API pull + webhook push).
"""

import dataclasses
import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    Authentication configuration for Nagios XI REST API (pull-based).
    Leave these blank to use webhook-only mode (Nagios Core).
    """

    nagios_url: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Nagios XI base URL",
            "hint": "e.g. https://nagios.example.com/nagiosxi",
            "sensitive": False,
        },
    )
    api_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Nagios XI API key",
            "hint": "Found in Admin > Manage API Keys",
            "sensitive": True,
        },
    )
    verify_ssl: bool = dataclasses.field(
        default=True,
        metadata={
            "required": False,
            "description": "Verify SSL certificates",
            "hint": "Disable for self-signed certificates",
            "sensitive": False,
        },
    )


class NagiosProvider(BaseProvider):
    """Pull alerts from Nagios XI REST API and/or receive push alerts via webhook."""

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
## Configuring Nagios to Send Alerts to Keep

Nagios can push alerts to Keep via webhook using a custom notification command.
This works with both **Nagios Core** and **Nagios XI**.

### Step 1: Create Notification Commands

Add the following to your Nagios configuration (e.g. `/usr/local/nagios/etc/objects/commands.cfg`):

```
define command {{
    command_name    notify-keep-host
    command_line    /usr/bin/curl -s -X POST \\
      -H "Content-Type: application/json" \\
      -d '{{"host_name": "$HOSTNAME$", "host_alias": "$HOSTALIAS$", "host_address": "$HOSTADDRESS$", \
"state": "$HOSTSTATE$", "state_type": "$HOSTSTATETYPE$", "output": "$HOSTOUTPUT$", \
"long_output": "$LONGHOSTOUTPUT$", "notification_type": "$NOTIFICATIONTYPE$", "timestamp": "$TIMET$"}}' \\
      "{keep_webhook_api_url}?api_key={api_key}"
}}

define command {{
    command_name    notify-keep-service
    command_line    /usr/bin/curl -s -X POST \\
      -H "Content-Type: application/json" \\
      -d '{{"host_name": "$HOSTNAME$", "host_alias": "$HOSTALIAS$", "host_address": "$HOSTADDRESS$", \
"service_description": "$SERVICEDESC$", "state": "$SERVICESTATE$", "state_type": "$SERVICESTATETYPE$", \
"output": "$SERVICEOUTPUT$", "long_output": "$LONGSERVICEOUTPUT$", \
"notification_type": "$NOTIFICATIONTYPE$", "timestamp": "$TIMET$"}}' \\
      "{keep_webhook_api_url}?api_key={api_key}"
}}
```

### Step 2: Create a Keep Contact

```
define contact {{
    contact_name                    keep
    alias                           Keep Alerting
    service_notification_period     24x7
    host_notification_period        24x7
    service_notification_options    w,u,c,r
    host_notification_options       d,u,r
    service_notification_commands   notify-keep-service
    host_notification_commands      notify-keep-host
}}
```

### Step 3: Add the Contact to Your Hosts/Services

Add `contact_groups keep-notifications` to your host and service definitions.

### Step 4: Restart Nagios

```bash
sudo systemctl restart nagios
```
"""

    SEVERITIES_MAP = {
        "OK": AlertSeverity.INFO,
        "UP": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.CRITICAL,
    }

    STATUS_MAP = {
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
    }

    # Nagios XI host state codes → string
    _HOST_STATE = {0: "UP", 1: "DOWN", 2: "UNREACHABLE"}
    # Nagios XI service state codes → string
    _SERVICE_STATE = {0: "OK", 1: "WARNING", 2: "CRITICAL", 3: "UNKNOWN"}

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["host_name", "service_description"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read host and service status from Nagios XI API",
            mandatory=False,
            documentation_url="https://assets.nagios.com/downloads/nagiosxi/docs/Nagios-XI-REST-API.pdf",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate that the Nagios XI API is reachable and the API key works.
        Returns a dict of scope_name → True | error_message.
        """
        scopes = {"read_alerts": True}
        if not self._is_pull_configured():
            scopes["read_alerts"] = "nagios_url and api_key are required for pull-based integration"
            return scopes

        try:
            resp = requests.get(
                self._xi_url("objects/hoststatus"),
                params={"apikey": self.authentication_config.api_key, "count": 1},
                verify=self.authentication_config.verify_ssl,
                timeout=10,
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            scopes["read_alerts"] = str(e)

        return scopes

    # ------------------------------------------------------------------
    # Pull-based (Nagios XI REST API)
    # ------------------------------------------------------------------

    def _is_pull_configured(self) -> bool:
        cfg = self.authentication_config
        return bool(cfg.nagios_url and cfg.api_key)

    def _xi_url(self, path: str) -> str:
        base = self.authentication_config.nagios_url.rstrip("/")
        return urljoin(base + "/", f"api/v1/{path}")

    def _fetch_host_alerts(self) -> list[AlertDto]:
        resp = requests.get(
            self._xi_url("objects/hoststatus"),
            params={"apikey": self.authentication_config.api_key},
            verify=self.authentication_config.verify_ssl,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        hosts = data.get("hoststatus", data) if isinstance(data, dict) else data
        if isinstance(hosts, dict):
            hosts = hosts.get("hoststatus", [])

        alerts = []
        for host in hosts:
            state_code = host.get("current_state", 0)
            state = self._HOST_STATE.get(int(state_code), "UNKNOWN")
            # Only surface problems (non-UP) unless acknowledged
            if state == "UP":
                continue
            host_name = host.get("host_name", "unknown")
            alerts.append(
                AlertDto(
                    id=f"nagios:host:{host_name}",
                    name=f"Host {state}: {host_name}",
                    description=host.get("plugin_output", ""),
                    severity=self.SEVERITIES_MAP.get(state, AlertSeverity.INFO),
                    status=self.STATUS_MAP.get(state, AlertStatus.FIRING),
                    host=host_name,
                    service=None,
                    source=["nagios"],
                    output=host.get("plugin_output", ""),
                    long_output=host.get("long_plugin_output", ""),
                    acknowledged=bool(host.get("problem_has_been_acknowledged", 0)),
                    lastReceived=self._parse_xi_time(host.get("last_check")),
                )
            )
        return alerts

    def _fetch_service_alerts(self) -> list[AlertDto]:
        resp = requests.get(
            self._xi_url("objects/servicestatus"),
            params={"apikey": self.authentication_config.api_key},
            verify=self.authentication_config.verify_ssl,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        services = data.get("servicestatus", data) if isinstance(data, dict) else data
        if isinstance(services, dict):
            services = services.get("servicestatus", [])

        alerts = []
        for svc in services:
            state_code = svc.get("current_state", 0)
            state = self._SERVICE_STATE.get(int(state_code), "UNKNOWN")
            if state == "OK":
                continue
            host_name = svc.get("host_name", "unknown")
            service_description = svc.get("service_description", "unknown")
            alerts.append(
                AlertDto(
                    id=f"nagios:service:{host_name}:{service_description}",
                    name=f"{service_description} on {host_name}",
                    description=svc.get("plugin_output", ""),
                    severity=self.SEVERITIES_MAP.get(state, AlertSeverity.INFO),
                    status=self.STATUS_MAP.get(state, AlertStatus.FIRING),
                    host=host_name,
                    service=service_description,
                    source=["nagios"],
                    output=svc.get("plugin_output", ""),
                    long_output=svc.get("long_plugin_output", ""),
                    acknowledged=bool(svc.get("problem_has_been_acknowledged", 0)),
                    lastReceived=self._parse_xi_time(svc.get("last_check")),
                )
            )
        return alerts

    @staticmethod
    def _parse_xi_time(value) -> Optional[str]:
        """Parse Nagios XI timestamps (ISO-8601 strings or Unix epoch ints)."""
        if not value:
            return None
        try:
            # Unix epoch
            ts = int(value)
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except (ValueError, TypeError):
            pass
        try:
            # ISO-8601 string from Nagios XI
            return datetime.fromisoformat(str(value)).isoformat()
        except ValueError:
            logger.warning(f"Could not parse Nagios XI timestamp: {value!r}")
            return None

    def _get_alerts(self) -> list[AlertDto]:
        """Pull current host and service problems from the Nagios XI REST API."""
        if not self._is_pull_configured():
            logger.info(
                "Nagios XI pull not configured (nagios_url/api_key missing); "
                "operating in webhook-only mode"
            )
            return []

        alerts: list[AlertDto] = []
        try:
            alerts.extend(self._fetch_host_alerts())
        except Exception as e:
            logger.error(f"Failed to fetch Nagios host alerts: {e}")

        try:
            alerts.extend(self._fetch_service_alerts())
        except Exception as e:
            logger.error(f"Failed to fetch Nagios service alerts: {e}")

        return alerts

    # ------------------------------------------------------------------
    # Push-based (webhook from Nagios Core / Nagios XI)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a Nagios webhook payload into an AlertDto.
        Handles both host notifications and service notifications.
        """

        def _get(key):
            v = event.get(key)
            return None if (v is None or v == "") else v

        state = _get("state") or "UNKNOWN"
        host_name = _get("host_name")
        service_description = _get("service_description")

        is_host_alert = service_description is None
        name = (
            f"Host {state}: {host_name}"
            if is_host_alert
            else f"{service_description} on {host_name}"
        )

        last_received = None
        if ts := _get("timestamp"):
            try:
                last_received = datetime.fromtimestamp(
                    int(ts), tz=timezone.utc
                ).isoformat()
            except (ValueError, OSError):
                logger.warning(f"Failed to parse Nagios timestamp: {ts!r}")

        return AlertDto(
            id=(
                f"{host_name}:{service_description or 'HOST'}"
                if host_name
                else None
            ),
            name=name,
            description=_get("output"),
            severity=NagiosProvider.SEVERITIES_MAP.get(state, AlertSeverity.INFO),
            status=NagiosProvider.STATUS_MAP.get(state, AlertStatus.FIRING),
            host=host_name,
            service=service_description,
            source=["nagios"],
            output=_get("output"),
            long_output=_get("long_output"),
            notification_type=_get("notification_type"),
            lastReceived=last_received,
            alias=_get("host_alias"),
            address=_get("host_address"),
            state_type=_get("state_type"),
        )


if __name__ == "__main__":
    pass
