"""
Apache SkyWalking provider for Keep.

SkyWalking is a distributed tracing, APM (Application Performance Management),
and observability platform for microservices, cloud-native, and container-based
architectures. It provides real-time monitoring, tracing, alerting, and topology
mapping via a GraphQL API and webhook alerting.

Integration modes:
  1. Pull  — queries the SkyWalking OAP GraphQL API for current alarm records.
  2. Webhook (Push) — receives alarm notifications sent by SkyWalking's webhook
     alert hook (POST JSON payload to the Keep webhook URL).

References:
  https://skywalking.apache.org/docs/main/next/en/api/query-protocol/
  https://skywalking.apache.org/docs/main/next/en/api/alarm-hook/
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
    """Authentication configuration for Apache SkyWalking."""

    oap_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "SkyWalking OAP server URL",
            "hint": "e.g. http://skywalking-oap:12800",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    token: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "SkyWalking authentication token (if token-based auth is enabled)",
            "sensitive": True,
        },
        default=None,
    )


class SkywalkingProvider(BaseProvider):
    """Pull current SkyWalking alarms and receive webhook alarm notifications."""

    # Webhook (push) support — SkyWalking can POST alarms to an HTTP endpoint
    webhook_description = (
        "Configure SkyWalking to forward alarm notifications to Keep via its built-in "
        "alarm webhook hook."
    )
    webhook_template = ""
    webhook_markdown = """
To send alarms from SkyWalking to Keep via webhook:

1. Open `alarm-settings.yml` in your SkyWalking OAP server configuration directory.
2. Add a `webhooks` section at the bottom of the file (or append to an existing one):
   ```yaml
   webhooks:
     - url: {keep_webhook_api_url}
       method: POST
       headers:
         x-api-key: {api_key}
   ```
3. Restart the SkyWalking OAP server.
4. When any configured alarm rule fires, SkyWalking will POST the alarm payload to Keep.
"""

    PROVIDER_DISPLAY_NAME = "Apache SkyWalking"
    PROVIDER_TAGS = ["alert", "monitoring", "apm"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_ICON = "https://skywalking.apache.org/favicon.ico"

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connectivity",
            description="Can reach the SkyWalking OAP GraphQL endpoint",
            mandatory=True,
            alias="Connectivity",
        )
    ]

    FINGERPRINT_FIELDS = ["id"]

    # SkyWalking uses integer scope IDs; severity is derived from the rule name
    # or the message text — there is no native numeric severity in SkyWalking alarms.
    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "warn": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
    }

    # SkyWalking alarm messages contain the service/instance/endpoint name.
    # The status is either firing (new) or resolved.
    STATUS_MAP = {
        True: AlertStatus.RESOLVED,
        False: AlertStatus.FIRING,
    }

    # GraphQL query used to fetch recent alarm records
    _ALARM_GRAPHQL_QUERY = """
query GetAlarms($duration: Duration!, $scope: Scope, $keyword: String, $paging: Pagination!) {
  getAlarm(duration: $duration, scope: $scope, keyword: $keyword, paging: $paging) {
    items {
      id
      message
      startTime
      scope
      scopeId
      name
    }
    total
  }
}
"""

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = SkywalkingProviderAuthConfig(
            **self.config.authentication
        )

    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        token = self.authentication_config.token
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _graphql_url(self) -> str:
        base = str(self.authentication_config.oap_url).rstrip("/")
        return f"{base}/graphql"

    def validate_scopes(self) -> dict[str, bool | str]:
        """Check connectivity to the SkyWalking OAP GraphQL endpoint."""
        try:
            now = datetime.datetime.utcnow()
            start = now - datetime.timedelta(minutes=5)
            payload = {
                "query": self._ALARM_GRAPHQL_QUERY,
                "variables": {
                    "duration": {
                        "start": start.strftime("%Y-%m-%d %H%M"),
                        "end": now.strftime("%Y-%m-%d %H%M"),
                        "step": "MINUTE",
                    },
                    "paging": {"pageNum": 1, "pageSize": 1},
                },
            }
            response = requests.post(
                self._graphql_url(),
                headers=self._get_headers(),
                json=payload,
                timeout=10,
            )
            if response.status_code == 200:
                return {"connectivity": True}
            return {
                "connectivity": f"HTTP {response.status_code}: {response.text[:200]}"
            }
        except Exception as e:
            return {"connectivity": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        """Pull current alarm records from the SkyWalking OAP GraphQL API."""
        now = datetime.datetime.utcnow()
        # Pull alarms from the last hour
        start = now - datetime.timedelta(hours=1)
        payload = {
            "query": self._ALARM_GRAPHQL_QUERY,
            "variables": {
                "duration": {
                    "start": start.strftime("%Y-%m-%d %H%M"),
                    "end": now.strftime("%Y-%m-%d %H%M"),
                    "step": "MINUTE",
                },
                "paging": {"pageNum": 1, "pageSize": 100},
            },
        }
        try:
            response = requests.post(
                self._graphql_url(),
                headers=self._get_headers(),
                json=payload,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            self.logger.error(f"SkyWalking: failed to fetch alarms: {e}")
            return []

        items = (
            data.get("data", {}).get("getAlarm", {}).get("items") or []
        )
        return [self._format_alarm_record(item) for item in items]

    def _format_alarm_record(self, item: dict) -> AlertDto:
        """Convert a SkyWalking alarm record into an AlertDto."""
        message = item.get("message", "")
        scope = item.get("scope", "")
        name = item.get("name", scope)
        start_time_ms = item.get("startTime")

        # Derive severity from message keywords
        severity = AlertSeverity.HIGH  # default for SkyWalking alarms
        msg_lower = message.lower()
        for kw, sev in self.SEVERITIES_MAP.items():
            if kw in msg_lower:
                severity = sev
                break

        last_received = None
        if start_time_ms:
            try:
                last_received = datetime.datetime.utcfromtimestamp(
                    int(start_time_ms) / 1000
                ).isoformat() + "Z"
            except Exception:
                last_received = None

        return AlertDto(
            id=item.get("id", ""),
            name=name,
            description=message,
            severity=severity,
            status=AlertStatus.FIRING,
            lastReceived=last_received,
            source=["skywalking"],
            labels={
                "scope": scope,
                "scopeId": str(item.get("scopeId", "")),
                "name": name,
            },
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a SkyWalking webhook alarm payload into AlertDto(s).

        SkyWalking sends a JSON array of alarm messages when its webhook hook fires.
        Each element has fields: scopeId, scope, name, id0, id1, ruleName,
        alarmMessage, startTime, tags, events.
        """
        # SkyWalking posts an array at the top level
        if isinstance(event, list):
            return [
                SkywalkingProvider._parse_webhook_alarm(item) for item in event
            ]
        # Sometimes wrapped in a key
        if "alarms" in event:
            return [
                SkywalkingProvider._parse_webhook_alarm(item)
                for item in event["alarms"]
            ]
        return SkywalkingProvider._parse_webhook_alarm(event)

    @staticmethod
    def _parse_webhook_alarm(alarm: dict) -> AlertDto:
        scope = alarm.get("scope", "")
        name = alarm.get("name", scope)
        rule_name = alarm.get("ruleName", "")
        message = alarm.get("alarmMessage", alarm.get("message", ""))
        start_time_ms = alarm.get("startTime")
        tags = alarm.get("tags", [])  # list of {"key": ..., "value": ...}

        # Build labels from tags
        labels: dict = {tag["key"]: tag["value"] for tag in tags if "key" in tag}
        labels["scope"] = scope
        labels["ruleName"] = rule_name
        if alarm.get("id0"):
            labels["id0"] = str(alarm["id0"])
        if alarm.get("id1"):
            labels["id1"] = str(alarm["id1"])

        # Derive severity from rule name or message
        severity = AlertSeverity.HIGH
        combined = (rule_name + " " + message).lower()
        severity_map = {
            "critical": AlertSeverity.CRITICAL,
            "error": AlertSeverity.HIGH,
            "warning": AlertSeverity.WARNING,
            "warn": AlertSeverity.WARNING,
            "info": AlertSeverity.INFO,
        }
        for kw, sev in severity_map.items():
            if kw in combined:
                severity = sev
                break

        last_received = None
        if start_time_ms:
            try:
                last_received = datetime.datetime.utcfromtimestamp(
                    int(start_time_ms) / 1000
                ).isoformat() + "Z"
            except Exception:
                last_received = None

        return AlertDto(
            id=alarm.get("id", rule_name),
            name=name or rule_name,
            description=message,
            severity=severity,
            status=AlertStatus.FIRING,
            lastReceived=last_received,
            source=["skywalking"],
            labels=labels,
        )
