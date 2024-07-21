"""
VictoriametricsProvider is a class that allows to install webhooks and get alerts in Victoriametrics.
"""

import dataclasses
import datetime
from typing import Optional

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

    VMAlertHost: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "The hostname or IP address where VMAlert is running. This can be a local or remote server address.",
            "hint": "Example: 'localhost', '192.168.1.100', or 'vmalert.mydomain.com'",
        },
    )

    VMAlertPort: int = dataclasses.field(
        metadata={
            "required": True,
            "description": "The port number on which VMAlert is listening. This should match the port configured in your VMAlert setup.",
            "hint": "Example: 8880 (if VMAlert is set to listen on port 8880)",
        },
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
        "test": AlertSeverity.INFO
    }

    STATUS_MAP = {
        "firing": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "suppressed": AlertStatus.SUPPRESSED,
        "pending": AlertStatus.PENDING,
    }

    def validate_scopes(self) -> dict[str, bool | str]:
        response = requests.get(f"{self.vmalert_host}:{self.authentication_config.VMAlertPort}")
        if response.status_code == 200:
            connected_to_client = True
            self.logger.info("Connected to client successfully")
        else:
            connected_to_client = f"Error while connecting to client, {response.status_code}"
            self.logger.error("Error while connecting to client", extra={"status_code": response.status_code})
        return {
            'connected': connected_to_client,
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

    @property
    def vmalert_host(self):
        # if not the first time, return the cached host
        if self._host:
            return self._host.rstrip("/")

        # if the user explicitly supplied a host with http/https, use it
        if self.authentication_config.VMAlertHost.startswith(
                "http://"
        ) or self.authentication_config.VMAlertHost.startswith("https://"):
            self._host = self.authentication_config.VMAlertHost
            return self.authentication_config.VMAlertHost.rstrip("/")

        # otherwise, try to use https:
        try:
            requests.get(
                f"https://{self.authentication_config.VMAlertHost}:{self.authentication_config.VMAlertPort}",
                verify=False,
            )
            self.logger.debug("Using https")
            self._host = f"https://{self.authentication_config.VMAlertHost}"
            return self._host.rstrip("/")
        except requests.exceptions.SSLError:
            self.logger.debug("Using http")
            self._host = f"http://{self.authentication_config.VMAlertHost}"
            return self._host.rstrip("/")
        # should happen only if the user supplied invalid host, so just let validate_config fail
        except Exception:
            return self.authentication_config.VMAlertHost.rstrip("/")

    @staticmethod
    def _format_alert(
            event: dict, provider_instance: Optional["BaseProvider"] = None
    ) -> AlertDto | list[AlertDto]:
        alerts = []
        for alert in event["alerts"]:
            alerts.append(
                AlertDto(
                    name=alert["labels"]["alertname"],
                    fingerprint=alert['fingerprint'],
                    id=alert['fingerprint'],
                    description=alert["annotations"]['description'],
                    message=alert["annotations"]['summary'],
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
        response = requests.get(f"{self.vmalert_host}:{self.authentication_config.VMAlertPort}/api/v1/alerts")
        if response.status_code == 200:
            alerts = []
            response = response.json()
            for alert in response['data']['alerts']:
                alerts.append(
                    AlertDto(
                        name=alert["name"],
                        id=alert['id'],
                        description=alert["annotations"]['description'],
                        message=alert["annotations"]['summary'],
                        status=VictoriametricsProvider.STATUS_MAP[alert["state"]],
                        severity=VictoriametricsProvider.STATUS_MAP[alert["labels"]["severity"]],
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
