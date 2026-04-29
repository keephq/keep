"""
GrafanaFaroProvider is a class that receives frontend observability data from Grafana Faro.
Grafana Faro is an open-source web SDK for real user monitoring (RUM) — capturing JavaScript
errors, performance metrics, and user session data from web applications.
"""

import dataclasses
import datetime
from typing import List

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class GrafanaFaroProviderAuthConfig:
    """
    GrafanaFaroProviderAuthConfig holds credentials for connecting to a Grafana Cloud
    instance that collects Faro telemetry, or a self-hosted Grafana with Faro backend.
    """

    grafana_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Grafana instance URL",
            "hint": "e.g. https://your-org.grafana.net",
            "sensitive": False,
            "validation": "any_http_url",
        },
    )

    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Grafana API token with at least Viewer role",
            "hint": "Create a service account token in Grafana → Administration → Service Accounts",
            "sensitive": True,
        },
    )

    app_name: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Faro application name to filter alerts (leave empty for all)",
            "hint": "The app_name configured in your Faro SDK initialization",
            "sensitive": False,
        },
        default="",
    )


class GrafanaFaroProvider(BaseProvider):
    """Receive frontend observability signals from Grafana Faro (JavaScript errors, performance alerts)."""

    PROVIDER_DISPLAY_NAME = "Grafana Faro"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated with Grafana API",
            mandatory=True,
            alias="authenticated",
        ),
    ]

    # Faro log levels mapped to Keep severities
    SEVERITIES_MAP = {
        "error": AlertSeverity.HIGH,
        "warn": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "trace": AlertSeverity.LOW,
        "debug": AlertSeverity.LOW,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = GrafanaFaroProviderAuthConfig(
            **self.config.authentication
        )

    def __get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.authentication_config.api_token}",
            "Content-Type": "application/json",
        }

    def __get_api_url(self, path: str) -> str:
        base = self.authentication_config.grafana_url.rstrip("/")
        return f"{base}/api/{path.lstrip('/')}"

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {}
        try:
            resp = requests.get(
                self.__get_api_url("health"),
                headers=self.__get_headers(),
                timeout=10,
            )
            if resp.status_code in (200, 401):
                # Try authenticated endpoint
                auth_resp = requests.get(
                    self.__get_api_url("org"),
                    headers=self.__get_headers(),
                    timeout=10,
                )
                if auth_resp.status_code == 200:
                    scopes["authenticated"] = True
                elif auth_resp.status_code == 401:
                    scopes["authenticated"] = "Invalid or expired API token"
                else:
                    scopes["authenticated"] = (
                        f"Unexpected status code: {auth_resp.status_code}"
                    )
            else:
                scopes["authenticated"] = (
                    f"Cannot reach Grafana at {self.authentication_config.grafana_url}: {resp.status_code}"
                )
        except Exception as e:
            self.logger.error("Error validating Grafana Faro scopes: %s", e)
            scopes["authenticated"] = str(e)
        return scopes

    def __get_faro_alerts_from_grafana(self) -> List[AlertDto]:
        """
        Query Grafana Alerting for rules related to Faro / frontend observability.
        Faro data is typically stored in Loki (logs) or Prometheus (metrics) and
        surfaced through Grafana alerting rules.
        """
        try:
            resp = requests.get(
                self.__get_api_url("prometheus/grafana/api/v1/alerts"),
                headers=self.__get_headers(),
                timeout=15,
            )

            if not resp.ok:
                self.logger.warning(
                    "Could not fetch Grafana alerts (status %s), trying unified alerting endpoint",
                    resp.status_code,
                )
                # Try the unified alerting API
                resp = requests.get(
                    self.__get_api_url("alertmanager/grafana/api/v2/alerts"),
                    headers=self.__get_headers(),
                    params={"active": "true"},
                    timeout=15,
                )

            if not resp.ok:
                self.logger.error(
                    "Failed to get alerts from Grafana: %s", resp.text
                )
                return []

            data = resp.json()
            raw_alerts = data.get("data", {}).get("alerts", []) if isinstance(data, dict) else data
            if not isinstance(raw_alerts, list):
                raw_alerts = []

            alerts = []
            for alert in raw_alerts:
                labels = alert.get("labels", {})

                # Filter by app_name if configured
                app_name = labels.get("app_name", labels.get("app", ""))
                if (
                    self.authentication_config.app_name
                    and app_name != self.authentication_config.app_name
                ):
                    continue

                severity_str = labels.get("severity", "warning").lower()
                severity = self.SEVERITIES_MAP.get(severity_str, AlertSeverity.WARNING)

                state = alert.get("state", alert.get("status", {}).get("state", "firing"))
                status = (
                    AlertStatus.RESOLVED
                    if state in ("inactive", "resolved")
                    else AlertStatus.FIRING
                )

                alert_name = labels.get("alertname", "Grafana Faro Alert")
                annotations = alert.get("annotations", {})
                description = annotations.get("description", annotations.get("summary", ""))

                active_at = alert.get("activeAt", alert.get("startsAt", ""))
                if active_at:
                    try:
                        active_at = datetime.datetime.fromisoformat(
                            active_at.replace("Z", "+00:00")
                        ).isoformat()
                    except Exception:
                        pass

                alerts.append(
                    AlertDto(
                        id=labels.get("alertname", "") + labels.get("fingerprint", ""),
                        name=alert_name,
                        description=description,
                        severity=severity,
                        status=status,
                        lastReceived=active_at,
                        source=["grafana_faro"],
                        labels={
                            "app_name": app_name,
                            "environment": labels.get("env", labels.get("environment", "")),
                            "url": annotations.get("runbook_url", ""),
                            **{k: v for k, v in labels.items() if k not in ("alertname", "severity")},
                        },
                    )
                )

            return alerts

        except Exception as e:
            self.logger.error("Error fetching Grafana Faro alerts: %s", e)
            return []

    def _get_alerts(self) -> List[AlertDto]:
        self.logger.info("Collecting frontend observability alerts from Grafana Faro")
        return self.__get_faro_alerts_from_grafana()

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a Grafana Faro webhook / Grafana Alerting webhook payload into an AlertDto.

        Grafana Faro SDK can push exceptions and log messages to a collector,
        which then forwards to Grafana Alerting. This handler accepts the
        Grafana Alertmanager webhook format.
        """
        alerts = []

        # Handle Grafana Alertmanager webhook format
        raw_alerts = event.get("alerts", [event])

        for alert in raw_alerts:
            labels = alert.get("labels", {})
            annotations = alert.get("annotations", {})

            severity_str = labels.get("severity", "warning").lower()
            severity_map = {
                "critical": AlertSeverity.CRITICAL,
                "high": AlertSeverity.HIGH,
                "error": AlertSeverity.HIGH,
                "warning": AlertSeverity.WARNING,
                "warn": AlertSeverity.WARNING,
                "info": AlertSeverity.INFO,
            }
            severity = severity_map.get(severity_str, AlertSeverity.WARNING)

            status_str = alert.get("status", "firing")
            status = (
                AlertStatus.RESOLVED if status_str == "resolved" else AlertStatus.FIRING
            )

            ends_at = alert.get("endsAt", "")
            starts_at = alert.get("startsAt", "")
            last_received = ends_at if status == AlertStatus.RESOLVED else starts_at

            if last_received:
                try:
                    last_received = datetime.datetime.fromisoformat(
                        last_received.replace("Z", "+00:00")
                    ).isoformat()
                except Exception:
                    pass

            alerts.append(
                AlertDto(
                    id=alert.get("fingerprint", labels.get("alertname", "")),
                    name=labels.get("alertname", "Grafana Faro Alert"),
                    description=annotations.get(
                        "description", annotations.get("summary", "")
                    ),
                    severity=severity,
                    status=status,
                    lastReceived=last_received,
                    source=["grafana_faro"],
                    labels={
                        "app_name": labels.get("app_name", labels.get("app", "")),
                        "environment": labels.get("env", labels.get("environment", "")),
                        "generator_url": alert.get("generatorURL", ""),
                        **{
                            k: v
                            for k, v in labels.items()
                            if k not in ("alertname", "severity")
                        },
                    },
                    url=alert.get("generatorURL", ""),
                )
            )

        return alerts if len(alerts) > 1 else (alerts[0] if alerts else None)


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    grafana_url = os.environ.get("GRAFANA_URL")
    api_token = os.environ.get("GRAFANA_API_TOKEN")

    if not grafana_url or not api_token:
        raise Exception("GRAFANA_URL and GRAFANA_API_TOKEN must be set")

    config = ProviderConfig(
        description="Grafana Faro Provider",
        authentication={
            "grafana_url": grafana_url,
            "api_token": api_token,
        },
    )

    provider = GrafanaFaroProvider(
        context_manager,
        provider_id="grafana_faro",
        config=config,
    )

    alerts = provider._get_alerts()
    print(f"Found {len(alerts)} alerts")
    for alert in alerts[:5]:
        print(alert)
