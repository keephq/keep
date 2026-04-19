"""
Checkmk is a monitoring tool for Infrastructure and Application Monitoring.
"""

import dataclasses
import logging
from datetime import datetime, timezone
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.base.provider_exceptions import ProviderMethodException
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class CheckmkProviderAuthConfig:
    """
    Checkmk authentication configuration.
    """

    checkmk_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Checkmk Site URL",
            "hint": "https://checkmk.example.com/mysite",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    checkmk_username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Checkmk Username",
            "hint": "automation user for API access",
            "sensitive": False,
        }
    )
    checkmk_auth_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Checkmk Automation Secret / Auth Token",
            "hint": "Found in Checkmk user settings",
            "sensitive": True,
        }
    )
    verify_ssl: bool = dataclasses.field(
        metadata={
            "description": "Verify SSL certificates",
            "hint": "Set to false to allow self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )


class CheckmkProvider(BaseProvider):
    """Get alerts from Checkmk into Keep"""

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
  1. Checkmk supports custom notification scripts.
  2. Install Keep webhook script following the [Keep documentation](https://docs.keephq.dev/providers/documentation/checkmk-provider).
  3. In Checkmk WebUI, go to Setup.
  4. Click on Add rule.
  5. In the Notifications method section, select Webhook - KeepHQ and choose "Call with the following parameters:".
  6. Configure the Rule properties, Contact selections, and Conditions according to your requirements.
  7. The first parameter is the Webhook URL of Keep which is {keep_webhook_api_url}.
  8. The second parameter is the API Key of Keep which is {api_key}.
  9. Click on Save.
  10. Now Checkmk will be able to send alerts to Keep.
  """

    SEVERITIES_MAP = {
        "OK": AlertSeverity.INFO,
        "WARN": AlertSeverity.WARNING,
        "CRIT": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "ACKNOWLEDGED": AlertStatus.ACKNOWLEDGED,
        "UNREACH": AlertStatus.FIRING,
    }

    PROVIDER_DISPLAY_NAME = "Checkmk"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["id"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_hosts",
            description="Read hosts from Checkmk",
            mandatory=True,
            mandatory_for_webhook=False,
            documentation_url="https://checkmk.com/guide/latest/api/host",
        ),
        ProviderScope(
            name="read_services",
            description="Read services from Checkmk",
            mandatory=True,
            mandatory_for_webhook=False,
            documentation_url="https://checkmk.com/guide/latest/api/service",
        ),
        ProviderScope(
            name="read_events",
            description="Read events from Checkmk",
            mandatory=False,
            mandatory_for_webhook=False,
            documentation_url="https://checkmk.com/guide/latest/api/events",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.checkmk_url = config.authentication.get("checkmk_url", "").rstrip("/")
        self.checkmk_username = config.authentication.get("checkmk_username", "")
        self.checkmk_auth_token = config.authentication.get("checkmk_auth_token", "")
        self.verify_ssl = config.authentication.get("verify_ssl", True)

    def validate_config(self):
        """
        Validates that Checkmk URL and credentials are provided.
        """
        if not self.checkmk_url:
            raise ProviderMethodException(
                "Checkmk URL is required", context_manager=self.context_manager
            )
        if not self.checkmk_username or not self.checkmk_auth_token:
            raise ProviderMethodException(
                "Checkmk username and auth token are required",
                context_manager=self.context_manager,
            )

    def _get_headers(self) -> dict:
        """Get headers for Checkmk API requests."""
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.checkmk_username}/{self.checkmk_auth_token}",
        }

    def _get_all_hosts(self) -> list[dict]:
        """Fetch all hosts from Checkmk."""
        url = f"{self.checkmk_url}/domain-types/host_config/collections/all"
        try:
            response = requests.get(
                url, headers=self._get_headers(), verify=self.verify_ssl, timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get("value", [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching hosts from Checkmk: {e}")
            raise ProviderMethodException(
                f"Failed to fetch hosts: {str(e)}", context_manager=self.context_manager
            )

    def _get_all_services(self, host_name: Optional[str] = None) -> list[dict]:
        """Fetch services from Checkmk, optionally filtered by host."""
        params = {"host_name": host_name} if host_name else {}
        url = f"{self.checkmk_url}/domain-types/service/collections/all"
        try:
            response = requests.get(
                url, headers=self._get_headers(), params=params, verify=self.verify_ssl, timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get("value", [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching services from Checkmk: {e}")
            raise ProviderMethodException(
                f"Failed to fetch services: {str(e)}", context_manager=self.context_manager
            )

    def pull_alerts(self):
        """
        Pull alerts from Checkmk by fetching all problem hosts and services.
        """
        self.validate_config()
        alerts = []

        # Fetch hosts with problems
        try:
            hosts = self._get_all_hosts()
            problem_hosts = [
                h for h in hosts
                if h.get("extensions", {}).get("attributes", {}).get("tag_criticality") == "production"
            ]
            logger.info(f"Found {len(problem_hosts)} production hosts")
        except ProviderMethodException:
            problem_hosts = []

        # Fetch services and convert to alerts
        try:
            services = self._get_all_services()
            for service in services:
                extensions = service.get("extensions", {})
                attrs = extensions.get("attributes", {})
                
                # Get host and service state
                host = service.get("title", "").split(" / ")[0] if " / " in service.get("title", "") else ""
                service_name = service.get("title", "")
                state = extensions.get("state", 0)
                check_type = extensions.get("check_type", "")
                
                # Map state to severity
                state_map = {0: "OK", 1: "WARN", 2: "CRIT", 3: "UNKNOWN"}
                severity_map = {0: AlertSeverity.INFO, 1: AlertSeverity.WARNING, 2: AlertSeverity.CRITICAL, 3: AlertSeverity.INFO}
                
                # Only include non-OK states as alerts
                if state != 0:
                    alert = AlertDto(
                        id=service.get("id", ""),
                        name=f"{host} / {service_name}" if host else service_name,
                        description=f"Check: {check_type}",
                        severity=severity_map.get(state, AlertSeverity.INFO),
                        status=AlertStatus.FIRING,
                        host=host,
                        source=["checkmk"],
                        lastReceived=datetime.now(timezone.utc).isoformat(),
                    )
                    alerts.append(alert)
                    logger.info(f"Alert: {alert.name} - State: {state_map.get(state, 'UNKNOWN')}")
        except ProviderMethodException as e:
            logger.error(f"Error pulling services: {e}")

        logger.info(f"Pulled {len(alerts)} alerts from Checkmk")
        return alerts

    @staticmethod
    def convert_to_utc_isoformat(long_date_time: str, default: str) -> str:
        # Early return if long_date_time is None
        if long_date_time is None:
            logger.warning("Received None as long_date_time, returning default value")
            return default

        logger.info(f"Converting {long_date_time} to UTC ISO format")
        formats = [
            "%a %b %d %H:%M:%S %Z %Y",  # For timezone names (e.g., CEST, UTC)
            "%a %b %d %H:%M:%S %z %Y",  # For timezone offsets (e.g., +0700, -0500)
            "%a %b %d %H:%M:%S %z%z %Y",  # For space-separated offsets (e.g., +07 00)
        ]

        for date_format in formats:
            try:
                # Handle special case where timezone offset has a space
                if "+" in long_date_time or "-" in long_date_time:
                    # Remove space in timezone offset if present (e.g., '+07 00' -> '+0700')
                    parts = long_date_time.split()
                    if (
                        len(parts) == 6 and len(parts[4]) == 3
                    ):  # If offset is +07, we need +0700
                        parts[4] = parts[4] + "00"
                        long_date_time = " ".join(parts)
                    if len(parts) == 7:  # If offset is split into two parts
                        offset = parts[-3] + parts[-2]
                        long_date_time = " ".join(parts[:-3] + [offset] + parts[-1:])

                # Parse the datetime string
                local_dt = datetime.strptime(long_date_time, date_format)

                # Convert to UTC if it has timezone info, otherwise assume UTC
                if local_dt.tzinfo is None:
                    local_dt = local_dt.replace(tzinfo=timezone.utc)
                utc_dt = local_dt.astimezone(timezone.utc)

                # Return the ISO 8601 format
                return utc_dt.isoformat()

            except ValueError:
                continue

        # If none of the formats match
        logger.exception(f"Error converting {long_date_time} to UTC ISO format")
        return default

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: BaseProvider = None
    ) -> AlertDto | list[AlertDto]:
        """
        Service alerts and Host alerts have different fields, so we are mapping the fields based on the event type.
        """

        def _check_values(value):
            if value not in event or event.get(value) == "":
                return None
            return event.get(value)

        # Service alerts don't have a status field, so we are mapping the status based on the severity.
        def _set_severity(status):
            if status == "UP":
                return AlertSeverity.INFO
            elif status == "DOWN":
                return AlertSeverity.CRITICAL
            elif status == "UNREACH":
                return AlertSeverity.CRITICAL

        # https://forum.checkmk.com/t/convert-notify-shortdatetime-to-utc-timezone/20158/2
        microtime = _check_values("micro_time")
        logger.info(f"Microtime: {microtime}")
        if microtime:
            ts = int(int(microtime) / 1000000)
            dt_object = datetime.fromtimestamp(ts)
            last_received = dt_object.isoformat()
        else:
            last_received = CheckmkProvider.convert_to_utc_isoformat(
                _check_values("long_date_time"), _check_values("short_date_time")
            )

        alert = AlertDto(
            id=_check_values("id"),
            name=_check_values("check_command"),
            description=_check_values("summary"),
            severity=CheckmkProvider.SEVERITIES_MAP.get(
                event.get("severity"), _set_severity(event.get("status"))
            ),
            status=CheckmkProvider.STATUS_MAP.get(
                event.get("status"), AlertStatus.FIRING
            ),
            host=_check_values("host"),
            alias=_check_values("alias"),
            address=_check_values("address"),
            service=_check_values("service"),
            source=["checkmk"],
            current_event=_check_values("event"),
            output=_check_values("output"),
            long_output=_check_values("long_output"),
            path_url=_check_values("url"),
            perf_data=_check_values("perf_data"),
            site=_check_values("site"),
            what=_check_values("what"),
            notification_type=_check_values("notification_type"),
            contact_name=_check_values("contact_name"),
            contact_email=_check_values("contact_email"),
            contact_pager=_check_values("contact_pager"),
            date=_check_values("date"),
            lastReceived=last_received,
            long_date=_check_values("long_date_time"),
        )

        return alert


if __name__ == "__main__":
    pass
