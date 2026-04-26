"""
SkywalkingProvider integrates with Apache SkyWalking, an open-source APM and
observability platform. Keep pulls active alarms via the SkyWalking GraphQL API
and can receive webhook events from SkyWalking alarm webhooks.
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


@pydantic.dataclasses.dataclass
class SkywalkingProviderAuthConfig:
    """
    SkywalkingProviderAuthConfig holds the connection details for Apache SkyWalking.
    """

    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SkyWalking OAP server host (including protocol and port)",
            "hint": "e.g. http://skywalking-oap:12800 — the GraphQL endpoint is at <host>/graphql",
            "sensitive": False,
        },
    )

    token: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Bearer token for SkyWalking authentication (if auth is enabled)",
            "hint": "Set in skywalking-oap-server application.yml under restapi.authentication",
            "sensitive": True,
        },
    )


class SkywalkingProvider(BaseProvider):
    """Pull active alarms from Apache SkyWalking and receive alarm webhook events."""

    PROVIDER_DISPLAY_NAME = "Apache SkyWalking"
    PROVIDER_CATEGORY = ["Monitoring", "APM"]
    PROVIDER_TAGS = ["alert", "apm"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connected",
            description="Can reach the SkyWalking OAP GraphQL endpoint",
            mandatory=True,
            alias="connected",
        ),
    ]

    # SkyWalking alarm scope → human-readable label
    SCOPE_LABELS = {
        "SERVICE": "Service",
        "SERVICE_INSTANCE": "Service Instance",
        "ENDPOINT": "Endpoint",
        "DATABASE_ACCESS": "Database",
        "SERVICE_RELATION": "Service Relation",
        "SERVICE_INSTANCE_RELATION": "Instance Relation",
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """Validate the provider configuration."""
        self.authentication_config = SkywalkingProviderAuthConfig(
            **self.config.authentication
        )

    def __graphql_endpoint(self) -> str:
        host = self.authentication_config.host.rstrip("/")
        return f"{host}/graphql"

    def __get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.authentication_config.token:
            headers["Authorization"] = f"Bearer {self.authentication_config.token}"
        return headers

    def __run_query(self, query: str, variables: Optional[dict] = None) -> dict:
        """Execute a GraphQL query against the SkyWalking OAP server."""
        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables

        response = requests.post(
            self.__graphql_endpoint(),
            headers=self.__get_headers(),
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate connectivity by querying the SkyWalking version."""
        query = """
        query {
            version
        }
        """
        try:
            result = self.__run_query(query)
            if "errors" in result:
                return {"connected": f"GraphQL error: {result['errors'][0].get('message', 'unknown')}"}
            version = result.get("data", {}).get("version", "")
            if version:
                return {"connected": True}
            return {"connected": "Connected but could not determine SkyWalking version"}
        except requests.exceptions.ConnectionError as e:
            return {"connected": f"Connection refused: {e}"}
        except requests.exceptions.HTTPError as e:
            return {"connected": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
        except Exception as e:
            self.logger.error("Error validating SkyWalking scopes: %s", e)
            return {"connected": f"Error: {e}"}

    def _get_alerts(self) -> list[AlertDto]:
        """Pull active alarms from SkyWalking via GraphQL."""
        alerts = []

        # Fetch alarms for the last 30 minutes
        end_time = datetime.datetime.utcnow()
        start_time = end_time - datetime.timedelta(minutes=30)

        query = """
        query GetAlarms($duration: Duration!) {
            getAlarm(condition: {
                duration: $duration
                pageCondition: { pageSize: 100, pageNum: 1 }
            }) {
                msgs {
                    id
                    message
                    startTime
                    scope
                    name
                    id0
                    id1
                    rulesName
                }
            }
        }
        """

        variables = {
            "duration": {
                "start": start_time.strftime("%Y-%m-%d %H%M"),
                "end": end_time.strftime("%Y-%m-%d %H%M"),
                "step": "MINUTE",
            }
        }

        try:
            self.logger.info("Fetching SkyWalking alarms")
            result = self.__run_query(query, variables)

            if "errors" in result:
                self.logger.error("SkyWalking GraphQL error: %s", result["errors"])
                return alerts

            msgs = result.get("data", {}).get("getAlarm", {}).get("msgs", [])
            for alarm in msgs:
                alerts.append(self.__alarm_to_alert(alarm))

        except Exception as e:
            self.logger.error("Error fetching SkyWalking alarms: %s", e)

        return alerts

    def __alarm_to_alert(self, alarm: dict) -> AlertDto:
        """Convert a SkyWalking alarm message to an AlertDto."""
        alarm_id = alarm.get("id", "unknown")
        message = alarm.get("message", "SkyWalking alarm triggered")
        scope = alarm.get("scope", "SERVICE")
        name = alarm.get("name", "")
        rules = alarm.get("rulesName", [])
        start_time_ms = alarm.get("startTime", 0)

        try:
            last_received = datetime.datetime.fromtimestamp(
                int(start_time_ms) / 1000, tz=datetime.timezone.utc
            ).isoformat()
        except (ValueError, TypeError):
            last_received = datetime.datetime.utcnow().isoformat()

        scope_label = self.SCOPE_LABELS.get(scope, scope)
        alert_name = f"[{scope_label}] {name}: {', '.join(rules) if rules else 'alarm'}"

        host = self.authentication_config.host.rstrip("/")
        url = f"{host}/"

        return AlertDto(
            id=f"skywalking-{alarm_id}",
            name=alert_name,
            description=message,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.FIRING,
            lastReceived=last_received,
            source=["skywalking"],
            url=url,
            labels={
                "alarm_id": str(alarm_id),
                "scope": scope,
                "entity_name": name,
                "rules": ", ".join(rules) if isinstance(rules, list) else str(rules),
                "id0": str(alarm.get("id0", "")),
                "id1": str(alarm.get("id1", "")),
            },
            fingerprint=f"skywalking-{alarm_id}",
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format a SkyWalking alarm webhook payload into an AlertDto.

        SkyWalking sends alarm webhooks as a JSON array of alarm objects:
        [
          {
            "scopeId": 1,
            "scope": "SERVICE",
            "name": "consumer-service",
            "id0": "consumer|demo",
            "id1": "",
            "ruleName": "service_resp_time_rule",
            "alarmMessage": "Response time of service consumer-service is more than 1000ms in 3 minutes of last 10 minutes",
            "startTime": 1714100000000,
            "tags": [{"key": "level", "value": "WARNING"}]
          }
        ]

        Keep calls _format_alert per-element, so we receive a single alarm dict.
        """
        scope = event.get("scope", "SERVICE")
        name = event.get("name", "")
        rule_name = event.get("ruleName", "alarm")
        message = event.get("alarmMessage", "SkyWalking alarm triggered")
        start_time_ms = event.get("startTime", 0)
        alarm_id = event.get("id", f"{scope}-{name}-{rule_name}")

        try:
            last_received = datetime.datetime.fromtimestamp(
                int(start_time_ms) / 1000, tz=datetime.timezone.utc
            ).isoformat()
        except (ValueError, TypeError):
            last_received = datetime.datetime.utcnow().isoformat()

        # Extract severity from tags if present
        tags = {t.get("key"): t.get("value") for t in event.get("tags", []) if isinstance(t, dict)}
        level = tags.get("level", "HIGH").upper()

        severity_map = {
            "CRITICAL": AlertSeverity.CRITICAL,
            "HIGH": AlertSeverity.HIGH,
            "WARNING": AlertSeverity.WARNING,
            "LOW": AlertSeverity.LOW,
            "INFO": AlertSeverity.INFO,
        }
        severity = severity_map.get(level, AlertSeverity.HIGH)

        scope_labels = {
            "SERVICE": "Service",
            "SERVICE_INSTANCE": "Service Instance",
            "ENDPOINT": "Endpoint",
            "DATABASE_ACCESS": "Database",
        }
        scope_label = scope_labels.get(scope, scope)
        alert_name = f"[{scope_label}] {name}: {rule_name}"

        return AlertDto(
            id=f"skywalking-{alarm_id}",
            name=alert_name,
            description=message,
            severity=severity,
            status=AlertStatus.FIRING,
            lastReceived=last_received,
            source=["skywalking"],
            labels={
                "scope": scope,
                "entity_name": name,
                "rule_name": rule_name,
                "id0": str(event.get("id0", "")),
                "id1": str(event.get("id1", "")),
                **{f"tag_{k}": v for k, v in tags.items()},
            },
            fingerprint=f"skywalking-{scope}-{name}-{rule_name}",
        )
