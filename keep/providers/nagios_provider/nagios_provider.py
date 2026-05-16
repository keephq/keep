"""
Nagios XI provider for polling host and service status through the REST API.
"""

import dataclasses
import datetime
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
    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI Host URL",
            "hint": "https://nagios.example.com",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI API Key",
            "sensitive": True,
        }
    )
    verify: bool = dataclasses.field(
        metadata={
            "required": False,
            "description": "Verify SSL certificates",
            "hint": "Set to false to allow self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )
    include_hosts: bool = dataclasses.field(
        metadata={
            "required": False,
            "description": "Poll Nagios XI host status objects",
            "sensitive": False,
        },
        default=True,
    )
    include_services: bool = dataclasses.field(
        metadata={
            "required": False,
            "description": "Poll Nagios XI service status objects",
            "sensitive": False,
        },
        default=True,
    )


class NagiosProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_status",
            description="Read Nagios XI host and service status",
            mandatory=True,
        )
    ]
    PROVIDER_ICON = "nagios-icon.png"
    FINGERPRINT_FIELDS = ["fingerprint"]

    HOST_STATE_MAP = {
        0: (AlertStatus.RESOLVED, AlertSeverity.INFO),
        1: (AlertStatus.FIRING, AlertSeverity.CRITICAL),
        2: (AlertStatus.FIRING, AlertSeverity.WARNING),
    }
    SERVICE_STATE_MAP = {
        0: (AlertStatus.RESOLVED, AlertSeverity.INFO),
        1: (AlertStatus.FIRING, AlertSeverity.WARNING),
        2: (AlertStatus.FIRING, AlertSeverity.CRITICAL),
        3: (AlertStatus.FIRING, AlertSeverity.INFO),
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
        try:
            self._request("objects/hoststatus", {"records": 1})
            return {"read_status": True}
        except Exception as e:
            return {"read_status": str(e)}

    def _api_url(self, path: str) -> str:
        base_url = str(self.authentication_config.host_url).rstrip("/")
        api_base = (
            f"{base_url}/api/v1/"
            if base_url.endswith("/nagiosxi")
            else f"{base_url}/nagiosxi/api/v1/"
        )
        return urljoin(api_base, path)

    def _request(self, path: str, params: dict | None = None) -> dict:
        request_params = {"apikey": self.authentication_config.api_key}
        if params:
            request_params.update(params)

        response = requests.get(
            self._api_url(path),
            params=request_params,
            verify=self.authentication_config.verify,
            timeout=30,
        )
        if not response.ok:
            raise ProviderException(
                f"Nagios XI API request failed: {response.status_code} {response.text}"
            )
        return response.json()

    @staticmethod
    def _first_present(*values):
        for value in values:
            if value is not None:
                return value
        return None

    @staticmethod
    def _coerce_state(value) -> int:
        if value is None:
            return 3
        try:
            return int(value)
        except (TypeError, ValueError):
            normalized = str(value).strip().upper()
            return {
                "UP": 0,
                "OK": 0,
                "DOWN": 1,
                "WARNING": 1,
                "CRITICAL": 2,
                "UNREACHABLE": 2,
                "UNKNOWN": 3,
            }.get(normalized, 3)

    @staticmethod
    def _timestamp(value) -> str:
        if value in (None, ""):
            return datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        try:
            return datetime.datetime.fromtimestamp(
                int(float(value)), tz=datetime.timezone.utc
            ).isoformat()
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _extract_items(payload: dict, key: str) -> list[dict]:
        value = payload.get(key, [])
        if isinstance(value, dict):
            return list(value.values())
        if isinstance(value, list):
            return value
        return []

    @classmethod
    def _format_host(cls, host: dict) -> AlertDto:
        state = cls._coerce_state(
            cls._first_present(
                host.get("current_state"),
                host.get("state"),
                host.get("status"),
                host.get("host_state"),
            )
        )
        status, severity = cls.HOST_STATE_MAP.get(
            state, (AlertStatus.FIRING, AlertSeverity.INFO)
        )
        host_name = (
            host.get("host_name") or host.get("name") or host.get("display_name")
        )
        alert_id = f"nagios-host-{host.get('hoststatus_id') or host_name}"
        acknowledged = str(host.get("problem_acknowledged", "0")) == "1"
        if acknowledged and status == AlertStatus.FIRING:
            status = AlertStatus.ACKNOWLEDGED

        return AlertDto(
            id=alert_id,
            name=f"Nagios host {host_name}",
            status=status,
            severity=severity,
            lastReceived=cls._timestamp(host.get("last_check")),
            description=host.get("output") or host.get("status_text"),
            service=host_name,
            source=["nagios"],
            fingerprint=alert_id,
            labels={
                "nagios_object_type": "host",
                "host_name": host_name,
                "state": str(state),
            },
        )

    @classmethod
    def _format_service(cls, service: dict) -> AlertDto:
        state = cls._coerce_state(
            cls._first_present(
                service.get("current_state"),
                service.get("state"),
                service.get("status"),
                service.get("service_state"),
            )
        )
        status, severity = cls.SERVICE_STATE_MAP.get(
            state, (AlertStatus.FIRING, AlertSeverity.INFO)
        )
        host_name = service.get("host_name") or service.get("host")
        service_name = (
            service.get("service_description")
            or service.get("display_name")
            or service.get("name")
        )
        service_id = service.get("servicestatus_id")
        alert_id = (
            f"nagios-service-{service_id}"
            if service_id
            else f"nagios-service-{host_name}-{service_name}"
        )
        acknowledged = str(service.get("problem_acknowledged", "0")) == "1"
        if acknowledged and status == AlertStatus.FIRING:
            status = AlertStatus.ACKNOWLEDGED

        return AlertDto(
            id=alert_id,
            name=f"Nagios service {host_name}/{service_name}",
            status=status,
            severity=severity,
            lastReceived=cls._timestamp(service.get("last_check")),
            description=service.get("output") or service.get("status_text"),
            service=service_name,
            source=["nagios"],
            fingerprint=alert_id,
            labels={
                "nagios_object_type": "service",
                "host_name": host_name,
                "service_description": service_name,
                "state": str(state),
            },
        )

    def _get_alerts(self) -> list[AlertDto]:
        alerts = []

        if self.authentication_config.include_hosts:
            try:
                host_payload = self._request("objects/hoststatus")
                alerts.extend(
                    self._format_host(host)
                    for host in self._extract_items(host_payload, "hoststatus")
                )
            except Exception as e:
                self.logger.exception("Failed to fetch Nagios XI host status")
                raise ProviderException(
                    f"Failed to fetch Nagios XI host status: {e}"
                ) from e

        if self.authentication_config.include_services:
            try:
                service_payload = self._request("objects/servicestatus")
                alerts.extend(
                    self._format_service(service)
                    for service in self._extract_items(service_payload, "servicestatus")
                )
            except Exception as e:
                self.logger.exception("Failed to fetch Nagios XI service status")
                raise ProviderException(
                    f"Failed to fetch Nagios XI service status: {e}"
                ) from e

        return alerts
