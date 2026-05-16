"""
NagiosXIProvider is a class that provides a set of methods to interact with the Nagios XI REST API.

Nagios XI is a monitoring platform. This provider polls host and service status
via the Nagios XI REST API using apikey authentication, following the same
polling pattern as the CentreonProvider.

State mapping (Nagios convention):
  - 0 = OK       -> AlertStatus.RESOLVED, AlertSeverity.LOW
  - 1 = WARNING  -> AlertStatus.FIRING,   AlertSeverity.WARNING
  - 2 = CRITICAL -> AlertStatus.FIRING,   AlertSeverity.CRITICAL
  - 3 = UNKNOWN  -> AlertStatus.FIRING,   AlertSeverity.INFO

References:
  - Nagios XI REST API: https://api.nagios.org/
  - CentreonProvider (reference implementation)
"""

import dataclasses
import datetime

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class NagiosxiProviderAuthConfig:
    """
    NagiosxiProviderAuthConfig holds the authentication information for the
    Nagios XI provider.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI Host URL (e.g. https://nagios.example.com/nagios)",
            "sensitive": False,
            "validation": "any_http_url",
        },
    )

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI API Key",
            "sensitive": True,
        },
        default=None,
    )


class NagiosxiProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Nagios XI"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="API key is valid and user is authenticated",
        ),
    ]

    # Nagios state codes:
    #   0 = OK, 1 = WARNING, 2 = CRITICAL, 3 = UNKNOWN
    # https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/3/en/statetypes.html
    HOST_STATUS_MAP = {
        0: AlertStatus.RESOLVED,   # UP
        1: AlertStatus.FIRING,     # DOWN
        2: AlertStatus.FIRING,     # UNREACHABLE
    }

    HOST_SEVERITY_MAP = {
        0: AlertSeverity.LOW,       # UP
        1: AlertSeverity.CRITICAL,  # DOWN
        2: AlertSeverity.WARNING,   # UNREACHABLE
    }

    SERVICE_STATUS_MAP = {
        0: AlertStatus.RESOLVED,    # OK
        1: AlertStatus.FIRING,     # WARNING
        2: AlertStatus.FIRING,     # CRITICAL
        3: AlertStatus.FIRING,     # UNKNOWN
    }

    SERVICE_SEVERITY_MAP = {
        0: AlertSeverity.LOW,       # OK
        1: AlertSeverity.WARNING,   # WARNING
        2: AlertSeverity.CRITICAL,  # CRITICAL
        3: AlertSeverity.INFO,      # UNKNOWN
    }

    FINGERPRINT_FIELDS = ["id"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """
        Validates the configuration of the Nagios XI provider.
        """
        self.authentication_config = NagiosxiProviderAuthConfig(
            **self.config.authentication
        )

    def __get_url(self, endpoint: str) -> str:
        """
        Build the full API URL for a given Nagios XI REST API endpoint.

        Nagios XI REST API endpoints follow the pattern:
          {host_url}/api/v1/objects/{endpoint}
        """
        host_url = str(self.authentication_config.host_url).rstrip("/")
        return f"{host_url}/api/v1/objects/{endpoint}"

    def __get_params(self, extra: dict | None = None) -> dict:
        """
        Build common query parameters including the apikey.
        """
        params = {"apikey": self.authentication_config.api_key}
        if extra:
            params.update(extra)
        return params

    def __get_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate the scopes of the provider by making a test API call.
        """
        try:
            response = requests.get(
                self.__get_url("hoststatus"),
                params=self.__get_params(),
                headers=self.__get_headers(),
                timeout=10,
            )
            if response.ok:
                scopes = {"authenticated": True}
            else:
                scopes = {
                    "authenticated": f"Error validating scopes: {response.status_code} {response.text}"
                }
        except Exception as e:
            scopes = {
                "authenticated": f"Error validating scopes: {e}",
            }
        return scopes

    def __get_host_status(self) -> list[AlertDto]:
        """
        Fetch host status from Nagios XI via the REST API.

        Endpoint: /api/v1/objects/hoststatus
        Returns a list of AlertDto objects for each host.
        """
        try:
            response = requests.get(
                self.__get_url("hoststatus"),
                params=self.__get_params(),
                headers=self.__get_headers(),
                timeout=30,
            )

            if not response.ok:
                self.logger.error(
                    "Failed to get host status from Nagios XI: %s", response.text
                )
                raise ProviderException(
                    f"Failed to get host status from Nagios XI: {response.status_code}"
                )

            data = response.json()
            host_records = data.get("hoststatus", [])

            if not isinstance(host_records, list):
                # The API may return a single object if there's only one host
                if isinstance(host_records, dict):
                    host_records = [host_records]
                else:
                    host_records = []

            alerts = []
            for host in host_records:
                current_state = int(host.get("current_state", 3))
                last_check = host.get("last_check")
                if last_check:
                    try:
                        last_received = datetime.datetime.fromtimestamp(
                            float(last_check)
                        ).isoformat()
                    except (ValueError, TypeError, OSError):
                        last_received = datetime.datetime.now().isoformat()
                else:
                    last_received = datetime.datetime.now().isoformat()

                alert = AlertDto(
                    id=str(host.get("host_object_id", host.get("host_name", ""))),
                    name=host.get("host_name", ""),
                    address=host.get("address", ""),
                    description=host.get("output", ""),
                    status=self.HOST_STATUS_MAP.get(
                        current_state, AlertStatus.FIRING
                    ),
                    severity=self.HOST_SEVERITY_MAP.get(
                        current_state, AlertSeverity.INFO
                    ),
                    acknowledged=host.get("problem_has_been_acknowledged", "0") == "1",
                    lastReceived=last_received,
                    source=["nagiosxi"],
                    # Extra Nagios-specific fields
                    current_state=current_state,
                    host_alias=host.get("alias", ""),
                    host_status=host.get("status", ""),
                    check_command=host.get("check_command", ""),
                    max_check_attempts=host.get("max_check_attempts", ""),
                    current_check_attempt=host.get("current_check_attempt", ""),
                    state_type=host.get("state_type", ""),
                    is_flapping=host.get("is_flapping", "0") == "1",
                    scheduled_downtime_depth=host.get(
                        "scheduled_downtime_depth", "0"
                    ),
                    plugin_output=host.get("output", ""),
                    long_plugin_output=host.get("long_output", ""),
                    perf_data=host.get("perf_data", ""),
                )
                alerts.append(alert)

            return alerts

        except ProviderException:
            raise
        except Exception as e:
            self.logger.error("Error getting host status from Nagios XI: %s", e)
            raise ProviderException(
                f"Error getting host status from Nagios XI: {e}"
            ) from e

    def __get_service_status(self) -> list[AlertDto]:
        """
        Fetch service status from Nagios XI via the REST API.

        Endpoint: /api/v1/objects/servicestatus
        Returns a list of AlertDto objects for each service.
        """
        try:
            response = requests.get(
                self.__get_url("servicestatus"),
                params=self.__get_params(),
                headers=self.__get_headers(),
                timeout=30,
            )

            if not response.ok:
                self.logger.error(
                    "Failed to get service status from Nagios XI: %s", response.text
                )
                raise ProviderException(
                    f"Failed to get service status from Nagios XI: {response.status_code}"
                )

            data = response.json()
            service_records = data.get("servicestatus", [])

            if not isinstance(service_records, list):
                if isinstance(service_records, dict):
                    service_records = [service_records]
                else:
                    service_records = []

            alerts = []
            for service in service_records:
                current_state = int(service.get("current_state", 3))
                last_check = service.get("last_check")
                if last_check:
                    try:
                        last_received = datetime.datetime.fromtimestamp(
                            float(last_check)
                        ).isoformat()
                    except (ValueError, TypeError, OSError):
                        last_received = datetime.datetime.now().isoformat()
                else:
                    last_received = datetime.datetime.now().isoformat()

                host_name = service.get("host_name", "")
                service_description = service.get(
                    "service_description", service.get("description", "")
                )

                alert = AlertDto(
                    id=f"{host_name}/{service_description}",
                    name=service_description,
                    host=host_name,
                    description=service.get("output", ""),
                    status=self.SERVICE_STATUS_MAP.get(
                        current_state, AlertStatus.FIRING
                    ),
                    severity=self.SERVICE_SEVERITY_MAP.get(
                        current_state, AlertSeverity.INFO
                    ),
                    acknowledged=service.get("problem_has_been_acknowledged", "0")
                    == "1",
                    lastReceived=last_received,
                    source=["nagiosxi"],
                    # Extra Nagios-specific fields
                    current_state=current_state,
                    host_id=service.get("host_object_id", ""),
                    service_id=service.get("service_object_id", ""),
                    check_command=service.get("check_command", ""),
                    max_check_attempts=service.get("max_check_attempts", ""),
                    current_check_attempt=service.get("current_check_attempt", ""),
                    state_type=service.get("state_type", ""),
                    is_flapping=service.get("is_flapping", "0") == "1",
                    scheduled_downtime_depth=service.get(
                        "scheduled_downtime_depth", "0"
                    ),
                    plugin_output=service.get("output", ""),
                    long_plugin_output=service.get("long_output", ""),
                    perf_data=service.get("perf_data", ""),
                )
                alerts.append(alert)

            return alerts

        except ProviderException:
            raise
        except Exception as e:
            self.logger.error("Error getting service status from Nagios XI: %s", e)
            raise ProviderException(
                f"Error getting service status from Nagios XI: {e}"
            ) from e

    def _get_alerts(self) -> list[AlertDto]:
        """
        Collect alerts from Nagios XI by polling both host and service status.

        This method follows the CentreonProvider polling pattern:
        it calls private methods to fetch host status and service status,
        then combines the results into a single list of AlertDto objects.
        Errors in one method do not prevent the other from returning results.
        """
        alerts = []
        try:
            self.logger.info("Collecting alerts (host status) from Nagios XI")
            host_status_alerts = self.__get_host_status()
            alerts.extend(host_status_alerts)
        except Exception as e:
            self.logger.error("Error getting host status from Nagios XI: %s", e)

        try:
            self.logger.info("Collecting alerts (service status) from Nagios XI")
            service_status_alerts = self.__get_service_status()
            alerts.extend(service_status_alerts)
        except Exception as e:
            self.logger.error("Error getting service status from Nagios XI: %s", e)

        return alerts


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    host_url = os.environ.get("NAGIOSXI_HOST_URL")
    api_key = os.environ.get("NAGIOSXI_API_KEY")

    if host_url is None:
        raise ProviderException("NAGIOSXI_HOST_URL is not set")

    config = ProviderConfig(
        description="Nagios XI Provider",
        authentication={
            "host_url": host_url,
            "api_key": api_key,
        },
    )

    provider = NagiosxiProvider(
        context_manager,
        provider_id="nagiosxi",
        config=config,
    )

    alerts = provider._get_alerts()
    for alert in alerts:
        print(alert)
