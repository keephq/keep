"""
VictoriametricsProvider is a class that allows to install webhooks and get alerts in Victoriametrics.
"""

import dataclasses
import datetime

import pydantic
import requests
from pydantic import AnyHttpUrl

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.validation.fields import UrlPort


class ResourceAlreadyExists(Exception):
    def __init__(self, *args):
        super().__init__(*args)


@pydantic.dataclasses.dataclass
class VictoriametricsProviderAuthConfig:
    """
    VictoriaMetrics authentication configuration.
    Both VMAlert and VM Backend are optional, but at least one must be configured.
    """

    # VMAlert Configuration
    VMAlertHost: AnyHttpUrl | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "The hostname or IP address where VMAlert is running",
            "hint": "Example: 'http://localhost', 'http://192.168.1.100'",
            "validation": "any_http_url",
            "config_sub_group": "vmalert",
            "config_main_group": "address",
        },
        default=None,
    )

    VMAlertPort: UrlPort = dataclasses.field(
        metadata={
            "required": False,
            "description": "The port number on which VMAlert is listening",
            "hint": "Example: 8880",
            "validation": "port",
            "config_sub_group": "vmalert",
            "config_main_group": "address",
        },
        default=8880,
    )

    VMAlertURL: AnyHttpUrl | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "The full URL to the VMAlert instance. Alternative to Host/Port",
            "hint": "Example: 'http://vmalert.mydomain.com:8880'",
            "validation": "any_http_url",
            "config_sub_group": "vmalert",
            "config_main_group": "address",
        },
        default=None,
    )

    # VM Backend Configuration
    VMBackendHost: AnyHttpUrl | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "The hostname or IP address where VictoriaMetrics backend is running",
            "hint": "Example: 'http://localhost', 'http://192.168.1.100'",
            "validation": "any_http_url",
            "config_sub_group": "vmbackend",
            "config_main_group": "address",
        },
        default=None,
    )

    VMBackendPort: UrlPort = dataclasses.field(
        metadata={
            "required": False,
            "description": "The port number on which VictoriaMetrics backend is listening",
            "hint": "Example: 8428",
            "validation": "port",
            "config_sub_group": "vmbackend",
            "config_main_group": "address",
        },
        default=8428,
    )

    VMBackendURL: AnyHttpUrl | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "The full URL to the VictoriaMetrics backend. Alternative to Host/Port",
            "hint": "Example: 'http://vm.mydomain.com:8428'",
            "validation": "any_http_url",
            "config_sub_group": "vmbackend",
            "config_main_group": "address",
        },
        default=None,
    )

    # Auth Configuration
    BasicAuthUsername: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "Username for basic authentication",
            "config_sub_group": "auth",
            "config_main_group": "authentication",
        },
        default=None,
    )

    BasicAuthPassword: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "Password for basic authentication",
            "config_sub_group": "auth",
            "config_main_group": "authentication",
            "sensitive": True,
        },
        default=None,
    )

    # Auth Configuration
    BasicAuthUsername: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "Username for basic authentication",
            "config_sub_group": "auth",
            "config_main_group": "authentication",
        },
        default=None,
    )

    BasicAuthPassword: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "Password for basic authentication",
            "config_sub_group": "auth",
            "config_main_group": "authentication",
            "sensitive": True,
        },
        default=None,
    )

    SkipValidation: bool = dataclasses.field(
        metadata={
            "required": False,
            "description": "Enter 'true' to skip validation of authentication",
            "config_sub_group": "validation",
            "config_main_group": "validation",
        },
        default=False,
    )


class VictoriametricsProvider(BaseProvider):
    """Install Webhooks and receive alerts from Victoriametrics."""

    webhook_description = "This provider takes advantage of configurable webhooks available with Prometheus Alertmanager. Use the following template to configure AlertManager:"
    webhook_template = """route:
  receiver: "keep"
  group_by: ['alertname']
  group_wait:      15s
  group_interval:  15s
  repeat_interval: 1m
  continue: true

receivers:
- name: "keep"
  webhook_configs:
  - url: '{keep_webhook_api_url}'
    send_resolved: true
    http_config:
      basic_auth:
        username: api_key
        password: {api_key}
"""

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connected",
            description="The user can connect to the client",
            mandatory=True,
            alias="Connect to the client",
        ),
    ]
    PROVIDER_CATEGORY = ["Monitoring"]
    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "low": AlertSeverity.LOW,
        "test": AlertSeverity.INFO,
        "info": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "firing": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "suppressed": AlertStatus.SUPPRESSED,
        "pending": AlertStatus.PENDING,
    }

    def _get_auth(self):
        """Get basic auth tuple if credentials are configured."""
        if (
            self.authentication_config.BasicAuthUsername
            and self.authentication_config.BasicAuthPassword
        ):
            return (
                self.authentication_config.BasicAuthUsername,
                self.authentication_config.BasicAuthPassword,
            )
        return None

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate scopes by checking configured services."""
        results = []
        if self.authentication_config.SkipValidation == True:
            return {"connected": True}

        if self.vmalert_enabled:
            vmalert_response = requests.get(self.vmalert_host, auth=self._get_auth())
            if vmalert_response.status_code == 200:
                self.logger.info("Connected to VMAlert successfully")
            else:
                results.append(f"VMAlert error: {vmalert_response.status_code}")
                self.logger.error(
                    "Error connecting to VMAlert",
                    extra={"status_code": vmalert_response.status_code},
                )

        if self.vmbackend_enabled:
            vmbackend_response = requests.get(
                self.vmbackend_host, auth=self._get_auth()
            )
            if vmbackend_response.status_code == 200:
                self.logger.info("Connected to VM Backend successfully")
            else:
                results.append(f"VM Backend error: {vmbackend_response.status_code}")
                self.logger.error(
                    "Error connecting to VM Backend",
                    extra={"status_code": vmbackend_response.status_code},
                )

        return {
            "connected": True if not results else ", ".join(results),
        }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        self._vmalert_host = None
        self._vmbackend_host = None
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Victoriametrics provider.
        At least one service (VMAlert or VM Backend) must be configured.
        """
        self.authentication_config = VictoriametricsProviderAuthConfig(
            **self.config.authentication
        )

        vmalert_configured = (
            self.authentication_config.VMAlertURL is not None
            or self.authentication_config.VMAlertHost is not None
        )
        vmbackend_configured = (
            self.authentication_config.VMBackendURL is not None
            or self.authentication_config.VMBackendHost is not None
        )

        if not vmalert_configured and not vmbackend_configured:
            raise Exception("At least one of VMAlert or VM Backend must be configured")

    @property
    def vmalert_enabled(self) -> bool:
        """Check if VMAlert is configured."""
        return (
            self.authentication_config.VMAlertURL is not None
            or self.authentication_config.VMAlertHost is not None
        )

    @property
    def vmbackend_enabled(self) -> bool:
        """Check if VM Backend is configured."""
        return (
            self.authentication_config.VMBackendURL is not None
            or self.authentication_config.VMBackendHost is not None
        )

    @property
    def vmalert_host(self):
        """Get the VMAlert host URL."""
        # Return cached host if available
        if self._vmalert_host:
            return self._vmalert_host.rstrip("/")

        # Skip if VMAlert is not configured
        if not self.vmalert_enabled:
            return None

        host = None
        if self.authentication_config.VMAlertURL is not None:
            host = self.authentication_config.VMAlertURL
        else:
            host = f"{self.authentication_config.VMAlertHost}:{self.authentication_config.VMAlertPort}"

        # If HTTP/HTTPS is explicitly specified, use it
        if host.startswith("http://") or host.startswith("https://"):
            self._vmalert_host = host
            return host.rstrip("/")

        # Try HTTPS first, fall back to HTTP
        try:
            url = f"https://{host}"
            requests.get(
                url,
                verify=False,
                auth=self._get_auth(),
            )
            self.logger.debug("Using HTTPS for VMAlert")
            self._vmalert_host = f"https://{host}"
            return self._vmalert_host.rstrip("/")
        except requests.exceptions.SSLError:
            self.logger.debug("Using HTTP for VMAlert")
            self._vmalert_host = f"http://{host}"
            return self._vmalert_host.rstrip("/")
        except Exception:
            return host.rstrip("/")

    @property
    def vmbackend_host(self):
        """Get the VM Backend host URL."""
        # Return cached host if available
        if self._vmbackend_host:
            return self._vmbackend_host.rstrip("/")

        # Skip if VM Backend is not configured
        if not self.vmbackend_enabled:
            return None

        host = None
        if self.authentication_config.VMBackendURL is not None:
            host = self.authentication_config.VMBackendURL
        else:
            host = f"{self.authentication_config.VMBackendHost}:{self.authentication_config.VMBackendPort}"

        # If HTTP/HTTPS is explicitly specified, use it
        if host.startswith("http://") or host.startswith("https://"):
            self._vmbackend_host = host
            return host.rstrip("/")

        # Try HTTPS first, fall back to HTTP
        try:
            url = f"https://{host}"
            requests.get(
                url,
                verify=False,
                auth=self._get_auth(),
            )
            self.logger.debug("Using HTTPS for VM Backend")
            self._vmbackend_host = f"https://{host}"
            return self._vmbackend_host.rstrip("/")
        except requests.exceptions.SSLError:
            self.logger.debug("Using HTTP for VM Backend")
            self._vmbackend_host = f"http://{host}"
            return self._vmbackend_host.rstrip("/")
        except Exception:
            return host.rstrip("/")

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        alerts = []
        for alert in event["alerts"]:
            annotations = alert.get("annotations", {})
            labels = alert.get("labels", {})
            fingerprint = alert.get("fingerprint")
            alerts.append(
                AlertDto(
                    name=labels.get("alertname", ""),
                    fingerprint=fingerprint,
                    id=fingerprint,
                    description=annotations.get("description"),
                    message=annotations.get("summary"),
                    status=VictoriametricsProvider.STATUS_MAP.get(
                        alert["status"], AlertStatus.FIRING
                    ),
                    severity=VictoriametricsProvider.SEVERITIES_MAP.get(
                        labels.get("severity", "low"), AlertSeverity.LOW
                    ),
                    startedAt=alert.get("startsAt"),
                    url=alert.get("generatorURL"),
                    source=["victoriametrics"],
                    labels=labels,
                    lastReceived=datetime.datetime.now(
                        tz=datetime.timezone.utc
                    ).isoformat(),
                )
            )
        return alerts

    def _get_alerts(self) -> list[AlertDto]:
        """Get alerts from VMAlert."""
        if not self.vmalert_enabled:
            raise Exception("VMAlert is not configured")

        response = requests.get(
            f"{self.vmalert_host}/api/v1/alerts", auth=self._get_auth()
        )
        try:
            response.raise_for_status()
            alerts = []
            response = response.json()
            for alert in response["data"]["alerts"]:
                alerts.append(
                    AlertDto(
                        name=alert["name"],
                        id=alert["id"],
                        description=alert["annotations"]["description"],
                        message=alert["annotations"]["summary"],
                        status=VictoriametricsProvider.STATUS_MAP[alert["state"]],
                        severity=VictoriametricsProvider.SEVERITIES_MAP[
                            alert["labels"]["severity"]
                        ],
                        startedAt=alert["activeAt"],
                        url=alert["source"],
                        source=["victoriametrics"],
                        event_id=alert["rule_id"],
                        labels=alert["labels"],
                    )
                )
            return alerts
        except Exception as e:
            self.logger.exception("Failed to get alerts")
            raise e

    def _query(self, query="", start="", end="", step="", queryType="", **kwargs: dict):
        """Query metrics from VM Backend."""
        if not self.vmbackend_enabled:
            raise Exception("VM Backend is not configured")

        auth = self._get_auth()
        base_url = self.vmbackend_host

        if queryType == "query":
            response = requests.get(
                f"{base_url}/api/v1/query",
                params={"query": query, "time": start},
                auth=auth,
            )
            try:
                response.raise_for_status()
                results = response.json()
                return results.get("data", {}).get("result", [])
            except Exception as e:
                self.logger.exception("Failed to perform instant query")
                raise e

        elif queryType == "query_range":
            response = requests.get(
                f"{base_url}/api/v1/query_range",
                params={"query": query, "start": start, "end": end, "step": step},
                auth=auth,
            )
            if response.status_code == 200:
                results = response.json()
                # return only the results
                return response.json()
            else:
                self.logger.error(
                    "Failed to perform range query", extra=response.json()
                )
                raise Exception("Could not range query")

        else:
            self.logger.error("Invalid query type")
            raise Exception("Invalid query type")


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    from keep.providers.providers_factory import ProvidersFactory

    vmalerthost = os.environ.get("VMALERT_HOST") or "http://localhost:8880"
    user = os.environ.get("VMALERT_USER") or "admin"
    password = os.environ.get("VMALERT_PASSWORD") or "secret"
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    config = {
        "authentication": {
            "VMAlertURL": vmalerthost,
            "BasicAuthUsername": user,
            "BasicAuthPassword": password,
        },
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="vm-keephq",
        provider_type="victoriametrics",
        provider_config=config,
    )
    alerts = provider.get_alerts()

    vmbackendhost = os.environ.get("VMBACKEND_HOST") or "http://localhost:8428"
    user = os.environ.get("VMBACKEND_USER") or "admin"
    password = os.environ.get("VMBACKEND_PASSWORD") or "secret"

    config = {
        "authentication": {
            "VMBackendURL": vmbackendhost,
            "BasicAuthUsername": user,
            "BasicAuthPassword": password,
        },
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="vm-keephq",
        provider_type="victoriametrics",
        provider_config=config,
    )
    query = provider.query(
        query="avg(rate(process_cpu_seconds_total))", queryType="query"
    )

    print(alerts)
