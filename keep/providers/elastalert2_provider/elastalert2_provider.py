"""
ElastAlert2Provider integrates Keep with ElastAlert2 — an alerting framework
for Elasticsearch. Supports pulling active alerts and receiving webhook notifications.
Reference: https://elastalert2.readthedocs.io/en/latest/
"""

import dataclasses
import logging
from datetime import datetime, timezone

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class ElastAlert2ProviderAuthConfig:
    """
    ElastAlert2 provider authentication configuration.
    ElastAlert2 exposes a REST API when started with --http-port flag.
    Reference: https://elastalert2.readthedocs.io/en/latest/elastalert_server.html
    """

    base_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "ElastAlert2 server base URL",
            "hint": "e.g. http://elastalert2:3030 (default port is 3030)",
        }
    )
    api_key: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "API key for ElastAlert2 server (if authentication is enabled)",
            "sensitive": True,
        },
    )
    verify_ssl: bool = dataclasses.field(
        default=True,
        metadata={
            "required": False,
            "description": "Verify SSL certificate (default: true)",
        },
    )


class ElastAlert2Provider(BaseProvider):
    """
    Pull rule status and triggered alerts from ElastAlert2 into Keep,
    or receive real-time alerts via ElastAlert2's HTTP alerter.
    """

    PROVIDER_DISPLAY_NAME = "ElastAlert2"
    PROVIDER_CATEGORY = ["Monitoring", "Logging"]
    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="api:read",
            description="Required to read rules and alert status from ElastAlert2",
            mandatory=True,
            mandatory_for_webhook=False,
            documentation_url="https://elastalert2.readthedocs.io/en/latest/",
            alias="ElastAlert2 API Access",
        ),
        ProviderScope(
            name="webhook:receive",
            description="Required to receive real-time alert webhooks from ElastAlert2",
            mandatory=False,
            mandatory_for_webhook=True,
            documentation_url="https://elastalert2.readthedocs.io/en/latest/alerts.html#http-post",
            alias="HTTP POST Alerter",
        ),
    ]

    SEVERITY_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "warn": AlertSeverity.WARNING,
        "medium": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
        "debug": AlertSeverity.LOW,
        # ElastAlert2 priority levels
        "1": AlertSeverity.CRITICAL,
        "2": AlertSeverity.HIGH,
        "3": AlertSeverity.WARNING,
        "4": AlertSeverity.INFO,
    }

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ElastAlert2ProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    @property
    def __headers(self):
        headers = {"Content-Type": "application/json"}
        if self.authentication_config.api_key:
            headers["Authorization"] = f"Bearer {self.authentication_config.api_key}"
        return headers

    @property
    def __base(self):
        return self.authentication_config.base_url.rstrip("/")

    def _get(self, endpoint: str) -> dict | list:
        url = f"{self.__base}{endpoint}"
        response = requests.get(
            url,
            headers=self.__headers,
            verify=self.authentication_config.verify_ssl,
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {scope.name: "Invalid" for scope in self.PROVIDER_SCOPES}
        try:
            # ElastAlert2 REST API - list rules endpoint
            self._get("/")
            scopes["api:read"] = True
        except Exception as e:
            scopes["api:read"] = str(e)
        # Webhook scope is external
        scopes["webhook:receive"] = True
        return scopes

    def get_alerts(self) -> list[AlertDto]:
        """
        Fetch rules with error / silenced status from ElastAlert2.
        ElastAlert2 doesn't natively expose triggered alert history via REST,
        but we can pull rule error statuses and any running error state.
        """
        alerts = []
        try:
            # GET /rules returns all configured rules
            data = self._get("/rules")
            rules = data if isinstance(data, list) else data.get("rules", [])

            for rule in rules:
                # Only surface rules that have errors or are in alert state
                if rule.get("is_enabled") and rule.get("last_error"):
                    alerts.append(self._format_rule_error_alert(rule))
        except Exception:
            self.logger.exception("Failed to fetch rules from ElastAlert2")

        return alerts

    def _format_rule_error_alert(self, rule: dict) -> AlertDto:
        return AlertDto(
            id=f"rule-error-{rule.get('name', 'unknown')}",
            name=f"ElastAlert2 Rule Error: {rule.get('name', 'Unknown Rule')}",
            status=AlertStatus.FIRING,
            severity=AlertSeverity.HIGH,
            description=rule.get("last_error", "Rule has encountered an error"),
            source=["elastalert2"],
            rule_name=rule.get("name"),
            payload=rule,
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "ElastAlert2Provider" = None
    ) -> AlertDto:
        """
        Format an ElastAlert2 HTTP POST alerter payload into Keep AlertDto.
        Configure ElastAlert2 rule with http_post alerter pointing to Keep.

        Example rule snippet:
            alert: post
            http_post_url: https://<keep>/alerts/event/elastalert2
            http_post_payload:
              alert_name: "%(rule_name)s"
              message: "%(message)s"
              num_hits: "%(num_hits)s"
              timestamp: "@timestamp"
        """
        logger = logging.getLogger(__name__)
        logger.info("Formatting ElastAlert2 alert webhook payload")

        # ElastAlert2 sends the matched document fields + metadata
        name = (
            event.get("alert_name")
            or event.get("rule_name")
            or event.get("name")
            or "ElastAlert2 Alert"
        )

        description = (
            event.get("message")
            or event.get("body")
            or event.get("alert_text")
            or event.get("alert_info")
            or ""
        )

        raw_severity = (
            event.get("severity")
            or event.get("priority")
            or event.get("level")
            or "warning"
        )
        severity = ElastAlert2Provider.SEVERITY_MAP.get(
            str(raw_severity).lower(), AlertSeverity.WARNING
        )

        # Timestamps — ElastAlert2 typically includes @timestamp from the matched doc
        raw_ts = (
            event.get("@timestamp")
            or event.get("timestamp")
            or event.get("alert_time")
        )
        last_received = None
        if raw_ts:
            for fmt in (
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
            ):
                try:
                    last_received = datetime.strptime(raw_ts, fmt).replace(tzinfo=timezone.utc).isoformat()
                    break
                except Exception:
                    continue
            if not last_received:
                last_received = str(raw_ts)

        num_hits = event.get("num_hits") or event.get("num_matches")

        return AlertDto(
            id=str(event.get("id") or f"{name}-{last_received or ''}"),
            name=name,
            status=AlertStatus.FIRING,
            severity=severity,
            description=description,
            lastReceived=last_received,
            source=["elastalert2"],
            num_hits=num_hits,
            index=event.get("_index"),
            rule_name=event.get("rule_name") or event.get("alert_name"),
            payload=event,
        )


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(tenant_id="keeptest", workflow_id="test")
    config = ProviderConfig(
        authentication={
            "base_url": os.environ.get("ELASTALERT2_URL", "http://localhost:3030"),
            "api_key": os.environ.get("ELASTALERT2_API_KEY", ""),
            "verify_ssl": False,
        }
    )
    provider = ElastAlert2Provider(context_manager, "elastalert2-test", config)
    print("Validating scopes:", provider.validate_scopes())
    alerts = provider.get_alerts()
    print(f"Found {len(alerts)} alerts")
    for a in alerts:
        print(a)
