"""
Nagios Provider is a class that allows to ingest/digest data from Nagios XI.
"""

import dataclasses
import datetime
import logging
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod
from keep.providers.providers_factory import ProvidersFactory

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    Nagios XI authentication configuration.
    """

    nagios_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI URL",
            "hint": "https://nagios.example.com/nagiosxi",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI API Key",
            "hint": "Found in Admin > Manage API Keys",
            "sensitive": True,
        }
    )
    verify: bool = dataclasses.field(
        metadata={
            "description": "Verify SSL certificates",
            "hint": "Set to false to allow self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )


class NagiosProvider(BaseProvider):
    """
    Pull/Push alerts from Nagios XI into Keep.
    """

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]
    FINGERPRINT_FIELDS = ["id"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="servicestatus",
            description="Read service status from Nagios XI API.",
            mandatory=True,
            documentation_url="https://www.nagios.org/documentation/",
        ),
        ProviderScope(
            name="hoststatus",
            description="Read host status from Nagios XI API.",
            mandatory=True,
            documentation_url="https://www.nagios.org/documentation/",
        ),
    ]

    PROVIDER_METHODS = [
        ProviderMethod(
            name="Acknowledge Problem",
            func_name="acknowledge_problem",
            scopes=["servicestatus"],
            type="action",
        ),
    ]

    # Nagios service states: 0=OK, 1=WARNING, 2=CRITICAL, 3=UNKNOWN
    SEVERITIES_MAP = {
        0: AlertSeverity.INFO,
        1: AlertSeverity.WARNING,
        2: AlertSeverity.CRITICAL,
        3: AlertSeverity.INFO,
        "0": AlertSeverity.INFO,
        "1": AlertSeverity.WARNING,
        "2": AlertSeverity.CRITICAL,
        "3": AlertSeverity.INFO,
        "OK": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
    }

    # Nagios host states: 0=UP, 1=DOWN, 2=UNREACHABLE
    HOST_SEVERITIES_MAP = {
        0: AlertSeverity.INFO,
        1: AlertSeverity.CRITICAL,
        2: AlertSeverity.HIGH,
        "0": AlertSeverity.INFO,
        "1": AlertSeverity.CRITICAL,
        "2": AlertSeverity.HIGH,
        "UP": AlertSeverity.INFO,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.HIGH,
    }

    STATUS_MAP = {
        0: AlertStatus.RESOLVED,
        1: AlertStatus.FIRING,
        2: AlertStatus.FIRING,
        3: AlertStatus.FIRING,
        "0": AlertStatus.RESOLVED,
        "1": AlertStatus.FIRING,
        "2": AlertStatus.FIRING,
        "3": AlertStatus.FIRING,
        "OK": AlertStatus.RESOLVED,
        "UP": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
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

    def validate_scopes(self) -> dict[str, bool | str]:
        validated_scopes = {}
        for scope in self.PROVIDER_SCOPES:
            try:
                self._send_request(f"objects/{scope.name}", {"records": "1"})
                validated_scopes[scope.name] = True
            except Exception as e:
                validated_scopes[scope.name] = str(e)
        return validated_scopes

    def _send_request(
        self, endpoint: str, params: Optional[dict] = None
    ) -> dict:
        """
        Send a request to the Nagios XI REST API.

        Args:
            endpoint: The API endpoint (e.g., 'objects/servicestatus').
            params: Additional query parameters.

        Returns:
            dict: The JSON response from Nagios XI.
        """
        base_url = str(self.authentication_config.nagios_url).rstrip("/")
        url = f"{base_url}/api/v1/{endpoint}"
        request_params = {"apikey": self.authentication_config.api_key}
        if params:
            request_params.update(params)

        response = requests.get(
            url,
            params=request_params,
            verify=self.authentication_config.verify,
        )

        try:
            response.raise_for_status()
        except requests.HTTPError:
            self.logger.exception(
                "Error while sending request to Nagios XI API",
                extra={
                    "response": response.text,
                    "tenant_id": self.context_manager.tenant_id,
                },
            )
            raise

        return response.json()

    def _post_request(
        self, endpoint: str, data: Optional[dict] = None
    ) -> dict:
        """
        Send a POST request to the Nagios XI REST API.

        Args:
            endpoint: The API endpoint.
            data: POST body data.

        Returns:
            dict: The JSON response from Nagios XI.
        """
        base_url = str(self.authentication_config.nagios_url).rstrip("/")
        url = f"{base_url}/api/v1/{endpoint}"
        post_data = {"apikey": self.authentication_config.api_key}
        if data:
            post_data.update(data)

        response = requests.post(
            url,
            data=post_data,
            verify=self.authentication_config.verify,
        )

        try:
            response.raise_for_status()
        except requests.HTTPError:
            self.logger.exception(
                "Error while sending POST request to Nagios XI API",
                extra={
                    "response": response.text,
                    "tenant_id": self.context_manager.tenant_id,
                },
            )
            raise

        return response.json()

    def acknowledge_problem(
        self,
        host_name: str,
        service_description: str = None,
        comment: str = "Acknowledged via Keep",
        sticky: bool = True,
        notify: bool = True,
        persistent: bool = True,
    ):
        """
        Acknowledge a host or service problem in Nagios XI.

        Args:
            host_name: The host name.
            service_description: The service description (optional, for service problems).
            comment: Acknowledgement comment.
            sticky: Whether the acknowledgement is sticky.
            notify: Whether to send notifications.
            persistent: Whether the comment is persistent.
        """
        self.logger.info(
            f"Acknowledging problem for host={host_name}, service={service_description}"
        )

        if service_description:
            # Acknowledge service problem
            cmd = "ACKNOWLEDGE_SVC_PROBLEM"
            data = {
                "cmd": cmd,
                "host_name": host_name,
                "service_description": service_description,
                "sticky": "1" if sticky else "0",
                "notify": "1" if notify else "0",
                "persistent": "1" if persistent else "0",
                "comment": comment,
            }
        else:
            # Acknowledge host problem
            cmd = "ACKNOWLEDGE_HOST_PROBLEM"
            data = {
                "cmd": cmd,
                "host_name": host_name,
                "sticky": "1" if sticky else "0",
                "notify": "1" if notify else "0",
                "persistent": "1" if persistent else "0",
                "comment": comment,
            }

        self._post_request("system/command", data)
        self.logger.info(
            f"Acknowledged problem for host={host_name}, service={service_description}"
        )

    def _get_alerts(self) -> list[AlertDto]:
        """
        Get alerts from Nagios XI by pulling service and host status.
        """
        alerts = []

        # Get service problems (non-OK states)
        try:
            service_data = self._send_request(
                "objects/servicestatus",
                {
                    "current_state": "in:1,2,3",  # WARNING, CRITICAL, UNKNOWN
                },
            )
            for record in service_data.get("servicestatus", []):
                alerts.append(self._format_service_alert(record))
        except Exception:
            self.logger.exception("Error fetching service status from Nagios XI")

        # Get host problems (non-UP states)
        try:
            host_data = self._send_request(
                "objects/hoststatus",
                {
                    "current_state": "in:1,2",  # DOWN, UNREACHABLE
                },
            )
            for record in host_data.get("hoststatus", []):
                alerts.append(self._format_host_alert(record))
        except Exception:
            self.logger.exception("Error fetching host status from Nagios XI")

        return alerts

    def _format_service_alert(self, service: dict) -> AlertDto:
        """
        Format a Nagios XI service status record into an AlertDto.
        """
        current_state = service.get("current_state", 3)
        severity = self.SEVERITIES_MAP.get(current_state, AlertSeverity.INFO)

        # Determine status
        if service.get("problem_acknowledged", "0") == "1":
            status = AlertStatus.ACKNOWLEDGED
        else:
            status = self.STATUS_MAP.get(current_state, AlertStatus.FIRING)

        last_check = service.get("last_check")
        if last_check:
            try:
                last_received = datetime.datetime.fromtimestamp(
                    int(last_check), tz=datetime.timezone.utc
                ).isoformat()
            except (ValueError, TypeError):
                last_received = datetime.datetime.now(
                    tz=datetime.timezone.utc
                ).isoformat()
        else:
            last_received = datetime.datetime.now(
                tz=datetime.timezone.utc
            ).isoformat()

        host_name = service.get("host_name", "unknown")
        service_description = service.get("service_description", service.get("name", "unknown"))

        return AlertDto(
            id=f"{host_name}/{service_description}",
            name=service_description,
            status=status,
            severity=severity,
            lastReceived=last_received,
            source=["nagios"],
            message=service.get("status_text", service.get("output", "")),
            description=service.get("status_text", service.get("output", "")),
            hostname=host_name,
            service=service_description,
            current_state=current_state,
            last_state_change=service.get("last_state_change"),
            check_command=service.get("check_command"),
            current_attempt=service.get("current_attempt"),
            max_attempts=service.get("max_attempts"),
            problem_acknowledged=service.get("problem_acknowledged"),
        )

    def _format_host_alert(self, host: dict) -> AlertDto:
        """
        Format a Nagios XI host status record into an AlertDto.
        """
        current_state = host.get("current_state", 0)
        severity = self.HOST_SEVERITIES_MAP.get(current_state, AlertSeverity.INFO)

        if host.get("problem_acknowledged", "0") == "1":
            status = AlertStatus.ACKNOWLEDGED
        else:
            status = self.STATUS_MAP.get(current_state, AlertStatus.FIRING)

        last_check = host.get("last_check")
        if last_check:
            try:
                last_received = datetime.datetime.fromtimestamp(
                    int(last_check), tz=datetime.timezone.utc
                ).isoformat()
            except (ValueError, TypeError):
                last_received = datetime.datetime.now(
                    tz=datetime.timezone.utc
                ).isoformat()
        else:
            last_received = datetime.datetime.now(
                tz=datetime.timezone.utc
            ).isoformat()

        host_name = host.get("host_name", host.get("name", "unknown"))

        return AlertDto(
            id=host_name,
            name=f"Host {host_name}",
            status=status,
            severity=severity,
            lastReceived=last_received,
            source=["nagios"],
            message=host.get("status_text", host.get("output", "")),
            description=host.get("status_text", host.get("output", "")),
            hostname=host_name,
            service="host",
            ip_address=host.get("address"),
            current_state=current_state,
            last_state_change=host.get("last_state_change"),
            check_command=host.get("check_command"),
            problem_acknowledged=host.get("problem_acknowledged"),
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format a Nagios webhook event into an AlertDto.

        Supports both Nagios XI webhook payloads and custom webhook formats.
        """
        # Try to determine if this is a host or service alert
        alert_type = event.get("type", event.get("notification_type", "service")).lower()
        host_name = event.get("host_name", event.get("hostname", "unknown"))
        service_description = event.get(
            "service_description", event.get("service", "")
        )

        # Determine severity
        state = event.get("state", event.get("current_state", event.get("severity", "UNKNOWN")))
        if "host" in alert_type or not service_description:
            severity = NagiosProvider.HOST_SEVERITIES_MAP.get(
                state, AlertSeverity.INFO
            )
        else:
            severity = NagiosProvider.SEVERITIES_MAP.get(state, AlertSeverity.INFO)

        # Determine status
        status_raw = event.get("status", state)
        if event.get("problem_acknowledged") == "1":
            status = AlertStatus.ACKNOWLEDGED
        else:
            status = NagiosProvider.STATUS_MAP.get(status_raw, AlertStatus.FIRING)

        # Determine last received time
        last_received = event.get(
            "lastReceived",
            event.get(
                "timestamp",
                datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            ),
        )

        # Build alert ID
        if service_description:
            alert_id = event.get("id", f"{host_name}/{service_description}")
            name = service_description
        else:
            alert_id = event.get("id", host_name)
            name = f"Host {host_name}"

        output = event.get("output", event.get("status_text", event.get("message", "")))

        return AlertDto(
            id=alert_id,
            name=event.get("name", name),
            status=status,
            severity=severity,
            lastReceived=last_received,
            source=["nagios"],
            message=output,
            description=output,
            hostname=host_name,
            service=service_description or "host",
            ip_address=event.get("address", event.get("ip_address")),
            url=event.get("url"),
            pushed=True,
        )


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    api_key = os.environ.get("NAGIOS_API_KEY")
    nagios_url = os.environ.get("NAGIOS_URL", "http://localhost/nagiosxi")

    provider_config = {
        "authentication": {
            "api_key": api_key,
            "nagios_url": nagios_url,
        },
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="nagios",
        provider_type="nagios",
        provider_config=provider_config,
    )
    alerts = provider.get_alerts()
    print(f"Got {len(alerts)} alerts")
