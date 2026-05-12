"""
Nagios Provider allows ingesting alerts from Nagios via Livestatus or webhook.
"""

import dataclasses
import datetime
import json
import logging
import os
import socket
import re
from typing import Union

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.base.provider_exceptions import ProviderMethodException
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    Nagios authentication configuration.
    """

    nagios_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios Frontend/API URL",
            "hint": "https://nagios.example.com",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    livestatus_host: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Livestatus Host (default: localhost)",
            "hint": "localhost",
            "sensitive": False,
        },
        default="localhost",
    )
    livestatus_port: int = dataclasses.field(
        metadata={
            "required": False,
            "description": "Livestatus Port (default: 6557)",
            "hint": "6557",
            "sensitive": False,
        },
        default=6557,
    )
    api_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "API Key for webhook authentication",
            "hint": "Your Keep API key",
            "sensitive": True,
        },
        default="",
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
    Pull/Push alerts from Nagios into Keep via Livestatus or webhook.
    """

    PROVIDER_CATEGORY = ["Monitoring"]
    KEEP_NAGIOS_WEBHOOK_INTEGRATION_NAME = "keep"
    KEEP_NAGIOS_WEBHOOK_SCRIPT_FILENAME = "nagios_provider_script.js"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_problems",
            description="Read problems from Nagios via Livestatus",
            mandatory=False,
            mandatory_for_webhook=False,
            documentation_url="https://docs.nagios.org/nagioscore/en/livestatus",
        ),
        ProviderScope(
            name="read_hosts",
            description="Read host status from Nagios via Livestatus",
            mandatory=False,
            mandatory_for_webhook=False,
            documentation_url="https://docs.nagios.org/nagioscore/en/livestatus",
        ),
        ProviderScope(
            name="read_services",
            description="Read service status from Nagios via Livestatus",
            mandatory=False,
            mandatory_for_webhook=False,
            documentation_url="https://docs.nagios.org/nagioscore/en/livestatus",
        ),
    ]

    PROVIDER_METHODS = [
        ProviderMethod(
            name="Acknowledge Problem",
            func_name="acknowledge_problem",
            scopes=["read_problems"],
            type="action",
        ),
        ProviderMethod(
            name="Schedule Downtime",
            func_name="schedule_downtime",
            scopes=["read_problems"],
            type="action",
        ),
        ProviderMethod(
            name="Remove Acknowledgement",
            func_name="remove_acknowledgement",
            scopes=["read_problems"],
            type="action",
        ),
        ProviderMethod(
            name="Get Problems",
            func_name="get_problems",
            scopes=["read_problems"],
            type="view",
        ),
    ]

    SEVERITIES_MAP = {
        0: AlertSeverity.INFO,
        1: AlertSeverity.WARNING,
        2: AlertSeverity.CRITICAL,
        3: AlertSeverity.CRITICAL,
    }

    SERVICE_SEVERITY_MAP = {
        "OK": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.WARNING,
    }

    STATUS_MAP = {
        "OK": AlertStatus.RESOLVED,
        "UP": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "DOWN": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
        "PENDING": AlertStatus.FIRING,
    }

    NAGIOS_STATE_MAP = {
        0: "OK",
        1: "WARNING",
        2: "CRITICAL",
        3: "UNKNOWN",
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Nagios provider.
        """
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        validated_scopes = {}
        for scope in self.PROVIDER_SCOPES:
            try:
                if scope.name == "read_problems":
                    self._get_problems_livestatus()
            except Exception as e:
                error = str(e)
                if "connection" in error.lower() or "refused" in error.lower():
                    validated_scopes[scope.name] = "Livestatus connection failed"
                    continue
                validated_scopes[scope.name] = error
                continue
            validated_scopes[scope.name] = True
        return validated_scopes

    def _send_livestatus_request(self, query: str) -> list:
        """
        Send a Livestatus query to Nagios.

        Args:
            query (str): The Livestatus query.

        Returns:
            list: The query results.
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect(
                (
                    self.authentication_config.livestatus_host,
                    self.authentication_config.livestatus_port,
                )
            )
            sock.send(query.encode())
            response = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
            sock.close()

            if not response:
                return []

            lines = response.decode("utf-8").strip().split("\n")
            if len(lines) < 2:
                return []

            headers = lines[0].split(";")
            num_columns = len(headers)

            results = []
            for line in lines[1:]:
                if not line:
                    continue
                values = line.split(";")
                if len(values) == num_columns:
                    row = dict(zip(headers, values))
                    results.append(row)
            return results

        except socket.error as e:
            self.logger.error(f"Livestatus connection error: {e}")
            raise ProviderMethodException(f"Livestatus connection failed: {e}")

    def _get_problems_livestatus(self) -> list[dict]:
        """
        Get problems from Nagios via Livestatus.

        Returns:
            list[dict]: List of problems.
        """
        query = "GET services\nFilter: state > 0\nFilter: acknowledged = 0\nColumns: host_name service_description state output last_check\n"
        return self._send_livestatus_request(query)

    def acknowledge_problem(self, host: str, service: str):
        """
        Acknowledge a problem (via external command file).

        Args:
            host (str): The host name.
            service (str): The service description.
        """
        self.logger.info(f"Acknowledging problem for {host}/{service}")
        self._send_external_command(
            f"ACKNOWLEDGE_SVC_PROBLEM;{host};{service};2;1;1;Keep Provider;Acknowledged via Keep"
        )
        self.logger.info(f"Acknowledged problem for {host}/{service}")

    def remove_acknowledgement(self, host: str, service: str):
        """
        Remove acknowledgement from a problem.

        Args:
            host (str): The host name.
            service (str): The service description.
        """
        self.logger.info(f"Removing acknowledgement for {host}/{service}")
        self._send_external_command(
            f"REMOVE_SVC_ACKNOWLEDGEMENT;{host};{service}"
        )
        self.logger.info(f"Removed acknowledgement for {host}/{service}")

    def schedule_downtime(
        self,
        host: str,
        service: str,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        comment: str = "Downtime scheduled via Keep",
    ):
        """
        Schedule downtime for a service.

        Args:
            host (str): The host name.
            service (str): The service description.
            start_time (datetime): Start time.
            end_time (datetime): End time.
            comment (str): Comment for the downtime.
        """
        self.logger.info(f"Scheduling downtime for {host}/{service}")
        start_ts = int(start_time.timestamp())
        end_ts = int(end_time.timestamp())
        self._send_external_command(
            f"SCHEDULE_SVC_DOWNTIME;{host};{service};{start_ts};{end_ts};1;0;{comment}"
        )
        self.logger.info(f"Scheduled downtime for {host}/{service}")

    def _send_external_command(self, command: str):
        """
        Send external command to Nagios command file.

        Args:
            command (str): The command to send.
        """
        command_file = "/var/nagios/rw/nagios.cmd"
        try:
            with open(command_file, "w") as f:
                f.write(f"[{int(datetime.datetime.now().timestamp())}] {command}\n")
        except PermissionError:
            raise ProviderMethodException(
                "Cannot write to Nagios command file. Check permissions."
            )
        except FileNotFoundError:
            raise ProviderMethodException(
                "Nagios command file not found. Check configuration."
            )

    def get_problems(self):
        """
        Get all current problems from Nagios.

        Returns:
            list[dict]: List of problems.
        """
        return self._get_alerts()

    @staticmethod
    def _convert_severity(severity: Union[int, str]) -> AlertSeverity:
        """
        Convert Nagios severity to Keep AlertSeverity.

        Args:
            severity (Union[int, str]): The severity value. Can be:
                - Integer (0-3): 0=OK, 1=WARNING, 2=CRITICAL, 3=UNKNOWN
                - String: "OK", "WARNING", "CRITICAL", "UNKNOWN"

        Returns:
            AlertSeverity: The corresponding Keep AlertSeverity
        """
        if isinstance(severity, int):
            return NagiosProvider.SEVERITIES_MAP.get(severity, AlertSeverity.INFO)

        if isinstance(severity, str):
            severity_upper = severity.upper().strip()
            return NagiosProvider.SERVICE_SEVERITY_MAP.get(severity_upper, AlertSeverity.INFO)

        return AlertSeverity.INFO

    def _get_alerts(self) -> list[AlertDto]:
        """
        Get alerts from Nagios via Livestatus.

        Returns:
            list[AlertDto]: List of formatted alerts.
        """
        try:
            problems = self._get_problems_livestatus()
        except ProviderMethodException:
            self.logger.warning("Livestatus not available, returning empty list")
            return []

        formatted_alerts = []
        for problem in problems:
            host_name = problem.get("host_name", "unknown")
            service_description = problem.get("service_description", "unknown")
            state = problem.get("state", "0")
            output = problem.get("output", "")
            last_check = problem.get("last_check", "")

            severity = self._convert_severity(int(state))
            status = NagiosProvider.STATUS_MAP.get(
                NagiosProvider.NAGIOS_STATE_MAP.get(int(state), "UNKNOWN"),
                AlertStatus.FIRING,
            )

            alert_id = f"{host_name}:{service_description}"

            last_received = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
            if last_check:
                try:
                    last_received = datetime.datetime.fromtimestamp(
                        int(last_check)
                    ).isoformat()
                except (ValueError, TypeError):
                    pass

            formatted_alerts.append(
                AlertDto(
                    id=alert_id,
                    name=f"{host_name} - {service_description}",
                    status=status,
                    lastReceived=last_received,
                    source=["nagios"],
                    message=output,
                    severity=severity,
                    environment="production",
                    problem=problem,
                    hostname=host_name,
                    service=service_description,
                )
            )
        return formatted_alerts

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        """
        Setup webhook for Nagios.
        This provides instructions for configuring Nagios notification commands.
        """
        self.logger.info("Setting up Nagios webhook")

        __location__ = os.path.realpath(
            os.path.join(os.getcwd(), os.path.dirname(__file__))
        )

        with open(
            os.path.join(
                __location__, NagiosProvider.KEEP_NAGIOS_WEBHOOK_SCRIPT_FILENAME
            )
        ) as f:
            script = f.read()

        self.logger.info(
            "Nagios webhook setup complete. To configure:\n"
            "1. Copy the notification script to your Nagios object directory\n"
            "2. Add a command definition using the script\n"
            "3. Associate the command with contact/contactgroup notifications\n"
            f"Script location: {__location__}/{NagiosProvider.KEEP_NAGIOS_WEBHOOK_SCRIPT_FILENAME}"
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format a Nagios alert from webhook.

        Args:
            event (dict): The raw Nagios event payload.
            provider_instance (BaseProvider): The provider instance.

        Returns:
            AlertDto: The formatted alert.
        """
        host_name = event.get("host_name", event.get("HOSTNAME", "unknown"))
        service_description = event.get("service_description", event.get("SERVICEDESC", ""))
        state = event.get("state", event.get("SERVICESTATE", "UNKNOWN"))
        output = event.get("output", event.get("SERVICEOUTPUT", ""))
        long_output = event.get("long_output", event.get("LONGSERVICEOUTPUT", ""))
        check_time = event.get("check_time", event.get("TIMET", ""))
        notification_type = event.get("notification_type", event.get("NOTIFICATIONTYPE", ""))

        alert_id = f"{host_name}:{service_description}" if service_description else host_name

        if provider_instance:
            severity = provider_instance._convert_severity(state)
            status = provider_instance.STATUS_MAP.get(state.upper(), AlertStatus.FIRING)
        else:
            severity = NagiosProvider._convert_severity(state)
            status = NagiosProvider.STATUS_MAP.get(state.upper(), AlertStatus.FIRING)

        if notification_type in ["RECOVERY", "OK"]:
            status = AlertStatus.RESOLVED
            severity = AlertSeverity.INFO

        last_received = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        if check_time:
            try:
                last_received = datetime.datetime.fromtimestamp(
                    int(check_time)
                ).isoformat()
            except (ValueError, TypeError):
                pass

        message = output
        if long_output:
            message = f"{output}\n{long_output}"

        tags = {
            "notification_type": notification_type,
            "nagios_state": state,
        }

        return AlertDto(
            id=alert_id,
            name=f"{host_name} - {service_description}" if service_description else host_name,
            status=status,
            lastReceived=last_received,
            source=["nagios"],
            message=message,
            severity=severity,
            environment=event.get("environment", "production"),
            pushed=True,
            hostname=host_name,
            service=service_description or "host",
            tags=tags,
            url=event.get("nagios_url"),
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    provider_config = {
        "authentication": {
            "nagios_url": "http://localhost",
            "livestatus_host": "localhost",
            "livestatus_port": 6557,
        },
    }
    from keep.providers.providers_factory import ProvidersFactory

    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="nagios",
        provider_type="nagios",
        provider_config=provider_config,
    )
    alerts = provider.get_alerts()
    print(f"Found {len(alerts)} alerts")