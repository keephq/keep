"""
Centreon is a class that provides a set of methods to interact with the Centreon API.
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
class CentreonProviderAuthConfig:
    """
    CentreonProviderAuthConfig is a class that holds the authentication information for the CentreonProvider.
    """

    host_url: pydantic.AnyHttpUrl | None = dataclasses.field(
        metadata={
            "required": True,
            "description": "Centreon Host URL",
            "sensitive": False,
            "validation": "any_http_url",
        },
        default=None,
    )

    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Centreon API Token",
            "sensitive": True,
        },
        default=None,
    )


class CentreonProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Centreon"
    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(name="authenticated", description="User is authenticated"),
    ]

    """
  Centreon only supports the following host state (UP = 0, DOWN = 2, UNREA = 3)
  https://docs.centreon.com/docs/api/rest-api-v1/#realtime-information
  """

    STATUS_MAP = {
        2: AlertStatus.FIRING,
        3: AlertStatus.FIRING,
        0: AlertStatus.RESOLVED,
    }

    SEVERITY_MAP = {
        "CRITICAL": AlertSeverity.CRITICAL,
        "WARNING": AlertSeverity.WARNING,
        "UNKNOWN": AlertSeverity.INFO,
        "OK": AlertSeverity.LOW,
        "PENDING": AlertSeverity.INFO,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """
        Validates the configuration of the Centreon provider.
        """
        self.authentication_config = CentreonProviderAuthConfig(
            **self.config.authentication
        )

    def __get_url(self, params: str):
        url = self.authentication_config.host_url + "/centreon/api/index.php?" + params
        return url

    def __get_headers(self):
        return {
            "Content-Type": "application/json",
            "centreon-auth-token": self.authentication_config.api_token,
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate the scopes of the provider.
        """
        try:
            response = requests.get(
                self.__get_url("object=centreon_realtime_hosts&action=list"),
                headers=self.__get_headers(),
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
        try:
            url = self.__get_url("object=centreon_realtime_hosts&action=list")
            response = requests.get(url, headers=self.__get_headers())

            if not response.ok:
                self.logger.error(
                    "Failed to get host status from Centreon: %s", response.json()
                )
                raise ProviderException("Failed to get host status from Centreon")

            return [
                AlertDto(
                    id=host["id"],
                    name=host["name"],
                    address=host["address"],
                    description=host["output"],
                    status=host["state"],
                    severity=host["output"].split()[0],
                    instance_name=host["instance_name"],
                    acknowledged=host["acknowledged"],
                    max_check_attempts=host["max_check_attempts"],
                    lastReceived=datetime.datetime.fromtimestamp(
                        host["last_check"]
                    ).isoformat(),
                    source=["centreon"],
                )
                for host in response.json()
            ]

        except Exception as e:
            self.logger.error("Error getting host status from Centreon: %s", e)
            raise ProviderException(f"Error getting host status from Centreon: {e}") from e

    def __get_service_status(self) -> list[AlertDto]:
        try:
            url = self.__get_url("object=centreon_realtime_services&action=list")
            response = requests.get(url, headers=self.__get_headers())

            if not response.ok:
                self.logger.error(
                    "Failed to get service status from Centreon: %s", response.json()
                )
                raise ProviderException("Failed to get service status from Centreon")

            return [
                AlertDto(
                    id=service["service_id"],
                    host_id=service["host_id"],
                    name=service["name"],
                    description=service["description"],
                    status=service["state"],
                    severity=service["output"].split(":")[0],
                    acknowledged=service["acknowledged"],
                    max_check_attempts=service["max_check_attempts"],
                    lastReceived=datetime.datetime.fromtimestamp(
                        service["last_check"]
                    ).isoformat(),
                    source=["centreon"],
                )
                for service in response.json()
            ]

        except Exception as e:
            self.logger.error("Error getting service status from Centreon: %s", e)
            raise ProviderException(f"Error getting service status from Centreon: {e}") from e

    def _get_alerts(self) -> list[AlertDto]:
        alerts = []
        try:
            self.logger.info("Collecting alerts (host status) from Centreon")
            host_status_alerts = self.__get_host_status()
            alerts.extend(host_status_alerts)
        except Exception as e:
            self.logger.error("Error getting host status from Centreon: %s", e)

        try:
            self.logger.info("Collecting alerts (service status) from Centreon")
            service_status_alerts = self.__get_service_status()
            alerts.extend(service_status_alerts)
        except Exception as e:
            self.logger.error("Error getting service status from Centreon: %s", e)

        return alerts


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    host_url = os.environ.get("CENTREON_HOST_URL")
    api_token = os.environ.get("CENTREON_API_TOKEN")

    if host_url is None:
        raise ProviderException("CENTREON_HOST_URL is not set")

    config = ProviderConfig(
        description="Centreon Provider",
        authentication={
            "host_url": host_url,
            "api_token": api_token,
        },
    )

    provider = CentreonProvider(
        context_manager,
        provider_id="centreon",
        config=config,
    )

    provider._get_alerts()
