"""
NagiosProvider pulls active host + service problems from a Nagios XI
deployment via its REST API.

Reference (Nagios XI REST API): https://assets.nagios.com/downloads/nagiosxi/docs/Nagios-XI-REST-API.pdf

Endpoints used:
  GET /nagiosxi/api/v1/objects/hoststatus    — host state per Nagios host
  GET /nagiosxi/api/v1/objects/servicestatus — service state per Nagios service

Status mapping (Nagios current_state values):
  Host: 0 UP, 1 DOWN, 2 UNREACHABLE
  Service: 0 OK, 1 WARNING, 2 CRITICAL, 3 UNKNOWN
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
class NagiosProviderAuthConfig:
    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI base URL (e.g. https://nagios.example.com).",
            "sensitive": False,
            "validation": "any_http_url",
        },
    )

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI API key (account → API access tab in the UI).",
            "sensitive": True,
        },
        default=None,
    )

    verify_ssl: bool = dataclasses.field(
        metadata={
            "required": False,
            "description": "Verify TLS certificates. Many Nagios installs use self-signed certs.",
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
            name="authenticated",
            description="API key is valid for the Nagios XI REST API",
        ),
    ]

    # Nagios host states (current_state on /objects/hoststatus).
    HOST_STATUS_MAP = {
        0: AlertStatus.RESOLVED,   # UP — no alert
        1: AlertStatus.FIRING,     # DOWN
        2: AlertStatus.FIRING,     # UNREACHABLE
    }
    HOST_SEVERITY_MAP = {
        0: AlertSeverity.INFO,
        1: AlertSeverity.CRITICAL,
        2: AlertSeverity.HIGH,
    }

    # Nagios service states (current_state on /objects/servicestatus).
    SERVICE_STATUS_MAP = {
        0: AlertStatus.RESOLVED,   # OK
        1: AlertStatus.FIRING,     # WARNING
        2: AlertStatus.FIRING,     # CRITICAL
        3: AlertStatus.FIRING,     # UNKNOWN — still surfaces, low-confidence
    }
    SERVICE_SEVERITY_MAP = {
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
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def __url(self, path: str) -> str:
        base = str(self.authentication_config.host_url).rstrip("/")
        return f"{base}/nagiosxi/api/v1/{path}"

    def __params(self, extra: dict | None = None) -> dict:
        params = {"apikey": self.authentication_config.api_key}
        if extra:
            params.update(extra)
        return params

    def __get(self, path: str, params: dict | None = None) -> dict:
        try:
            response = requests.get(
                self.__url(path),
                params=self.__params(params),
                verify=self.authentication_config.verify_ssl,
                timeout=30,
            )
        except requests.RequestException as e:
            raise ProviderException(f"Nagios request failed: {e}") from e
        if not response.ok:
            raise ProviderException(
                f"Nagios responded {response.status_code}: {response.text[:300]}"
            )
        try:
            return response.json()
        except ValueError as e:
            raise ProviderException(f"Nagios returned non-JSON: {e}") from e

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            self.__get("objects/hoststatus")
            return {"authenticated": True}
        except Exception as e:
            return {"authenticated": f"Error validating scopes: {e}"}

    @staticmethod
    def _to_iso(value) -> str:
        """Nagios timestamps come back as either ISO strings or numeric unix seconds.
        Normalize to ISO. If unparseable, return current UTC iso (safe default)."""
        if value in (None, "", 0, "0"):
            return datetime.datetime.utcnow().isoformat()
        try:
            if isinstance(value, (int, float)):
                return datetime.datetime.fromtimestamp(float(value)).isoformat()
            # Try int-as-string
            return datetime.datetime.fromtimestamp(float(value)).isoformat()
        except (ValueError, TypeError):
            return str(value)

    def _host_to_alert(self, row: dict) -> AlertDto | None:
        state = row.get("current_state")
        if state in (0, "0", None):
            # UP — not an alert
            return None
        state_int = int(state) if not isinstance(state, int) else state
        return AlertDto(
            id=f"nagios-host-{row.get('host_object_id') or row.get('host_name')}",
            name=f"Host {row.get('host_name', '?')}",
            description=row.get("output", "") or row.get("plugin_output", ""),
            severity=self.HOST_SEVERITY_MAP.get(state_int, AlertSeverity.INFO),
            status=self.HOST_STATUS_MAP.get(state_int, AlertStatus.FIRING),
            lastReceived=self._to_iso(row.get("last_check") or row.get("last_state_change")),
            source=["nagios"],
            host_name=row.get("host_name"),
            host_state=state_int,
        )

    def _service_to_alert(self, row: dict) -> AlertDto | None:
        state = row.get("current_state")
        if state in (0, "0", None):
            # OK — not an alert
            return None
        state_int = int(state) if not isinstance(state, int) else state
        host = row.get("host_name", "?")
        svc = row.get("service_description") or row.get("name", "?")
        return AlertDto(
            id=f"nagios-svc-{row.get('service_object_id') or f'{host}-{svc}'}",
            name=f"Service {svc} on {host}",
            description=row.get("output", "") or row.get("plugin_output", ""),
            severity=self.SERVICE_SEVERITY_MAP.get(state_int, AlertSeverity.INFO),
            status=self.SERVICE_STATUS_MAP.get(state_int, AlertStatus.FIRING),
            lastReceived=self._to_iso(row.get("last_check") or row.get("last_state_change")),
            source=["nagios"],
            host_name=host,
            service_description=svc,
            service_state=state_int,
        )

    def _get_alerts(self) -> list[AlertDto]:
        alerts: list[AlertDto] = []

        # Host status
        try:
            payload = self.__get("objects/hoststatus")
            hosts = self._unwrap_records(payload, "hoststatus")
            for row in hosts:
                a = self._host_to_alert(row)
                if a:
                    alerts.append(a)
        except Exception as e:
            self.logger.error("Nagios: host status fetch failed: %s", e)

        # Service status
        try:
            payload = self.__get("objects/servicestatus")
            services = self._unwrap_records(payload, "servicestatus")
            for row in services:
                a = self._service_to_alert(row)
                if a:
                    alerts.append(a)
        except Exception as e:
            self.logger.error("Nagios: service status fetch failed: %s", e)

        return alerts

    @staticmethod
    def _unwrap_records(payload: dict, key: str) -> list[dict]:
        """Nagios XI sometimes wraps results in {"records": N, "<key>": [...]} and
        sometimes returns a bare list. Handle both shapes."""
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []
        candidate = payload.get(key)
        if isinstance(candidate, list):
            return candidate
        # Common Nagios XI shape: {"recordcount": ..., "hoststatus": {"host_status": [...]}}
        nested = payload.get(key, {})
        if isinstance(nested, dict):
            for v in nested.values():
                if isinstance(v, list):
                    return v
        return []


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")

    host_url = os.environ.get("NAGIOS_HOST_URL")
    api_key = os.environ.get("NAGIOS_API_KEY")

    if not host_url or not api_key:
        raise ProviderException(
            "Set NAGIOS_HOST_URL and NAGIOS_API_KEY to smoke-test."
        )

    config = ProviderConfig(
        description="Nagios Provider",
        authentication={
            "host_url": host_url,
            "api_key": api_key,
            "verify_ssl": os.environ.get("NAGIOS_VERIFY_SSL", "true").lower() != "false",
        },
    )
    provider = NagiosProvider(context_manager, provider_id="nagios", config=config)
    alerts = provider._get_alerts()
    print(f"Fetched {len(alerts)} Nagios alert(s)")
    for a in alerts[:5]:
        print(" -", a)
