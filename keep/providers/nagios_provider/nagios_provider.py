"""
Nagios XI provider.
"""

import dataclasses
import datetime
from typing import Any
from urllib.parse import urljoin

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    NagiosProviderAuthConfig holds Nagios XI API authentication details.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI Host URL",
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


class NagiosProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(name="authenticated", description="User is authenticated"),
    ]

    HOST_STATE_LABELS = {
        0: "UP",
        1: "WARNING",
        2: "DOWN",
        3: "UNKNOWN",
    }
    SERVICE_STATE_LABELS = {
        0: "OK",
        1: "WARNING",
        2: "CRITICAL",
        3: "UNKNOWN",
    }
    STATUS_MAP = {
        0: AlertStatus.RESOLVED,
        1: AlertStatus.FIRING,
        2: AlertStatus.FIRING,
        3: AlertStatus.FIRING,
    }
    SEVERITY_MAP = {
        0: AlertSeverity.LOW,
        1: AlertSeverity.WARNING,
        2: AlertSeverity.CRITICAL,
        3: AlertSeverity.INFO,
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
        self._base_url = self.__normalize_base_url(
            str(self.authentication_config.host_url)
        )

    @staticmethod
    def __normalize_base_url(host_url: str) -> str:
        host_url = host_url.rstrip("/")
        if host_url.endswith("/api/v1"):
            return host_url
        if host_url.endswith("/nagiosxi"):
            return f"{host_url}/api/v1"
        return urljoin(f"{host_url}/", "nagiosxi/api/v1").rstrip("/")

    def __get_url(self, path: str) -> str:
        return f"{self._base_url}/{path.lstrip('/')}"

    def __get_params(self) -> dict[str, str]:
        return {"apikey": self.authentication_config.api_key}

    @staticmethod
    def __coerce_int(value: Any, default: int = 3) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def __coerce_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}
        return False

    @staticmethod
    def __coerce_timestamp(value: Any) -> str:
        timestamp = NagiosProvider.__coerce_int(value, 0)
        if timestamp > 0:
            return datetime.datetime.fromtimestamp(
                timestamp, tz=datetime.timezone.utc
            ).isoformat()
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    @staticmethod
    def __extract_objects(payload: Any, key: str) -> list[dict]:
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []

        objects = payload.get(key) or payload.get("record") or payload.get("records")
        if objects is None and {"host_name", "service_description"} & set(payload):
            objects = payload
        if isinstance(objects, list):
            return [item for item in objects if isinstance(item, dict)]
        if isinstance(objects, dict):
            return [objects]
        return []

    def __request_objects(self, path: str, key: str) -> list[dict]:
        response = requests.get(
            self.__get_url(path),
            params=self.__get_params(),
            timeout=30,
        )
        if not response.ok:
            raise ProviderException(
                f"Failed to get Nagios XI {key}: {response.status_code} {response.text}"
            )
        return self.__extract_objects(response.json(), key)

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate Nagios XI API connectivity and API key authentication.
        """
        try:
            self.__request_objects("objects/hoststatus", "hoststatus")
            return {"authenticated": True}
        except Exception as e:
            return {"authenticated": f"Error validating scopes: {e}"}

    def __format_host_alert(self, host: dict) -> AlertDto:
        state = self.__coerce_int(host.get("current_state"))
        hostname = host.get("host_name") or host.get("name") or host.get("host_id")
        acknowledged = self.__coerce_bool(host.get("problem_has_been_acknowledged"))
        state_label = self.HOST_STATE_LABELS.get(state, "UNKNOWN")
        status = self.STATUS_MAP.get(state, AlertStatus.FIRING)
        if acknowledged and status == AlertStatus.FIRING:
            status = AlertStatus.ACKNOWLEDGED

        return AlertDto(
            id=f"nagios-host-{host.get('host_id') or hostname}",
            name=f"Nagios host {hostname} is {state_label}",
            description=host.get("plugin_output") or host.get("status_text") or "",
            status=status,
            severity=self.SEVERITY_MAP.get(state, AlertSeverity.INFO),
            lastReceived=self.__coerce_timestamp(host.get("last_check")),
            source=["nagios"],
            service=str(hostname) if hostname else None,
            labels={
                "nagios_object_type": "host",
                "nagios_host_name": str(hostname) if hostname else "",
                "nagios_state": state_label,
            },
            acknowledged=acknowledged,
            url=host.get("status_url") or None,
        )

    def __format_service_alert(self, service: dict) -> AlertDto:
        state = self.__coerce_int(service.get("current_state"))
        hostname = service.get("host_name") or service.get("host_id")
        service_name = (
            service.get("service_description")
            or service.get("display_name")
            or service.get("name")
            or service.get("service_id")
        )
        acknowledged = self.__coerce_bool(service.get("problem_has_been_acknowledged"))
        state_label = self.SERVICE_STATE_LABELS.get(state, "UNKNOWN")
        status = self.STATUS_MAP.get(state, AlertStatus.FIRING)
        if acknowledged and status == AlertStatus.FIRING:
            status = AlertStatus.ACKNOWLEDGED

        return AlertDto(
            id=f"nagios-service-{service.get('service_id') or hostname}-{service_name}",
            name=f"Nagios service {service_name} on {hostname} is {state_label}",
            description=service.get("plugin_output")
            or service.get("status_text")
            or "",
            status=status,
            severity=self.SEVERITY_MAP.get(state, AlertSeverity.INFO),
            lastReceived=self.__coerce_timestamp(service.get("last_check")),
            source=["nagios"],
            service=str(service_name) if service_name else None,
            labels={
                "nagios_object_type": "service",
                "nagios_host_name": str(hostname) if hostname else "",
                "nagios_service_description": str(service_name) if service_name else "",
                "nagios_state": state_label,
            },
            acknowledged=acknowledged,
            url=service.get("status_url") or None,
        )

    def __get_host_status(self) -> list[AlertDto]:
        try:
            hosts = self.__request_objects("objects/hoststatus", "hoststatus")
            return [self.__format_host_alert(host) for host in hosts]
        except Exception as e:
            self.logger.error("Error getting host status from Nagios XI: %s", e)
            raise ProviderException(f"Error getting host status from Nagios XI: {e}")

    def __get_service_status(self) -> list[AlertDto]:
        try:
            services = self.__request_objects("objects/servicestatus", "servicestatus")
            return [self.__format_service_alert(service) for service in services]
        except Exception as e:
            self.logger.error("Error getting service status from Nagios XI: %s", e)
            raise ProviderException(f"Error getting service status from Nagios XI: {e}")

    def _get_alerts(self) -> list[AlertDto]:
        alerts = []
        try:
            self.logger.info("Collecting alerts (host status) from Nagios XI")
            alerts.extend(self.__get_host_status())
        except Exception as e:
            self.logger.error("Error getting host status from Nagios XI: %s", e)

        try:
            self.logger.info("Collecting alerts (service status) from Nagios XI")
            alerts.extend(self.__get_service_status())
        except Exception as e:
            self.logger.error("Error getting service status from Nagios XI: %s", e)

        return alerts
