"""
AlertmanagerProvider integrates Keep with Prometheus Alertmanager.
Supports pulling active alerts from the Alertmanager REST API (v2) and
receiving real-time webhook notifications when alerts fire or resolve.
"""

import dataclasses
import datetime
from typing import List, Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class AlertmanagerProviderAuthConfig:
    """
    AlertmanagerProviderAuthConfig holds connection details for Prometheus Alertmanager.
    """

    alertmanager_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Alertmanager base URL (e.g. http://alertmanager:9093)",
            "sensitive": False,
            "hint": "URL of your Alertmanager instance, e.g. http://localhost:9093",
        },
    )

    username: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Basic auth username (if Alertmanager is protected)",
            "sensitive": False,
        },
    )

    password: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Basic auth password (if Alertmanager is protected)",
            "sensitive": True,
        },
    )

    bearer_token: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Bearer token for authentication (alternative to basic auth)",
            "sensitive": True,
        },
    )


class AlertmanagerProvider(BaseProvider):
    """Pull active alerts from Prometheus Alertmanager and receive webhook notifications."""

    PROVIDER_DISPLAY_NAME = "Alertmanager"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read active alerts from Alertmanager API",
            mandatory=True,
        ),
    ]

    # Alertmanager status → Keep AlertStatus
    STATUS_MAP = {
        "firing": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "suppressed": AlertStatus.ACKNOWLEDGED,
        "unprocessed": AlertStatus.PENDING,
        "active": AlertStatus.FIRING,
    }

    # Alertmanager severity label → Keep AlertSeverity
    SEVERITY_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
        "none": AlertSeverity.INFO,
    }

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send Alertmanager alerts to Keep, configure a webhook receiver in Alertmanager:

1. Edit your `alertmanager.yml` configuration file.
2. Add a **receiver** that posts to Keep's webhook endpoint:

```yaml
receivers:
  - name: keep
    webhook_configs:
      - url: '{keep_webhook_api_url}'
        http_config:
          authorization:
            credentials: '{api_key}'
        send_resolved: true
```

3. Add a **route** to direct alerts to the Keep receiver:

```yaml
route:
  receiver: keep
  # Or route selectively:
  routes:
    - match:
        severity: critical
      receiver: keep
```

4. Reload Alertmanager: `curl -X POST http://alertmanager:9093/-/reload`
"""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AlertmanagerProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _get_headers(self) -> dict:
        headers = {"Accept": "application/json"}
        if self.authentication_config.bearer_token:
            headers["Authorization"] = f"Bearer {self.authentication_config.bearer_token}"
        return headers

    def _get_auth(self):
        if (
            self.authentication_config.username
            and self.authentication_config.password
        ):
            return (
                self.authentication_config.username,
                self.authentication_config.password,
            )
        return None

    def _base_url(self) -> str:
        return self.authentication_config.alertmanager_url.rstrip("/")

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            response = requests.get(
                f"{self._base_url()}/api/v2/alerts",
                headers=self._get_headers(),
                auth=self._get_auth(),
                timeout=10,
            )
            if response.status_code == 200:
                return {"read_alerts": True}
            return {
                "read_alerts": f"HTTP {response.status_code}: {response.text[:200]}"
            }
        except Exception as e:
            self.logger.error("Error validating Alertmanager scopes: %s", e)
            return {"read_alerts": str(e)}

    def _get_alerts(self) -> List[AlertDto]:
        alerts = []
        try:
            self.logger.info("Pulling active alerts from Alertmanager")
            response = requests.get(
                f"{self._base_url()}/api/v2/alerts",
                headers=self._get_headers(),
                auth=self._get_auth(),
                params={"active": "true", "silenced": "false", "inhibited": "false"},
                timeout=30,
            )
            if not response.ok:
                self.logger.error(
                    "Failed to fetch Alertmanager alerts: %s", response.text
                )
                return alerts

            for item in response.json():
                alerts.append(self._item_to_alert_dto(item))

        except Exception as e:
            self.logger.error("Error pulling Alertmanager alerts: %s", e)
        return alerts

    def _item_to_alert_dto(self, item: dict) -> AlertDto:
        labels = item.get("labels", {})
        annotations = item.get("annotations", {})
        status_obj = item.get("status", {})

        alert_name = labels.get("alertname", "Unknown")
        severity_label = labels.get("severity", "info").lower()
        state = status_obj.get("state", "firing").lower()

        starts_at = item.get("startsAt")
        ends_at = item.get("endsAt")

        # endsAt is "0001-01-01T00:00:00Z" when alert is still firing
        if ends_at and ends_at.startswith("0001"):
            ends_at = None

        last_received = ends_at or starts_at or datetime.datetime.utcnow().isoformat()

        # Build fingerprint-based ID
        fingerprint = item.get("fingerprint", "")

        # Collect generator URL
        generator_url = item.get("generatorURL", "")

        return AlertDto(
            id=fingerprint or alert_name,
            name=alert_name,
            description=annotations.get("description", annotations.get("summary", "")),
            severity=self.SEVERITY_MAP.get(severity_label, AlertSeverity.INFO),
            status=self.STATUS_MAP.get(state, AlertStatus.FIRING),
            lastReceived=last_received,
            startedAt=starts_at,
            url=generator_url,
            source=["alertmanager"],
            labels={**labels, "state": state},
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format an Alertmanager webhook payload into AlertDto(s).

        Alertmanager sends webhook payloads with the shape:
        {
          "version": "4",
          "groupKey": "...",
          "status": "firing" | "resolved",
          "receiver": "...",
          "groupLabels": {...},
          "commonLabels": {...},
          "commonAnnotations": {...},
          "externalURL": "...",
          "alerts": [ { "status": "firing", "labels": {...}, ... }, ... ]
        }
        """
        common_labels = event.get("commonLabels", {})
        common_annotations = event.get("commonAnnotations", {})
        external_url = event.get("externalURL", "")
        group_status = event.get("status", "firing")

        alert_dtos = []
        for item in event.get("alerts", [event]):
            labels = {**common_labels, **item.get("labels", {})}
            annotations = {**common_annotations, **item.get("annotations", {})}
            status_str = item.get("status", group_status).lower()
            severity_label = labels.get("severity", "info").lower()
            alert_name = labels.get("alertname", "Unknown")
            fingerprint = item.get("fingerprint", "")
            starts_at = item.get("startsAt")
            ends_at = item.get("endsAt")

            if ends_at and ends_at.startswith("0001"):
                ends_at = None

            last_received = ends_at or starts_at or datetime.datetime.utcnow().isoformat()
            generator_url = item.get("generatorURL", external_url)

            alert_dtos.append(
                AlertDto(
                    id=fingerprint or alert_name,
                    name=alert_name,
                    description=annotations.get(
                        "description", annotations.get("summary", "")
                    ),
                    severity=AlertmanagerProvider.SEVERITY_MAP.get(
                        severity_label, AlertSeverity.INFO
                    ),
                    status=AlertmanagerProvider.STATUS_MAP.get(
                        status_str, AlertStatus.FIRING
                    ),
                    lastReceived=last_received,
                    startedAt=starts_at,
                    url=generator_url,
                    source=["alertmanager"],
                    labels=labels,
                )
            )

        return alert_dtos if len(alert_dtos) != 1 else alert_dtos[0]


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    url = os.environ.get("ALERTMANAGER_URL", "http://localhost:9093")

    config = ProviderConfig(
        description="Alertmanager Provider",
        authentication={"alertmanager_url": url},
    )

    provider = AlertmanagerProvider(
        context_manager,
        provider_id="alertmanager-test",
        config=config,
    )

    alerts = provider._get_alerts()
    print(f"Found {len(alerts)} active alerts")
    for a in alerts:
        print(a)
