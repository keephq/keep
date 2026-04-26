"""
CorootProvider integrates Keep with Coroot, an open-source, eBPF-based
observability and SLO monitoring platform.  It pulls active SLO violations
and cluster-level alerts so you can route and correlate them in Keep.
"""

import dataclasses
import datetime
from typing import List, Optional
from urllib.parse import urljoin

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class CorootProviderAuthConfig:
    """
    CorootProviderAuthConfig holds connection details for a self-hosted or
    Coroot Cloud instance.
    """

    coroot_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Base URL of your Coroot instance",
            "hint": "e.g. https://coroot.my-company.com or http://localhost:8080",
            "validation": "any_http_url",
        },
    )

    api_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Coroot API key (required for Coroot Cloud and authenticated instances)",
            "hint": "Generate under Settings > API Keys in Coroot",
            "sensitive": True,
        },
        default="",
    )

    project_id: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Coroot project / world ID (leave blank to use the default project)",
            "hint": "Visible in the Coroot URL: /p/<project_id>/",
        },
        default="default",
    )


class CorootProvider(BaseProvider):
    """Pull SLO violations and health alerts from a Coroot observability instance."""

    PROVIDER_DISPLAY_NAME = "Coroot"
    PROVIDER_TAGS = ["monitoring"]
    PROVIDER_CATEGORY = ["Monitoring", "Cloud Infrastructure"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="alerts:read",
            description="Read SLO violations and cluster alerts from Coroot",
            mandatory=True,
            alias="Read Alerts",
            documentation_url="https://coroot.com/docs",
        ),
    ]

    # Coroot severity names → Keep severity
    _SEVERITY_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
    }

    # Coroot status names → Keep status
    _STATUS_MAP = {
        "firing": AlertStatus.FIRING,
        "ok": AlertStatus.RESOLVED,
        "resolved": AlertStatus.RESOLVED,
        "pending": AlertStatus.PENDING,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "suppressed": AlertStatus.SUPPRESSED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = CorootProviderAuthConfig(
            **self.config.authentication
        )

    def _get_headers(self) -> dict:
        headers: dict = {"Content-Type": "application/json"}
        if self.authentication_config.api_key:
            headers["X-Api-Key"] = self.authentication_config.api_key
        return headers

    def _base_url(self) -> str:
        return str(self.authentication_config.coroot_url).rstrip("/")

    def _project_path(self) -> str:
        pid = self.authentication_config.project_id or "default"
        return f"/api/projects/{pid}"

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes: dict[str, bool | str] = {}
        try:
            # Lightweight check: hit the project overview endpoint
            url = f"{self._base_url()}{self._project_path()}/overview"
            resp = requests.get(url, headers=self._get_headers(), timeout=10)
            if resp.status_code in (200, 204):
                scopes["alerts:read"] = True
            elif resp.status_code == 401:
                scopes["alerts:read"] = "Unauthorized — check your API key"
            elif resp.status_code == 403:
                scopes["alerts:read"] = "Forbidden — insufficient permissions"
            elif resp.status_code == 404:
                # Try root to see if instance is reachable at all
                root_resp = requests.get(
                    self._base_url(), headers=self._get_headers(), timeout=10
                )
                if root_resp.ok:
                    scopes["alerts:read"] = (
                        f"Project '{self.authentication_config.project_id}' not found"
                    )
                else:
                    scopes["alerts:read"] = f"Coroot instance not reachable at {self._base_url()}"
            else:
                scopes["alerts:read"] = f"Unexpected response: {resp.status_code}"
        except Exception as e:
            self.logger.exception("Failed to validate Coroot scopes")
            scopes["alerts:read"] = str(e)
        return scopes

    def _get_alerts(self) -> List[AlertDto]:
        """
        Pull active SLO violations from Coroot and return them as AlertDtos.

        Coroot exposes SLO status under:
          GET /api/projects/{project_id}/slo

        and application-level checks under:
          GET /api/projects/{project_id}/apps
        """
        self.logger.info("Fetching alerts from Coroot")
        alerts: List[AlertDto] = []

        alerts.extend(self._get_slo_alerts())
        alerts.extend(self._get_app_alerts())

        self.logger.info("Fetched %d Coroot alerts", len(alerts))
        return alerts

    def _get_slo_alerts(self) -> List[AlertDto]:
        """Pull SLO violations from Coroot."""
        alerts: List[AlertDto] = []
        url = f"{self._base_url()}{self._project_path()}/slo"

        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=15)
            if not resp.ok:
                self.logger.warning(
                    "SLO endpoint returned %s — skipping SLO alerts", resp.status_code
                )
                return alerts

            data = resp.json()
            slos = data if isinstance(data, list) else data.get("slos", [])

            for slo in slos:
                status_raw = slo.get("status", "firing").lower()
                if status_raw in ("ok", "resolved"):
                    continue  # Only surface violations

                slo_id = str(slo.get("id", slo.get("name", "")))
                name = slo.get("name", slo_id)
                objective = slo.get("objective", "")
                sli_value = slo.get("sli", {})
                service = slo.get("app", slo.get("service", ""))

                severity_raw = slo.get("severity", "warning").lower()
                alert = AlertDto(
                    id=f"coroot-slo-{slo_id}",
                    name=f"SLO violation: {name}",
                    severity=self._SEVERITY_MAP.get(severity_raw, AlertSeverity.WARNING),
                    status=self._STATUS_MAP.get(status_raw, AlertStatus.FIRING),
                    lastReceived=datetime.datetime.utcnow(),
                    description=(
                        f"SLO '{name}' is violating its objective. "
                        f"Objective: {objective}. Current SLI: {sli_value}"
                    ),
                    source=["coroot"],
                    url=(
                        f"{self._base_url()}/p/{self.authentication_config.project_id}"
                        f"/slo/{slo_id}"
                    ),
                    fingerprint=f"coroot-slo-{slo_id}",
                    service=service,
                    objective=str(objective),
                    sli=str(sli_value),
                )
                alerts.append(alert)
        except Exception as e:
            self.logger.error("Failed to fetch Coroot SLO alerts: %s", e)

        return alerts

    def _get_app_alerts(self) -> List[AlertDto]:
        """Pull application-level health alerts from Coroot."""
        alerts: List[AlertDto] = []
        url = f"{self._base_url()}{self._project_path()}/apps"

        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=15)
            if not resp.ok:
                self.logger.warning(
                    "Apps endpoint returned %s — skipping app alerts", resp.status_code
                )
                return alerts

            data = resp.json()
            apps = data if isinstance(data, list) else data.get("apps", [])

            for app in apps:
                health = app.get("health", app.get("status", "ok")).lower()
                if health in ("ok", "healthy", "resolved"):
                    continue

                app_id = str(app.get("id", app.get("name", "")))
                app_name = app.get("name", app_id)
                namespace = app.get("namespace", "")
                issues = app.get("issues", [])

                for idx, issue in enumerate(issues):
                    issue_name = issue.get("name", f"Issue #{idx + 1}")
                    severity_raw = issue.get("severity", "warning").lower()
                    status_raw = issue.get("status", "firing").lower()

                    if status_raw in ("ok", "resolved"):
                        continue

                    alert = AlertDto(
                        id=f"coroot-app-{app_id}-issue-{idx}",
                        name=f"Coroot: {app_name} — {issue_name}",
                        severity=self._SEVERITY_MAP.get(
                            severity_raw, AlertSeverity.WARNING
                        ),
                        status=self._STATUS_MAP.get(status_raw, AlertStatus.FIRING),
                        lastReceived=datetime.datetime.utcnow(),
                        description=issue.get(
                            "description",
                            f"Application '{app_name}' has a health issue: {issue_name}",
                        ),
                        source=["coroot"],
                        url=(
                            f"{self._base_url()}/p/{self.authentication_config.project_id}"
                            f"/app/{app_id}"
                        ),
                        fingerprint=f"coroot-app-{app_id}-{issue_name}",
                        service=app_name,
                        namespace=namespace,
                    )
                    alerts.append(alert)

                # Surface app-level alert if there are no discrete issues but app is unhealthy
                if not issues:
                    alert = AlertDto(
                        id=f"coroot-app-{app_id}-unhealthy",
                        name=f"Coroot: {app_name} is {health}",
                        severity=AlertSeverity.WARNING,
                        status=AlertStatus.FIRING,
                        lastReceived=datetime.datetime.utcnow(),
                        description=f"Application '{app_name}' health state: {health}",
                        source=["coroot"],
                        url=(
                            f"{self._base_url()}/p/{self.authentication_config.project_id}"
                            f"/app/{app_id}"
                        ),
                        fingerprint=f"coroot-app-{app_id}-unhealthy",
                        service=app_name,
                        namespace=namespace,
                    )
                    alerts.append(alert)
        except Exception as e:
            self.logger.error("Failed to fetch Coroot app alerts: %s", e)

        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """Format a Coroot webhook payload into an AlertDto."""
        severity_raw = event.get("severity", "warning").lower()
        status_raw = event.get("status", "firing").lower()

        severity = CorootProvider._SEVERITY_MAP.get(severity_raw, AlertSeverity.WARNING)
        status = CorootProvider._STATUS_MAP.get(status_raw, AlertStatus.FIRING)

        fired_at = event.get("fired_at") or event.get("timestamp")
        if fired_at:
            try:
                last_received = datetime.datetime.fromisoformat(
                    str(fired_at).replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                last_received = datetime.datetime.utcnow()
        else:
            last_received = datetime.datetime.utcnow()

        return AlertDto(
            id=str(event.get("id", "")),
            name=event.get("name", event.get("title", "Coroot alert")),
            severity=severity,
            status=status,
            lastReceived=last_received,
            description=event.get("description", event.get("summary", "")),
            source=["coroot"],
            url=event.get("url", ""),
            fingerprint=str(event.get("id", event.get("name", ""))),
            service=event.get("app", event.get("service", "")),
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    coroot_url = os.environ.get("COROOT_URL", "http://localhost:8080")
    api_key = os.environ.get("COROOT_API_KEY", "")

    config = ProviderConfig(
        description="Coroot Provider",
        authentication={
            "coroot_url": coroot_url,
            "api_key": api_key,
            "project_id": "default",
        },
    )
    provider = CorootProvider(
        context_manager, provider_id="coroot-test", config=config
    )
    print(provider.validate_scopes())
    alerts = provider._get_alerts()
    print(f"Fetched {len(alerts)} alerts")
    for a in alerts:
        print(f"  - {a.name}: {a.severity} ({a.status})")
