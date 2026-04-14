"""
Apache SkyWalking provider for Keep.

SkyWalking is an open-source APM (Application Performance Monitoring) tool
for distributed systems. This provider connects to SkyWalking's GraphQL API
to pull alerts/alarms, service topology, and metrics data.

See: https://github.com/apache/skywalking
     https://skywalking.apache.org/docs/main/latest/en/api/query-protocol/
"""

import dataclasses
import datetime
import logging
import typing

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider, ProviderHealthMixin
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus


logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SkywalkingProviderAuthConfig:
    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SkyWalking OAP server host (e.g., http://localhost:12800)",
            "config_main_group": "authentication",
        },
    )
    username: str | None = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SkyWalking username (if authentication is enabled)",
            "config_main_group": "authentication",
        },
    )
    password: str | None = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "SkyWalking password (if authentication is enabled)",
            "sensitive": True,
            "config_main_group": "authentication",
        },
    )


class SkywalkingProvider(BaseProvider, ProviderHealthMixin):
    """Pull alerts and topology data from Apache SkyWalking."""

    PROVIDER_DISPLAY_NAME = "Apache SkyWalking"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert", "topology"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read alarms/alerts from SkyWalking",
            mandatory=True,
            alias="Read Alerts",
        ),
        ProviderScope(
            name="read_topology",
            description="Read service topology from SkyWalking",
            mandatory=False,
            alias="Read Topology",
        ),
    ]

    FINGERPRINT_FIELDS = ["id", "name"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._host = self.authentication_config.host.rstrip("/")

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = SkywalkingProviderAuthConfig(
            **self.config.authentication
        )

    def _build_graphql_url(self) -> str:
        return f"{self._host}/graphql"

    def _graphql_request(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL request against the SkyWalking OAP server."""
        url = self._build_graphql_url()
        headers = {"Content-Type": "application/json"}

        if self.authentication_config.username and self.authentication_config.password:
            headers["Authorization"] = requests.auth._basic_auth_str(
                self.authentication_config.username,
                self.authentication_config.password,
            )

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=30
            )
            response.raise_for_status()
            data = response.json()
            if "errors" in data:
                raise ProviderException(
                    f"SkyWalking GraphQL errors: {data['errors']}"
                )
            return data.get("data", {})
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Failed to connect to SkyWalking: {e}")

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {}
        try:
            # Test connection by querying version
            data = self._graphql_request("query { version }")
            scopes["read_alerts"] = True
        except Exception as e:
            scopes["read_alerts"] = str(e)

        try:
            data = self._graphql_request(
                """query { listServices(duration: {start: "2024-01-01", end: "2024-01-02", step: DAY}) { services { id name } } }"""
            )
            scopes["read_topology"] = True
        except Exception as e:
            scopes["read_topology"] = str(e)

        return scopes

    def _get_alerts(self) -> list[AlertDto]:
        """Fetch alarms from SkyWalking."""
        now = datetime.datetime.utcnow()
        one_day_ago = now - datetime.timedelta(days=1)

        query = """
        query getAlarms($keyword: String, $scope: Scope, $duration: Duration!, $paging: Pagination!) {
            getAlarm(keyword: $keyword, scope: $scope, duration: $duration, paging: $paging) {
                msgs {
                    id
                    message
                    startTime
                    scope {
                        service
                        serviceInstance
                        endpoint
                    }
                    tags {
                        key
                        value
                    }
                }
                total
            }
        }
        """

        variables = {
            "duration": {
                "start": one_day_ago.strftime("%Y-%m-%d %H%M"),
                "end": now.strftime("%Y-%m-%d %H%M"),
                "step": "MINUTE",
            },
            "paging": {"pageNum": 1, "pageSize": 100},
        }

        try:
            data = self._graphql_request(query, variables)
        except Exception as e:
            logger.error(f"Failed to fetch SkyWalking alarms: {e}")
            return []

        alarms = data.get("getAlarm", {}).get("msgs", [])
        alerts = []

        for alarm in alarms:
            scope = alarm.get("scope", {})
            tags = {
                t["key"]: t["value"]
                for t in alarm.get("tags", [])
                if t.get("key")
            }

            # Map SkyWalking severity from tags if available
            severity = self._map_severity(tags.get("level", "warning"))

            service_name = scope.get("service", "unknown")
            alert = AlertDto(
                id=str(alarm.get("id", "")),
                name=alarm.get("message", "SkyWalking Alarm"),
                description=alarm.get("message", ""),
                severity=severity,
                status=AlertStatus.FIRING,
                source=["skywalking"],
                service=service_name,
                environment=tags.get("environment", "production"),
                lastReceived=datetime.datetime.utcnow().isoformat(),
                startedAt=(
                    datetime.datetime.fromtimestamp(
                        alarm["startTime"] / 1000
                    ).isoformat()
                    if alarm.get("startTime")
                    else None
                ),
                tags=tags,
                fingerprint=f"skywalking-{alarm.get('id', '')}",
            )
            alerts.append(alert)

        return alerts

    @staticmethod
    def _map_severity(level: str) -> AlertSeverity:
        level_lower = level.lower()
        if level_lower in ("critical", "fatal"):
            return AlertSeverity.CRITICAL
        elif level_lower in ("error", "high"):
            return AlertSeverity.HIGH
        elif level_lower in ("warning", "warn"):
            return AlertSeverity.WARNING
        elif level_lower in ("info", "notice"):
            return AlertSeverity.INFO
        return AlertSeverity.WARNING

    def _get_topology(self) -> dict:
        """Fetch global service topology from SkyWalking."""
        now = datetime.datetime.utcnow()
        one_hour_ago = now - datetime.timedelta(hours=1)

        query = """
        query getGlobalTopology($duration: Duration!) {
            getGlobalTopology(duration: $duration) {
                nodes {
                    id
                    name
                    type
                    isReal
                }
                calls {
                    id
                    source
                    target
                    detectPoints
                }
            }
        }
        """

        variables = {
            "duration": {
                "start": one_hour_ago.strftime("%Y-%m-%d %H%M"),
                "end": now.strftime("%Y-%m-%d %H%M"),
                "step": "MINUTE",
            }
        }

        try:
            data = self._graphql_request(query, variables)
            return data.get("getGlobalTopology", {})
        except Exception as e:
            logger.error(f"Failed to fetch SkyWalking topology: {e}")
            return {}

    @staticmethod
    def _format_alert(
        event: dict,
        provider_instance: typing.Optional["SkywalkingProvider"] = None,
    ) -> AlertDto | list[AlertDto]:
        """Format a SkyWalking webhook event into AlertDto(s)."""
        # SkyWalking webhook sends alarm data directly
        alerts = []
        scope_data = event.get("scope", {})
        tags = {
            t["key"]: t["value"]
            for t in event.get("tags", [])
            if t.get("key")
        }
        severity = SkywalkingProvider._map_severity(tags.get("level", "warning"))
        # scope can be a string (webhook) or dict (GraphQL) — handle both
        if isinstance(scope_data, dict):
            service_name = scope_data.get("service", event.get("name", "unknown"))
        else:
            service_name = event.get("name", "unknown")

        alert = AlertDto(
            id=str(event.get("id", event.get("id0", ""))),
            name=event.get("alarmMessage", event.get("name", "SkyWalking Alarm")),
            description=event.get("alarmMessage", ""),
            severity=severity,
            status=AlertStatus.FIRING,
            source=["skywalking"],
            service=service_name,
            lastReceived=datetime.datetime.utcnow().isoformat(),
            tags=tags,
            fingerprint=f"skywalking-{event.get('id', event.get('id0', ''))}",
        )
        alerts.append(alert)
        return alerts

    @staticmethod
    def webhook_example() -> dict:
        return {
            "scopeId": 1,
            "scope": "SERVICE",
            "name": "service_resp_time_rule",
            "id0": "bWVzaC1zdnI=.1",
            "id1": "",
            "ruleName": "service_resp_time_rule",
            "alarmMessage": "Response time of service mesh-svr is more than 1000ms in 2 minutes.",
            "startTime": 1718025380000,
            "tags": [
                {"key": "level", "value": "WARNING"},
            ],
        }


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG)
    config = ProviderConfig(
        authentication={"host": "http://localhost:12800"},
    )
    context_manager = ContextManager(
        tenant_id="test", workflow_id="test"
    )
    provider = SkywalkingProvider(
        context_manager, provider_id="skywalking-test", config=config
    )
    alerts = provider._get_alerts()
    print(f"Got {len(alerts)} alerts")
