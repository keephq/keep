"""
VictoriametricsProvider is a class that allows to install webhooks and get alerts in Victoriametrics.
"""

import dataclasses
import datetime

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


class ResourceAlreadyExists(Exception):
    def __init__(self, *args):
        super().__init__(*args)


@pydantic.dataclasses.dataclass
class VictoriametricsProviderAuthConfig:
    """
    vmalert authentication configuration.
    """

    VMAlertHost: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "The hostname or IP address where VMAlert is running. This can be a local or remote server address.",
            "hint": "Example: 'localhost', '192.168.1.100', or 'vmalert.mydomain.com'",
            "config_sub_group": "host",
            "config_main_group": "address",
        },
        default=None,
    )

    VMAlertPort: int = dataclasses.field(
        metadata={
            "required": False,
            "description": "The port number on which VMAlert is listening. This should match the port configured in your VMAlert setup.",
            "hint": "Example: 8880 (if VMAlert is set to listen on port 8880), defaults to 8880",
            "config_sub_group": "host",
            "config_main_group": "address",
        },
        default=8880,
    )

    VMAlertURL: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "The full URL to the VMAlert instance. For example: http://vmalert.mydomain.com:8880",
            "config_sub_group": "url",
            "config_main_group": "address",
        },
        default=None,
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

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "low": AlertSeverity.LOW,
        "test": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "firing": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "suppressed": AlertStatus.SUPPRESSED,
        "pending": AlertStatus.PENDING,
    }

    def validate_scopes(self) -> dict[str, bool | str]:
        response = requests.get(self.vmalert_host)
        if response.status_code == 200:
            connected_to_client = True
            self.logger.info("Connected to client successfully")
        else:
            connected_to_client = (
                f"Error while connecting to client, {response.status_code}"
            )
            self.logger.error(
                "Error while connecting to client",
                extra={"status_code": response.status_code},
            )
        return {
            "connected": connected_to_client,
        }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        self._host = None
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Victoriametrics provider.
        """
        self.authentication_config = VictoriametricsProviderAuthConfig(
            **self.config.authentication
        )
        if (
            self.authentication_config.VMAlertURL is None
            and self.authentication_config.VMAlertHost is None
        ):
            raise Exception("VMAlertURL or VMAlertHost is required")

    @property
    def vmalert_host(self):
        # if not the first time, return the cached host
        if self._host:
            return self._host.rstrip("/")

        host = None

        if self.authentication_config.VMAlertURL is not None:
            host = self.authentication_config.VMAlertURL
        else:
            host = f"{self.authentication_config.VMAlertHost}:{self.authentication_config.VMAlertPort}"

        # if the user explicitly supplied a host with http/https, use it
        if host.startswith("http://") or host.startswith("https://"):
            self._host = host
            return host.rstrip("/")

        # otherwise, try to use https:
        try:
            url = f"https://{host}"
            requests.get(
                url,
                verify=False,
            )
            self.logger.debug("Using https")
            self._host = f"https://{host}"
            return self._host.rstrip("/")
        except requests.exceptions.SSLError:
            self.logger.debug("Using http")
            self._host = f"http://{host}"
            return self._host.rstrip("/")
        # should happen only if the user supplied invalid host, so just let validate_config fail
        except Exception:
            return host.rstrip("/")

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        alerts = []
        for alert in event["alerts"]:
            alerts.append(
                AlertDto(
                    name=alert["labels"]["alertname"],
                    fingerprint=alert["fingerprint"],
                    id=alert["fingerprint"],
                    description=alert["annotations"]["description"],
                    message=alert["annotations"]["summary"],
                    status=VictoriametricsProvider.STATUS_MAP[alert["status"]],
                    startedAt=alert["startsAt"],
                    url=alert["generatorURL"],
                    source=["victoriametrics"],
                    labels=alert["labels"],
                    lastReceived=datetime.datetime.now(
                        tz=datetime.timezone.utc
                    ).isoformat(),
                )
            )
        return alerts

    def _get_alerts(self) -> list[AlertDto]:
        response = requests.get(f"{self.vmalert_host}/api/v1/alerts")
        if response.status_code == 200:
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
                        severity=VictoriametricsProvider.STATUS_MAP[
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
        else:
            self.logger.error("Failed to get alerts", extra=response.json())
            raise Exception("Could not get alerts")

    def _query(self, query="", start="", end="", step="", queryType="", **kwargs: dict):
        if queryType == "query":
            response = requests.get(
                f"{self.vmalert_host}/api/v1/query",
                params={"query": query, "time": start},
            )
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(
                    "Failed to perform instant query", extra=response.json()
                )
                raise Exception("Could not perform instant query")

        elif queryType == "query_range":
            response = requests.get(
                f"{self.vmalert_host}/api/v1/query_range",
                params={"query": query, "start": start, "end": end, "step": step},
            )
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(
                    "Failed to perform range query", extra=response.json()
                )
                raise Exception("Could not range query")

        else:
            self.logger.error("Invalid query type")
            raise Exception("Invalid query type")
