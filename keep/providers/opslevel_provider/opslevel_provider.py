"""
OpsLevelProvider integrates with OpsLevel service catalog and reliability platform,
allowing Keep to pull service check failures as alerts and receive webhook notifications
for service health events.
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
class OpsLevelProviderAuthConfig:
    """
    OpsLevelProviderAuthConfig holds authentication for the OpsLevel provider.
    """

    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "OpsLevel API Token",
            "hint": "Found at https://app.opslevel.com/api_tokens — create a token with read access",
            "sensitive": True,
        },
    )


class OpsLevelProvider(BaseProvider):
    """Pull service check failures from OpsLevel and receive reliability webhook events."""

    PROVIDER_DISPLAY_NAME = "OpsLevel"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated with OpsLevel API",
            mandatory=True,
            alias="authenticated",
        ),
    ]

    # OpsLevel check result status → Keep AlertStatus
    STATUS_MAP = {
        "failed": AlertStatus.FIRING,
        "passed": AlertStatus.RESOLVED,
        "upcoming": AlertStatus.FIRING,
        "needs_attention": AlertStatus.FIRING,
    }

    # OpsLevel check category → Keep AlertSeverity heuristic
    CATEGORY_SEVERITY_MAP = {
        "security": AlertSeverity.CRITICAL,
        "reliability": AlertSeverity.HIGH,
        "performance": AlertSeverity.HIGH,
        "quality": AlertSeverity.WARNING,
        "custom": AlertSeverity.WARNING,
        "general": AlertSeverity.INFO,
    }

    GRAPHQL_URL = "https://api.opslevel.com/graphql"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """Validate the provider configuration."""
        self.authentication_config = OpsLevelProviderAuthConfig(
            **self.config.authentication
        )

    def __get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.authentication_config.api_token}",
            "Content-Type": "application/json",
            "GraphQL-Visibility": "internal",
        }

    def __run_query(self, query: str, variables: Optional[dict] = None) -> dict:
        """Execute a GraphQL query against OpsLevel."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = requests.post(
            self.GRAPHQL_URL,
            headers=self.__get_headers(),
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate API token by fetching account info."""
        query = """
        query {
            account {
                name
            }
        }
        """
        try:
            result = self.__run_query(query)
            if "errors" in result:
                return {
                    "authenticated": f"GraphQL error: {result['errors'][0].get('message', 'unknown')}"
                }
            if result.get("data", {}).get("account"):
                return {"authenticated": True}
            return {"authenticated": "Unable to fetch account info"}
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                return {"authenticated": "Invalid or missing API token"}
            return {"authenticated": f"HTTP error: {e.response.status_code}"}
        except Exception as e:
            self.logger.error("Error validating OpsLevel scopes: %s", e)
            return {"authenticated": f"Error connecting to OpsLevel: {e}"}

    def _get_alerts(self) -> List[AlertDto]:
        """Pull failing service checks from OpsLevel."""
        alerts = []
        query = """
        query GetServiceCheckResults($after: String) {
            services(after: $after, first: 50) {
                nodes {
                    id
                    name
                    description
                    htmlUrl
                    checkStats {
                        totalChecks
                        totalPassingChecks
                    }
                    serviceStats {
                        rubric {
                            level {
                                name
                                index
                            }
                        }
                    }
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
        """
        try:
            self.logger.info("Fetching service check data from OpsLevel")
            after = None
            while True:
                variables = {"after": after} if after else {}
                result = self.__run_query(query, variables)

                if "errors" in result:
                    self.logger.error(
                        "OpsLevel GraphQL error: %s", result["errors"]
                    )
                    break

                services_data = result.get("data", {}).get("services", {})
                nodes = services_data.get("nodes", [])

                for service in nodes:
                    check_stats = service.get("checkStats", {})
                    total = check_stats.get("totalChecks", 0)
                    passing = check_stats.get("totalPassingChecks", 0)
                    failing = total - passing

                    if failing > 0:
                        alerts.append(self.__service_to_alert(service, failing, total))

                page_info = services_data.get("pageInfo", {})
                if not page_info.get("hasNextPage"):
                    break
                after = page_info.get("endCursor")

        except Exception as e:
            self.logger.error("Error fetching OpsLevel service data: %s", e)

        return alerts

    def __service_to_alert(
        self, service: dict, failing_checks: int, total_checks: int
    ) -> AlertDto:
        """Convert an OpsLevel service with failing checks to an AlertDto."""
        service_id = service.get("id", "unknown")
        name = service.get("name", "Unknown Service")
        description = service.get("description", "")
        url = service.get("htmlUrl", f"https://app.opslevel.com/services/{service_id}")

        level_info = (
            service.get("serviceStats", {})
            .get("rubric", {})
            .get("level", {})
        )
        level_name = level_info.get("name", "")
        level_index = level_info.get("index", 0)

        # Lower maturity level index = worse
        if level_index == 0:
            severity = AlertSeverity.CRITICAL
        elif level_index == 1:
            severity = AlertSeverity.HIGH
        elif level_index == 2:
            severity = AlertSeverity.WARNING
        else:
            severity = AlertSeverity.INFO

        return AlertDto(
            id=service_id,
            name=f"{name}: {failing_checks}/{total_checks} checks failing",
            severity=severity,
            status=AlertStatus.FIRING,
            lastReceived=datetime.datetime.utcnow().isoformat(),
            description=description or f"Service {name} has {failing_checks} failing checks out of {total_checks}",
            source=["opslevel"],
            url=url,
            labels={
                "service_id": service_id,
                "service_name": name,
                "failing_checks": str(failing_checks),
                "total_checks": str(total_checks),
                "maturity_level": level_name,
            },
            fingerprint=service_id,
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """Format an OpsLevel webhook payload into an AlertDto."""
        # OpsLevel webhooks send check result events
        check = event.get("check", {})
        service = event.get("service", {})
        result = event.get("result", "failed")

        check_id = check.get("id", "unknown")
        check_name = check.get("name", "Unknown Check")
        check_category = check.get("category", "general").lower()
        service_id = service.get("id", "unknown")
        service_name = service.get("name", "Unknown Service")
        service_url = service.get("htmlUrl", "")

        category_severity_map = {
            "security": AlertSeverity.CRITICAL,
            "reliability": AlertSeverity.HIGH,
            "performance": AlertSeverity.HIGH,
            "quality": AlertSeverity.WARNING,
            "custom": AlertSeverity.WARNING,
            "general": AlertSeverity.INFO,
        }
        severity = category_severity_map.get(check_category, AlertSeverity.WARNING)

        status_map = {
            "failed": AlertStatus.FIRING,
            "passed": AlertStatus.RESOLVED,
        }
        status = status_map.get(result, AlertStatus.FIRING)

        alert_id = f"{service_id}:{check_id}"

        return AlertDto(
            id=alert_id,
            name=f"{service_name}: {check_name}",
            severity=severity,
            status=status,
            lastReceived=datetime.datetime.utcnow().isoformat(),
            description=event.get("message", f"Check '{check_name}' {result} for service {service_name}"),
            source=["opslevel"],
            url=service_url,
            labels={
                "service_id": service_id,
                "service_name": service_name,
                "check_id": check_id,
                "check_name": check_name,
                "check_category": check_category,
                "result": result,
            },
            fingerprint=alert_id,
        )
