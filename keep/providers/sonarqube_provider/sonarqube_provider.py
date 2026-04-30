"""
SonarqubeProvider is a class that allows pulling code quality issues and vulnerabilities from SonarQube.
"""

import dataclasses
import datetime
from typing import List
from urllib.parse import urljoin

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SonarqubeProviderAuthConfig:
    """
    SonarqubeProviderAuthConfig is a class that allows to authenticate in SonarQube.
    """

    token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SonarQube User Token",
            "hint": "Generate a token at: Your Profile → Security → Generate Token",
            "sensitive": True,
        },
    )

    url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SonarQube Server URL",
            "hint": "e.g. https://sonarqube.example.com or https://sonarcloud.io",
            "sensitive": False,
            "validation": "any_http_url",
        },
    )

    organization: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Organization key (required for SonarCloud)",
            "hint": "Your SonarCloud organization key",
            "sensitive": False,
        },
        default="",
    )


class SonarqubeProvider(BaseProvider):
    """Pull code quality issues, security vulnerabilities, and bugs from SonarQube/SonarCloud."""

    PROVIDER_DISPLAY_NAME = "SonarQube"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Security", "Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated with SonarQube API",
            mandatory=True,
            alias="authenticated",
        ),
    ]

    SEVERITIES_MAP = {
        "BLOCKER": AlertSeverity.CRITICAL,
        "CRITICAL": AlertSeverity.HIGH,
        "MAJOR": AlertSeverity.HIGH,
        "MINOR": AlertSeverity.WARNING,
        "INFO": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "OPEN": AlertStatus.FIRING,
        "CONFIRMED": AlertStatus.FIRING,
        "REOPENED": AlertStatus.FIRING,
        "RESOLVED": AlertStatus.RESOLVED,
        "CLOSED": AlertStatus.RESOLVED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = SonarqubeProviderAuthConfig(
            **self.config.authentication
        )

    def __get_base_url(self) -> str:
        url = self.authentication_config.url.rstrip("/")
        return url

    def __get_headers(self) -> dict:
        import base64

        credentials = base64.b64encode(
            f"{self.authentication_config.token}:".encode()
        ).decode()
        return {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        }

    def __get_api_url(self, path: str) -> str:
        return urljoin(self.__get_base_url() + "/api/", path.lstrip("/"))

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {}
        try:
            resp = requests.get(
                self.__get_api_url("authentication/validate"),
                headers=self.__get_headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("valid"):
                    scopes["authenticated"] = True
                else:
                    scopes["authenticated"] = "Token is not valid"
            elif resp.status_code == 401:
                scopes["authenticated"] = "Unauthorized: invalid token"
            else:
                scopes["authenticated"] = (
                    f"Unexpected status code: {resp.status_code}"
                )
        except Exception as e:
            self.logger.error("Error validating SonarQube scopes: %s", e)
            scopes["authenticated"] = str(e)
        return scopes

    def __get_issues(self) -> List[AlertDto]:
        """Fetch open issues (bugs, vulnerabilities, code smells) from SonarQube."""
        try:
            params = {
                "statuses": "OPEN,CONFIRMED,REOPENED",
                "types": "BUG,VULNERABILITY,CODE_SMELL",
                "ps": 500,
            }
            if self.authentication_config.organization:
                params["organization"] = self.authentication_config.organization

            resp = requests.get(
                self.__get_api_url("issues/search"),
                headers=self.__get_headers(),
                params=params,
                timeout=20,
            )

            if not resp.ok:
                self.logger.error(
                    "Failed to get issues from SonarQube: %s", resp.text
                )
                return []

            data = resp.json()
            issues = data.get("issues", [])
            alerts = []

            for issue in issues:
                severity_str = issue.get("severity", "MAJOR")
                severity = self.SEVERITIES_MAP.get(severity_str, AlertSeverity.WARNING)

                status_str = issue.get("status", "OPEN")
                status = self.STATUS_MAP.get(status_str, AlertStatus.FIRING)

                creation_date = issue.get("creationDate", "")
                if creation_date:
                    try:
                        # SonarQube returns ISO format with timezone
                        creation_date = datetime.datetime.fromisoformat(
                            creation_date.replace("Z", "+00:00")
                        ).isoformat()
                    except Exception:
                        pass

                component = issue.get("component", "")
                project = issue.get("project", "")
                rule = issue.get("rule", "")
                issue_type = issue.get("type", "BUG")
                message = issue.get("message", "SonarQube Issue")
                line = issue.get("line", "")

                alerts.append(
                    AlertDto(
                        id=issue.get("key", ""),
                        name=f"[{issue_type}] {message[:100]}",
                        description=message,
                        severity=severity,
                        status=status,
                        lastReceived=creation_date,
                        source=["sonarqube"],
                        labels={
                            "component": component,
                            "project": project,
                            "rule": rule,
                            "type": issue_type,
                            "severity": severity_str,
                            "line": str(line) if line else "",
                        },
                        url=f"{self.__get_base_url()}/project/issues?id={project}&issues={issue.get('key', '')}&open={issue.get('key', '')}",
                    )
                )

            return alerts

        except Exception as e:
            self.logger.error("Error getting issues from SonarQube: %s", e)
            return []

    def _get_alerts(self) -> List[AlertDto]:
        self.logger.info("Collecting issues from SonarQube")
        return self.__get_issues()

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """Format a SonarQube webhook payload into an AlertDto."""
        # SonarQube webhooks send project analysis events
        project = event.get("project", {})
        quality_gate = event.get("qualityGate", {})
        analysis_date = event.get("analysedAt", "")

        status = quality_gate.get("status", "OK")
        alert_status = (
            AlertStatus.FIRING if status in ("ERROR", "WARN") else AlertStatus.RESOLVED
        )
        severity = (
            AlertSeverity.HIGH if status == "ERROR" else AlertSeverity.WARNING
        )

        conditions = quality_gate.get("conditions", [])
        failed_conditions = [c for c in conditions if c.get("status") != "OK"]
        description = (
            "; ".join(
                f"{c.get('metricKey', '')}: {c.get('actualValue', '')} (threshold {c.get('errorThreshold', '')})"
                for c in failed_conditions
            )
            if failed_conditions
            else f"Quality Gate {status}"
        )

        return AlertDto(
            id=event.get("taskId", project.get("key", "")),
            name=f"[SonarQube] Quality Gate {status}: {project.get('name', 'Unknown')}",
            description=description,
            severity=severity,
            status=alert_status,
            lastReceived=analysis_date,
            source=["sonarqube"],
            labels={
                "project_key": project.get("key", ""),
                "project_name": project.get("name", ""),
                "branch": event.get("branch", {}).get("name", ""),
                "quality_gate_status": status,
            },
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    token = os.environ.get("SONARQUBE_TOKEN")
    url = os.environ.get("SONARQUBE_URL", "https://sonarcloud.io")

    if not token:
        raise Exception("SONARQUBE_TOKEN must be set")

    config = ProviderConfig(
        description="SonarQube Provider",
        authentication={
            "token": token,
            "url": url,
        },
    )

    provider = SonarqubeProvider(
        context_manager,
        provider_id="sonarqube",
        config=config,
    )

    alerts = provider._get_alerts()
    print(f"Found {len(alerts)} issues")
    for alert in alerts[:5]:
        print(alert)
