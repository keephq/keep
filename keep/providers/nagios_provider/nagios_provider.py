"""
Nagios Provider - receive and pull alerts from Nagios XI.
"""

import dataclasses
from datetime import datetime, timezone

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    Nagios XI authentication config.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI Host URL",
            "hint": "e.g. https://nagios.example.com",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI API Key",
            "hint": "Found in Admin > System Config > API Keys",
            "sensitive": True,
        }
    )


class NagiosProvider(BaseProvider):
    """
    Pull and receive alerts from Nagios XI.
    """

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_ICON = "nagios-icon.png"
    WEBHOOK_INSTALLATION_REQUIRED = True

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send alerts from Nagios to Keep, set up a webhook notification command:

1. Create a new command in Nagios that posts JSON to {keep_webhook_api_url}
2. Include the header `X-API-KEY` with your Keep API key
3. Attach the command to the relevant contact or notification rule
4. See [Keep docs](https://docs.keephq.dev/providers/documentation/nagios-provider) for details
    """

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read alerts from Nagios XI",
        ),
    ]

    # Nagios service states: 0=OK, 1=WARNING, 2=CRITICAL, 3=UNKNOWN
    # Nagios host states:    0=UP, 1=DOWN, 2=UNREACHABLE
    STATUS_MAP = {
        0: AlertStatus.RESOLVED,
        1: AlertStatus.FIRING,
        2: AlertStatus.FIRING,
        3: AlertStatus.FIRING,
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
    }

    SEVERITY_MAP = {
        0: AlertSeverity.INFO,
        1: AlertSeverity.WARNING,
        2: AlertSeverity.CRITICAL,
        3: AlertSeverity.INFO,
        "OK": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
        "UP": AlertSeverity.INFO,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.HIGH,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        self.logger.info("Validating Nagios provider scopes")
        try:
            response = requests.get(
                url=f"{self.authentication_config.host_url}/nagiosxi/api/v1/system/status",
                params={"apikey": self.authentication_config.api_key},
                verify=True,
                timeout=10,
            )

            if response.status_code == 200:
                self.logger.info("Nagios scope validation successful")
                return {"read_alerts": True}

            return {"read_alerts": f"HTTP {response.status_code}: {response.text[:200]}"}

        except Exception as e:
            self.logger.exception("Failed to validate Nagios scopes")
            return {"read_alerts": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull current service and host problems from Nagios XI.
        """
        self.logger.info("Pulling alerts from Nagios XI")
        alerts = []

        try:
            # Fetch service problems
            svc_resp = requests.get(
                url=f"{self.authentication_config.host_url}/nagiosxi/api/v1/objects/servicestatus",
                params={"apikey": self.authentication_config.api_key},
                verify=True,
                timeout=30,
            )
            svc_resp.raise_for_status()
            services = svc_resp.json().get("servicestatus", {}).get("servicestatus", [])
            if isinstance(services, dict):
                services = [services]

            for svc in services:
                state = int(svc.get("current_state", 0))
                last_check_ts = svc.get("last_check")
                timestamp = (
                    datetime.fromtimestamp(int(last_check_ts), tz=timezone.utc).isoformat()
                    if last_check_ts
                    else None
                )

                alerts.append(
                    AlertDto(
                        id=f"{svc.get('host_name')}/{svc.get('name')}",
                        name=svc.get("name"),
                        status=self.STATUS_MAP.get(state, AlertStatus.FIRING),
                        severity=self.SEVERITY_MAP.get(state, AlertSeverity.INFO),
                        description=svc.get("status_text", ""),
                        hostname=svc.get("host_name"),
                        service_name=svc.get("name"),
                        timestamp=timestamp,
                        source=["nagios"],
                    )
                )

            # Fetch host problems
            host_resp = requests.get(
                url=f"{self.authentication_config.host_url}/nagiosxi/api/v1/objects/hoststatus",
                params={"apikey": self.authentication_config.api_key},
                verify=True,
                timeout=30,
            )
            host_resp.raise_for_status()
            hosts = host_resp.json().get("hoststatus", {}).get("hoststatus", [])
            if isinstance(hosts, dict):
                hosts = [hosts]

            for host in hosts:
                state = int(host.get("current_state", 0))
                last_check_ts = host.get("last_check")
                timestamp = (
                    datetime.fromtimestamp(int(last_check_ts), tz=timezone.utc).isoformat()
                    if last_check_ts
                    else None
                )

                alerts.append(
                    AlertDto(
                        id=host.get("name"),
                        name=host.get("name"),
                        status=self.STATUS_MAP.get(state, AlertStatus.FIRING),
                        severity=self.SEVERITY_MAP.get(state, AlertSeverity.INFO),
                        description=host.get("status_text", ""),
                        hostname=host.get("name"),
                        timestamp=timestamp,
                        source=["nagios"],
                    )
                )

        except Exception as e:
            self.logger.exception("Failed to pull alerts from Nagios XI")
            raise Exception(f"Error pulling alerts from Nagios: {e}")

        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format an incoming Nagios webhook payload into a Keep AlertDto.
        """
        # Nagios webhook payloads vary by config, but common fields:
        host_name = event.get("host_name") or event.get("hostname", "")
        service_desc = event.get("service_description") or event.get("service_desc", "")
        state_str = event.get("state", event.get("service_state", event.get("host_state", "UNKNOWN")))
        output = event.get("output") or event.get("plugin_output", "")
        timestamp_raw = event.get("timestamp") or event.get("long_date_time")

        # Try to resolve numeric state
        try:
            state_key = int(state_str)
        except (ValueError, TypeError):
            state_key = str(state_str).upper()

        alert_name = service_desc if service_desc else host_name
        alert_id = f"{host_name}/{service_desc}" if service_desc else host_name

        return AlertDto(
            id=alert_id,
            name=alert_name,
            status=NagiosProvider.STATUS_MAP.get(state_key, AlertStatus.FIRING),
            severity=NagiosProvider.SEVERITY_MAP.get(state_key, AlertSeverity.INFO),
            description=output,
            hostname=host_name,
            service_name=service_desc or None,
            timestamp=timestamp_raw,
            source=["nagios"],
            state=str(state_str),
            notification_type=event.get("notification_type"),
            attempt=event.get("attempt") or event.get("service_attempt"),
            acknowledgement=event.get("acknowledgement"),
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    config = ProviderConfig(
        description="Nagios Provider",
        authentication={
            "host_url": os.environ.get("NAGIOS_HOST_URL", "https://nagios.example.com"),
            "api_key": os.environ.get("NAGIOS_API_KEY", ""),
        },
    )

    provider = NagiosProvider(context_manager, "nagios-test", config)
    alerts = provider.get_alerts()
    print(f"Got {len(alerts)} alerts")
