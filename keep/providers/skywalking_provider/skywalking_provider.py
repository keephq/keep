"""
Apache SkyWalking Provider is a class that allows to pull alerts from Apache SkyWalking.
"""

import dataclasses
import datetime
import json
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
    SkyWalking authentication configuration.
    """

    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SkyWalking OAP Server URL",
            "hint": "e.g., http://localhost:12800",
        },
    )

    username: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Username for basic auth (optional)",
            "hint": "Leave empty if no authentication required",
        },
    )

    password: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Password for basic auth (optional)",
            "sensitive": True,
            "hint": "Leave empty if no authentication required",
        },
    )


class SkywalkingProvider(BaseProvider):
    """Pull alerts from Apache SkyWalking."""

    PROVIDER_DISPLAY_NAME = "Apache SkyWalking"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is able to query the SkyWalking OAP server",
            mandatory=True,
            alias="Authenticated",
        ),
    ]

    # SkyWalking scopes mapped to Keep alert sources
    SCOPE_MAP = {
        "All": "all",
        "Service": "service",
        "ServiceInstance": "service_instance",
        "Endpoint": "endpoint",
        "Process": "process",
        "ServiceRelation": "service_relation",
        "ServiceInstanceRelation": "service_instance_relation",
        "EndpointRelation": "endpoint_relation",
        "ProcessRelation": "process_relation",
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for SkyWalking provider.
        """
        self.authentication_config = SkywalkingProviderAuthConfig(
            **self.config.authentication
        )
        # Normalize host URL
        host = self.authentication_config.host
        if not host.startswith("http://") and not host.startswith("https://"):
            self.authentication_config.host = f"http://{host}"
        # Remove trailing slash
        self.authentication_config.host = self.authentication_config.host.rstrip("/")

    @property
    def _graphql_url(self) -> str:
        return f"{self.authentication_config.host}/graphql"

    def _get_auth(self) -> Optional[tuple]:
        """Get authentication tuple if credentials are provided."""
        if (
            self.authentication_config.username
            and self.authentication_config.password
        ):
            return (
                self.authentication_config.username,
                self.authentication_config.password,
            )
        return None

    def _execute_graphql(self, query: str, variables: dict = None) -> dict:
        """Execute a GraphQL query against the SkyWalking OAP server."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        auth = self._get_auth()
        headers = {"Content-Type": "application/json"}

        response = requests.post(
            self._graphql_url,
            json=payload,
            headers=headers,
            auth=auth,
            timeout=30,
        )
        response.raise_for_status()

        result = response.json()
        if "errors" in result and result["errors"]:
            error_messages = [e.get("message", str(e)) for e in result["errors"]]
            raise Exception(f"GraphQL errors: {', '.join(error_messages)}")

        return result.get("data", {})

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate that we can connect to the SkyWalking OAP server.
        """
        scopes = {}
        try:
            # Test connection with a simple health check query
            query = """
            query {
                checkHealth {
                    score
                    details
                }
            }
            """
            result = self._execute_graphql(query)
            health = result.get("checkHealth", {})
            score = health.get("score", -1)

            if score == 0:
                scopes["authenticated"] = True
                self.logger.info("SkyWalking connection validated successfully")
            else:
                details = health.get("details", "Unknown health issue")
                scopes["authenticated"] = f"OAP unhealthy (score={score}): {details}"
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to connect to SkyWalking: {e}")
            scopes["authenticated"] = f"Connection failed: {str(e)}"
        except Exception as e:
            self.logger.error(f"Failed to validate SkyWalking scopes: {e}")
            scopes["authenticated"] = str(e)

        return scopes

    def _get_duration(self, hours_back: int = 24) -> dict:
        """
        Get duration object for GraphQL query.
        Uses MINUTE step for better precision.
        """
        now = datetime.datetime.utcnow()
        start = now - datetime.timedelta(hours=hours_back)

        # Format: yyyy-MM-dd HHmm for MINUTE step
        return {
            "start": start.strftime("%Y-%m-%d %H%M"),
            "end": now.strftime("%Y-%m-%d %H%M"),
            "step": "MINUTE",
        }

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull alerts from SkyWalking.
        """
        self.logger.info("Fetching alerts from SkyWalking")

        duration = self._get_duration(hours_back=24)

        query = """
        query getAlarm($duration: Duration!, $paging: Pagination!) {
            getAlarm(duration: $duration, paging: $paging) {
                msgs {
                    startTime
                    recoveryTime
                    scope
                    id
                    name
                    message
                    tags {
                        key
                        value
                    }
                }
            }
        }
        """

        variables = {
            "duration": duration,
            "paging": {"pageNum": 1, "pageSize": 100},
        }

        all_alerts = []
        page_num = 1

        while True:
            variables["paging"]["pageNum"] = page_num

            try:
                result = self._execute_graphql(query, variables)
                alarms = result.get("getAlarm", {}).get("msgs", [])

                if not alarms:
                    break

                for alarm in alarms:
                    alert_dto = self._format_alarm_to_alert(alarm)
                    all_alerts.append(alert_dto)

                # If we got fewer results than page size, we're done
                if len(alarms) < variables["paging"]["pageSize"]:
                    break

                page_num += 1

                # Safety limit
                if page_num > 100:
                    self.logger.warning(
                        "Reached page limit (100), stopping pagination"
                    )
                    break

            except Exception as e:
                self.logger.error(f"Failed to fetch alerts page {page_num}: {e}")
                break

        self.logger.info(f"Fetched {len(all_alerts)} alerts from SkyWalking")
        return all_alerts

    def _format_alarm_to_alert(self, alarm: dict) -> AlertDto:
        """
        Format a SkyWalking alarm message to Keep AlertDto.
        """
        # Convert startTime from milliseconds to datetime
        start_time_ms = alarm.get("startTime", 0)
        start_time = datetime.datetime.utcfromtimestamp(start_time_ms / 1000)

        # Check recovery time to determine status
        recovery_time_ms = alarm.get("recoveryTime")
        if recovery_time_ms and recovery_time_ms > 0:
            status = AlertStatus.RESOLVED
            last_received = datetime.datetime.utcfromtimestamp(
                recovery_time_ms / 1000
            )
        else:
            status = AlertStatus.FIRING
            last_received = start_time

        # Extract tags as a dictionary
        tags_list = alarm.get("tags", [])
        tags = {tag["key"]: tag.get("value", "") for tag in tags_list}

        # Map scope to a readable format
        scope = alarm.get("scope", "All")
        scope_display = self.SCOPE_MAP.get(scope, scope.lower())

        # SkyWalking doesn't have explicit severity in alarms,
        # default to WARNING (users can configure rules with different severities)
        severity = AlertSeverity.WARNING

        # Check if severity is in tags
        if "severity" in tags:
            severity_str = tags["severity"].lower()
            if severity_str in ("critical", "error"):
                severity = AlertSeverity.CRITICAL
            elif severity_str in ("high",):
                severity = AlertSeverity.HIGH
            elif severity_str in ("warning", "warn"):
                severity = AlertSeverity.WARNING
            elif severity_str in ("info", "low"):
                severity = AlertSeverity.INFO

        return AlertDto(
            id=alarm.get("id"),
            name=alarm.get("name", "SkyWalking Alert"),
            status=status,
            severity=severity,
            lastReceived=last_received.isoformat(),
            message=alarm.get("message", ""),
            description=alarm.get("message", ""),
            source=["skywalking"],
            scope=scope_display,
            tags=tags,
            startedAt=start_time.isoformat(),
            fingerprint=f"skywalking-{alarm.get('id', '')}",
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format a webhook event from SkyWalking to AlertDto.
        SkyWalking can send alerts via webhook when configured.

        Expected webhook payload format (from alarm-settings.yml webhooks config):
        {
            "scopeId": 1,
            "scope": "Service",
            "name": "service-name",
            "id0": "...",
            "id1": "",
            "ruleName": "rule-name",
            "alarmMessage": "message",
            "startTime": 1234567890,
            "tags": [{"key": "k", "value": "v"}]
        }
        """
        # Handle list of alarms (SkyWalking sends array)
        if isinstance(event, list):
            # Return first alarm formatted, or handle multiple
            if event:
                event = event[0]
            else:
                return AlertDto(
                    id="unknown",
                    name="Empty SkyWalking Alert",
                    source=["skywalking"],
                )

        # Extract fields from webhook payload
        alarm_id = event.get("id0", event.get("id", "unknown"))
        name = event.get("name", event.get("ruleName", "SkyWalking Alert"))
        message = event.get("alarmMessage", event.get("message", ""))
        scope = event.get("scope", "Service")
        start_time_ms = event.get("startTime", 0)

        # Convert timestamp
        if start_time_ms:
            start_time = datetime.datetime.utcfromtimestamp(start_time_ms / 1000)
            last_received = start_time.isoformat()
        else:
            last_received = datetime.datetime.utcnow().isoformat()

        # Extract tags
        tags_list = event.get("tags", [])
        if isinstance(tags_list, list):
            tags = {
                tag.get("key", ""): tag.get("value", "")
                for tag in tags_list
                if isinstance(tag, dict)
            }
        else:
            tags = {}

        # Map scope
        scope_map = SkywalkingProvider.SCOPE_MAP
        scope_display = scope_map.get(scope, scope.lower() if scope else "service")

        # Determine severity from tags or default
        severity = AlertSeverity.WARNING
        if "severity" in tags:
            severity_str = tags["severity"].lower()
            if severity_str in ("critical", "error"):
                severity = AlertSeverity.CRITICAL
            elif severity_str in ("high",):
                severity = AlertSeverity.HIGH
            elif severity_str in ("warning", "warn"):
                severity = AlertSeverity.WARNING
            elif severity_str in ("info", "low"):
                severity = AlertSeverity.INFO

        return AlertDto(
            id=alarm_id,
            name=name,
            status=AlertStatus.FIRING,
            severity=severity,
            lastReceived=last_received,
            message=message,
            description=message,
            source=["skywalking"],
            scope=scope_display,
            tags=tags,
            ruleName=event.get("ruleName"),
            fingerprint=f"skywalking-{alarm_id}",
        )

    @staticmethod
    def parse_event_raw_body(raw_body: bytes | dict) -> dict:
        """Parse raw webhook body from SkyWalking."""
        if isinstance(raw_body, dict):
            return raw_body
        if isinstance(raw_body, list):
            return raw_body
        try:
            return json.loads(raw_body)
        except json.JSONDecodeError:
            return {"raw": raw_body.decode("utf-8") if isinstance(raw_body, bytes) else str(raw_body)}


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    host = os.environ.get("SKYWALKING_HOST", "http://localhost:12800")

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    config = ProviderConfig(
        authentication={"host": host},
    )

    provider = SkywalkingProvider(
        context_manager=context_manager,
        provider_id="skywalking-test",
        config=config,
    )

    # Test scopes validation
    scopes = provider.validate_scopes()
    print(f"Scopes: {scopes}")

    # Test fetching alerts
    if scopes.get("authenticated") is True:
        alerts = provider._get_alerts()
        print(f"Alerts: {alerts}")
