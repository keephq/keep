"""
TeamCityProvider — Pull failed builds and build investigations from JetBrains TeamCity.

TeamCity (https://www.jetbrains.com/teamcity/) is a widely-used CI/CD server.
Keep integrates with TeamCity in two ways:

1. **Pull mode** — Keep polls TeamCity's REST API for *failed or cancelled builds*
   and surfaces them as alerts, so teams can correlate CI failures with other
   incidents in the same dashboard.

2. **Webhook (push) mode** — TeamCity can POST build-event webhooks to Keep via
   a third-party plugin (e.g. Tcwebhooks) or custom build steps.

API reference: https://www.jetbrains.com/help/teamcity/rest/teamcity-rest-api-documentation.html
"""

import dataclasses
import datetime
import typing

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory


# ---------------------------------------------------------------------------
# Auth config
# ---------------------------------------------------------------------------


@pydantic.dataclasses.dataclass
class TeamcityProviderAuthConfig:
    """Authentication configuration for TeamCity.

    TeamCity supports two auth mechanisms:
    - **Bearer token** (recommended): create a *Personal Access Token* in
      your TeamCity profile (Profile → Access Tokens → Create token).
    - **Username + password**: plain HTTP Basic auth.
    """

    deployment_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "TeamCity server URL",
            "hint": "e.g. https://teamcity.example.com or http://localhost:8111",
            "validation": "any_http_url",
        }
    )

    # --- option A: personal access token ---
    access_token: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "TeamCity Personal Access Token",
            "hint": "Create in Profile → Access Tokens (TeamCity 2019.1+)",
            "sensitive": True,
            "config_sub_group": "token",
            "config_main_group": "authentication",
        },
    )

    # --- option B: username + password ---
    username: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "TeamCity username",
            "config_sub_group": "username_password",
            "config_main_group": "authentication",
        },
    )
    password: typing.Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "TeamCity password",
            "sensitive": True,
            "config_sub_group": "username_password",
            "config_main_group": "authentication",
        },
    )

    verify_ssl: bool = dataclasses.field(
        default=True,
        metadata={
            "required": False,
            "description": "Verify TLS/SSL certificates",
            "hint": "Disable for self-signed certificates in dev/test environments",
            "type": "switch",
        },
    )

    @pydantic.root_validator
    def check_auth(cls, values):  # noqa: N805
        token = values.get("access_token")
        username = values.get("username")
        password = values.get("password")
        if not token and not (username and password):
            raise ValueError(
                "Provide either an access_token or both username and password."
            )
        return values


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class TeamcityProvider(BaseProvider):
    """Pull failed builds from TeamCity CI/CD and receive webhook build events."""

    PROVIDER_DISPLAY_NAME = "TeamCity"
    PROVIDER_CATEGORY = ["Developer Tools", "Cloud Infrastructure"]
    PROVIDER_TAGS = ["alert"]

    # ------------------------------------------------------------------
    # Webhook (push) documentation
    # ------------------------------------------------------------------
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To push TeamCity build events to Keep:

**Option 1 — Tcwebhooks plugin** (recommended):
1. Install the [Tcwebhooks plugin](https://github.com/tcplugins/tcWebHooks) on your TeamCity server.
2. In TeamCity, go to **Administration → Webhooks** and create a new webhook.
3. Set the URL to `{keep_webhook_api_url}`.
4. Add a custom header `X-API-KEY: {api_key}`.
5. Select the build events you want to forward (e.g. *Build Failed*, *Build Finished*).

**Option 2 — Build step / Failure condition script**:
1. Add a *Command Line* build step that runs after failure:
```bash
curl -s -X POST {keep_webhook_api_url} \\
  -H "x-api-key: {api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{{"buildId":"%teamcity.build.id%","buildTypeId":"%system.teamcity.buildType.id%","status":"%teamcity.build.status.text%","projectName":"%system.teamcity.projectName%","branchName":"%teamcity.build.branch.name%"}}'
```
"""

    PROVIDER_SCOPES = [
        ProviderScope(
            name="view_project",
            description="Read access to projects and build configurations.",
            mandatory=True,
            alias="View Project",
        ),
        ProviderScope(
            name="view_build_runtime_data",
            description="Read access to build results and logs.",
            mandatory=True,
            alias="View Build Runtime Data",
        ),
    ]

    # Build-status → alert-status
    STATUS_MAP: dict[str, AlertStatus] = {
        "failure": AlertStatus.FIRING,
        "failed": AlertStatus.FIRING,
        "error": AlertStatus.FIRING,
        "cancelled": AlertStatus.FIRING,
        "canceled": AlertStatus.FIRING,
        "unknown": AlertStatus.FIRING,
        "success": AlertStatus.RESOLVED,
        "succeeded": AlertStatus.RESOLVED,
    }

    # Build-status → alert-severity
    SEVERITY_MAP: dict[str, AlertSeverity] = {
        "failure": AlertSeverity.HIGH,
        "failed": AlertSeverity.HIGH,
        "error": AlertSeverity.CRITICAL,
        "cancelled": AlertSeverity.WARNING,
        "canceled": AlertSeverity.WARNING,
        "unknown": AlertSeverity.INFO,
        "success": AlertSeverity.LOW,
        "succeeded": AlertSeverity.LOW,
    }

    FINGERPRINT_FIELDS = ["buildTypeId", "branchName"]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ) -> None:
        super().__init__(context_manager, provider_id, config)

    # ------------------------------------------------------------------
    # Config & auth helpers
    # ------------------------------------------------------------------

    def validate_config(self) -> None:
        self.authentication_config = TeamcityProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self) -> None:
        pass

    def _base_url(self) -> str:
        return str(self.authentication_config.deployment_url).rstrip("/")

    def _headers(self) -> dict[str, str]:
        cfg = self.authentication_config
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if cfg.access_token:
            headers["Authorization"] = f"Bearer {cfg.access_token}"
        return headers

    def _auth(self) -> typing.Optional[tuple[str, str]]:
        cfg = self.authentication_config
        if not cfg.access_token and cfg.username and cfg.password:
            return (cfg.username, cfg.password)
        return None

    def _get(self, path: str, params: typing.Optional[dict] = None) -> dict:
        url = f"{self._base_url()}{path}"
        try:
            resp = requests.get(
                url,
                headers=self._headers(),
                auth=self._auth(),
                params=params,
                verify=self.authentication_config.verify_ssl,
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as exc:
            raise ProviderException(
                f"TeamCity API error {exc.response.status_code} on GET {path}: "
                f"{exc.response.text[:200]}"
            ) from exc
        except requests.RequestException as exc:
            raise ProviderException(
                f"TeamCity request failed on GET {path}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Scope validation
    # ------------------------------------------------------------------

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes: dict[str, bool | str] = {}

        try:
            # /app/rest/builds requires view_project + view_build_runtime_data
            self._get("/app/rest/builds", {"count": 1})
            scopes["view_project"] = True
            scopes["view_build_runtime_data"] = True
        except ProviderException as exc:
            error = str(exc)
            scopes["view_project"] = error
            scopes["view_build_runtime_data"] = error

        return scopes

    # ------------------------------------------------------------------
    # Pull mode — fetch failed builds
    # ------------------------------------------------------------------

    def _get_alerts(self) -> list[AlertDto]:
        """Fetch failed, cancelled, or unknown-status builds from TeamCity."""
        alerts: list[AlertDto] = []
        try:
            # Locator: status:FAILURE|CANCELED and count=100 most recent
            data = self._get(
                "/app/rest/builds",
                {
                    "locator": "status:FAILURE,count:100,running:false",
                    "fields": (
                        "build(id,number,status,statusText,state,branchName,"
                        "buildType(id,name,projectName,webUrl),"
                        "startDate,finishDate,webUrl,triggered)"
                    ),
                },
            )
            builds = data.get("build", [])
            if not isinstance(builds, list):
                return alerts

            for build in builds:
                dto = self._build_to_alert_dto(build)
                if dto:
                    alerts.append(dto)

            # Also fetch cancelled builds
            data2 = self._get(
                "/app/rest/builds",
                {
                    "locator": "status:CANCELED,count:50,running:false",
                    "fields": (
                        "build(id,number,status,statusText,state,branchName,"
                        "buildType(id,name,projectName,webUrl),"
                        "startDate,finishDate,webUrl,triggered)"
                    ),
                },
            )
            cancelled = data2.get("build", [])
            if isinstance(cancelled, list):
                for build in cancelled:
                    dto = self._build_to_alert_dto(build)
                    if dto:
                        alerts.append(dto)

        except ProviderException as exc:
            self.logger.warning("TeamCity pull failed: %s", exc)

        return alerts

    # ------------------------------------------------------------------
    # Webhook (push) mode
    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(
        event: dict | list, provider_instance: "TeamcityProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """Convert a TeamCity webhook payload into an AlertDto."""
        if isinstance(event, list):
            result = []
            for item in event:
                dto = TeamcityProvider._build_to_alert_dto(item)
                if dto:
                    result.append(dto)
            return result if result else []

        dto = TeamcityProvider._build_to_alert_dto(event)
        return dto if dto else AlertDto(name="TeamCity Build Event", source=["teamcity"])

    # ------------------------------------------------------------------
    # Shared build → AlertDto conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _build_to_alert_dto(
        build: dict,
    ) -> typing.Optional[AlertDto]:
        if not isinstance(build, dict):
            return None

        # --- IDs ----------------------------------------------------------
        build_id = build.get("id") or build.get("buildId")
        build_number = build.get("number") or build.get("buildNumber", "")

        # --- build type / config ------------------------------------------
        build_type = build.get("buildType") or {}
        build_type_id = (
            build.get("buildTypeId")
            or build_type.get("id")
            or build.get("buildType", {}).get("id", "")
            if isinstance(build.get("buildType"), dict)
            else build.get("buildTypeId", "")
        )
        build_name = build_type.get("name") if isinstance(build_type, dict) else ""
        project_name = (
            build_type.get("projectName") if isinstance(build_type, dict) else ""
        ) or build.get("projectName", "")
        web_url = (
            build.get("webUrl")
            or (build_type.get("webUrl") if isinstance(build_type, dict) else None)
        )

        # --- status -------------------------------------------------------
        raw_status = (build.get("status") or build.get("buildStatus", "")).lower()
        status = TeamcityProvider.STATUS_MAP.get(raw_status, AlertStatus.FIRING)
        severity = TeamcityProvider.SEVERITY_MAP.get(raw_status, AlertSeverity.HIGH)
        status_text = build.get("statusText") or build.get("status", "")

        # --- branch -------------------------------------------------------
        branch = build.get("branchName") or build.get("branch", "")

        # --- name/title ---------------------------------------------------
        parts = []
        if project_name:
            parts.append(project_name)
        if build_name:
            parts.append(build_name)
        if build_number:
            parts.append(f"#{build_number}")
        name = " / ".join(parts) if parts else f"Build {build_id}"

        # --- description --------------------------------------------------
        description = status_text
        if branch:
            description = f"{description} (branch: {branch})" if description else f"Branch: {branch}"

        # --- timestamps ---------------------------------------------------
        last_received: typing.Optional[datetime.datetime] = None
        started_at: typing.Optional[datetime.datetime] = None

        for ts_raw, target in [
            (build.get("finishDate") or build.get("finishDateStr"), "last_received"),
            (build.get("startDate") or build.get("startDateStr"), "started_at"),
        ]:
            parsed = TeamcityProvider._parse_tc_datetime(ts_raw)
            if target == "last_received":
                last_received = parsed
            else:
                started_at = parsed

        # --- triggered by -------------------------------------------------
        triggered = build.get("triggered") or {}
        triggered_by = ""
        if isinstance(triggered, dict):
            triggered_by = (
                triggered.get("user", {}).get("username", "")
                if isinstance(triggered.get("user"), dict)
                else triggered.get("type", "")
            )

        # --- labels -------------------------------------------------------
        labels: dict[str, str] = {}
        if project_name:
            labels["projectName"] = project_name
        if build_type_id:
            labels["buildTypeId"] = str(build_type_id)
        if branch:
            labels["branchName"] = branch
        if triggered_by:
            labels["triggeredBy"] = triggered_by
        if build_number:
            labels["buildNumber"] = str(build_number)

        return AlertDto(
            id=str(build_id) if build_id else None,
            name=name,
            description=description,
            severity=severity,
            status=status,
            lastReceived=last_received.isoformat() if last_received else None,
            startedAt=started_at.isoformat() if started_at else None,
            url=web_url,
            source=["teamcity"],
            buildId=str(build_id) if build_id else None,
            buildNumber=str(build_number) if build_number else None,
            buildTypeId=str(build_type_id) if build_type_id else None,
            buildName=build_name,
            projectName=project_name,
            branchName=branch,
            statusText=status_text,
            labels=labels,
        )

    @staticmethod
    def _parse_tc_datetime(raw: typing.Any) -> typing.Optional[datetime.datetime]:
        """Parse a TeamCity date string.

        TeamCity uses the format ``20240101T123000+0000`` (ISO 8601 compact).
        We also handle standard ISO strings and Unix timestamps.
        """
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            try:
                return datetime.datetime.fromtimestamp(
                    float(raw), tz=datetime.timezone.utc
                ).replace(tzinfo=None)
            except (ValueError, OSError, OverflowError):
                return None
        if not isinstance(raw, str) or not raw.strip():
            return None
        s = raw.strip()
        # TeamCity compact format: 20240615T142300+0000
        if len(s) >= 15 and s[8] == "T" and not s[10:11] in (":", "-"):
            try:
                # Insert dashes/colons for fromisoformat compatibility
                s = f"{s[:4]}-{s[4:6]}-{s[6:8]}T{s[9:11]}:{s[11:13]}:{s[13:15]}{s[15:]}"
            except IndexError:
                pass
        try:
            return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).replace(
                tzinfo=None
            )
        except (ValueError, TypeError):
            return None


# ---------------------------------------------------------------------------
# Manual test entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")

    config = {
        "authentication": {
            "deployment_url": os.environ["TEAMCITY_URL"],
            "access_token": os.environ.get("TEAMCITY_TOKEN"),
        }
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="teamcity-test",
        provider_type="teamcity",
        provider_config=config,
    )
    print("Scopes:", provider.validate_scopes())
    alerts = provider.get_alerts()
    print(f"Fetched {len(alerts)} alerts")
    for a in alerts[:5]:
        print(" -", a.name, a.severity, a.status)
