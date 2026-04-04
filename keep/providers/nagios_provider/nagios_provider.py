"""
NagiosProvider is a provider that integrates Keep with Nagios monitoring system.
Supports pulling host/service alerts via Nagios REST API and receiving passive checks.
"""

import dataclasses
import logging
from datetime import datetime

import pydantic
import requests
from requests.auth import HTTPBasicAuth

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    Nagios provider authentication configuration.
    Uses Nagios XI REST API or Nagios Core via NagiosQL / livestatus.
    Reference: https://www.nagios.org/ncpa/
    """

    nagios_base_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios host base URL (e.g. https://nagios.example.com/nagiosxi)",
            "hint": "For Nagios XI: https://<host>/nagiosxi, for NCPA: https://<host>:5693",
        }
    )
    api_key: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "Nagios XI API Key (preferred auth method for XI)",
            "sensitive": True,
        },
    )
    username: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "Nagios username (used if API key is not provided)",
        },
    )
    password: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "Nagios password",
            "sensitive": True,
        },
    )
    verify_ssl: bool = dataclasses.field(
        default=True,
        metadata={
            "required": False,
            "description": "Verify SSL certificates (set to false for self-signed certs)",
        },
    )


class NagiosProvider(BaseProvider):
    """Get host/service alerts from Nagios XI or Nagios Core into Keep."""

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="api:read",
            description="Required to read host/service status from Nagios",
            mandatory=True,
            mandatory_for_webhook=False,
            documentation_url="https://www.nagios.org/documentation/",
            alias="Nagios API Access",
        ),
    ]

    # Nagios XI state codes → Keep status
    # 0=OK, 1=Warning, 2=Critical, 3=Unknown
    SERVICE_STATUS_MAP = {
        0: AlertStatus.RESOLVED,
        1: AlertStatus.FIRING,
        2: AlertStatus.FIRING,
        3: AlertStatus.FIRING,
    }

    SERVICE_SEVERITY_MAP = {
        0: AlertSeverity.INFO,
        1: AlertSeverity.WARNING,
        2: AlertSeverity.CRITICAL,
        3: AlertSeverity.HIGH,
    }

    # Host states: 0=UP, 1=DOWN, 2=UNREACHABLE
    HOST_STATUS_MAP = {
        0: AlertStatus.RESOLVED,
        1: AlertStatus.FIRING,
        2: AlertStatus.FIRING,
    }

    HOST_SEVERITY_MAP = {
        0: AlertSeverity.INFO,
        1: AlertSeverity.CRITICAL,
        2: AlertSeverity.HIGH,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """Validates required configuration for Nagios provider."""
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make an authenticated request to the Nagios XI API."""
        base = self.authentication_config.nagios_base_url.rstrip("/")
        url = f"{base}{endpoint}"

        req_params = params or {}

        # API key takes priority over basic auth
        if self.authentication_config.api_key:
            req_params["apikey"] = self.authentication_config.api_key
            auth = None
        elif self.authentication_config.username:
            auth = HTTPBasicAuth(
                self.authentication_config.username,
                self.authentication_config.password,
            )
        else:
            auth = None

        response = requests.get(
            url,
            params=req_params,
            auth=auth,
            verify=self.authentication_config.verify_ssl,
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {scope.name: "Invalid" for scope in self.PROVIDER_SCOPES}
        try:
            # Try fetching host status list as a connectivity check
            self._make_request("/api/v1/objects/hoststatus", {"count": 1})
            scopes["api:read"] = True
        except Exception as e:
            scopes["api:read"] = str(e)
        return scopes

    def get_alerts(self) -> list[AlertDto]:
        """Fetch all non-OK host and service alerts from Nagios XI."""
        alerts = []

        # Fetch host problems (DOWN/UNREACHABLE)
        try:
            host_data = self._make_request(
                "/api/v1/objects/hoststatus",
                {"current_state_ne": 0},  # not OK
            )
            for host in host_data.get("hoststatus", []):
                alerts.append(self._format_host_alert(host))
        except Exception:
            self.logger.exception("Failed to fetch host alerts from Nagios")

        # Fetch service problems (WARNING/CRITICAL/UNKNOWN)
        try:
            svc_data = self._make_request(
                "/api/v1/objects/servicestatus",
                {"current_state_ne": 0},  # not OK
            )
            for svc in svc_data.get("servicestatus", []):
                alerts.append(self._format_service_alert(svc))
        except Exception:
            self.logger.exception("Failed to fetch service alerts from Nagios")

        return alerts

    @staticmethod
    def _parse_nagios_time(ts: str) -> str | None:
        """Convert Nagios timestamp string to ISO format."""
        if not ts or ts in ("0000-00-00 00:00:00", "1970-01-01 00:00:00"):
            return None
        try:
            return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").isoformat()
        except Exception:
            return ts

    def _format_host_alert(self, host: dict) -> AlertDto:
        state = int(host.get("current_state", 1))
        return AlertDto(
            id=f"host-{host.get('host_name', 'unknown')}",
            name=f"Host {host.get('host_name', 'Unknown')} is {host.get('status_text', 'DOWN')}",
            status=self.HOST_STATUS_MAP.get(state, AlertStatus.FIRING),
            severity=self.HOST_SEVERITY_MAP.get(state, AlertSeverity.HIGH),
            description=host.get("plugin_output", ""),
            source=["nagios"],
            lastReceived=self._parse_nagios_time(host.get("last_state_change")),
            host=host.get("host_name"),
            acknowledged=host.get("problem_has_been_acknowledged", False),
            downtime=host.get("scheduled_downtime_depth", 0) > 0,
            payload=host,
        )

    def _format_service_alert(self, svc: dict) -> AlertDto:
        state = int(svc.get("current_state", 2))
        return AlertDto(
            id=f"svc-{svc.get('host_name', 'unknown')}-{svc.get('service_description', 'unknown')}",
            name=f"{svc.get('service_description', 'Service')} on {svc.get('host_name', 'unknown')}",
            status=self.SERVICE_STATUS_MAP.get(state, AlertStatus.FIRING),
            severity=self.SERVICE_SEVERITY_MAP.get(state, AlertSeverity.CRITICAL),
            description=svc.get("plugin_output", ""),
            source=["nagios"],
            lastReceived=self._parse_nagios_time(svc.get("last_state_change")),
            host=svc.get("host_name"),
            service=svc.get("service_description"),
            acknowledged=svc.get("problem_has_been_acknowledged", False),
            downtime=svc.get("scheduled_downtime_depth", 0) > 0,
            payload=svc,
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "NagiosProvider" = None
    ) -> AlertDto:
        """
        Format a Nagios passive check / webhook payload into Keep AlertDto.
        Nagios can post check results via EventBroker or custom scripts.
        """
        logger = logging.getLogger(__name__)
        logger.info("Formatting Nagios alert event")

        # Determine if host or service check
        service = event.get("service_description") or event.get("servicedisplayname")
        host = event.get("host_name") or event.get("hostname", "unknown")
        state_raw = int(event.get("current_state", event.get("state", 2)))

        if service:
            status = NagiosProvider.SERVICE_STATUS_MAP.get(state_raw, AlertStatus.FIRING)
            severity = NagiosProvider.SERVICE_SEVERITY_MAP.get(state_raw, AlertSeverity.CRITICAL)
            name = f"{service} on {host}"
            alert_id = f"svc-{host}-{service}"
        else:
            status = NagiosProvider.HOST_STATUS_MAP.get(state_raw, AlertStatus.FIRING)
            severity = NagiosProvider.HOST_SEVERITY_MAP.get(state_raw, AlertSeverity.HIGH)
            name = f"Host {host}"
            alert_id = f"host-{host}"

        last_check = event.get("last_check") or event.get("lastchecktime")
        last_received = None
        if last_check:
            try:
                last_received = datetime.strptime(last_check, "%Y-%m-%d %H:%M:%S").isoformat()
            except Exception:
                last_received = str(last_check)

        return AlertDto(
            id=str(event.get("id", alert_id)),
            name=name,
            status=status,
            severity=severity,
            description=event.get("plugin_output") or event.get("output", ""),
            lastReceived=last_received,
            source=["nagios"],
            host=host,
            service=service,
            acknowledged=event.get("problem_has_been_acknowledged", False),
            payload=event,
        )


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(tenant_id="keeptest", workflow_id="test")
    config = ProviderConfig(
        authentication={
            "nagios_base_url": os.environ.get("NAGIOS_BASE_URL", "https://nagios.example.com/nagiosxi"),
            "api_key": os.environ.get("NAGIOS_API_KEY", ""),
            "username": os.environ.get("NAGIOS_USERNAME", "nagiosadmin"),
            "password": os.environ.get("NAGIOS_PASSWORD", ""),
            "verify_ssl": False,
        }
    )
    provider = NagiosProvider(context_manager, "nagios-test", config)
    alerts = provider.get_alerts()
    print(f"Found {len(alerts)} alerts")
    for a in alerts:
        print(a)
