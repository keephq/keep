"""
SigNoz Provider is a class that allows to pull alerts from SigNoz
and also receive alert webhooks from SigNoz.
"""

import dataclasses
import datetime
import logging
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SignozProviderAuthConfig:
    """
    SigNoz authentication configuration.
    """

    signoz_access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SigNoz API Key (Access Token)",
            "hint": "The API key for authenticating with SigNoz. Generate from Settings > API Keys.",
            "sensitive": True,
        },
    )
    signoz_endpoint: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "SigNoz API Endpoint",
            "hint": "e.g. https://signoz.example.com or http://localhost:3301",
            "validation": "any_http_url",
        },
    )


class SignozProvider(BaseProvider):
    """Pull alerts from SigNoz or receive them via webhook."""

    PROVIDER_DISPLAY_NAME = "SigNoz"
    PROVIDER_CATEGORY = ["Monitoring", "Developer Tools"]
    PROVIDER_TAGS = ["alert"]
    FINGERPRINT_FIELDS = ["id"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated and can access SigNoz alerts API",
            mandatory=True,
            alias="Alerts Reader",
        ),
    ]

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "firing": AlertStatus.FIRING,
        "inactive": AlertStatus.RESOLVED,
        "pending": AlertStatus.PENDING,
        "nodata": AlertStatus.PENDING,
        "disabled": AlertStatus.SUPPRESSED,
    }

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for SigNoz provider.
        """
        self.authentication_config = SignozProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate provider scopes by making a test API call.
        """
        try:
            response = requests.get(
                f"{self.authentication_config.signoz_endpoint}/api/v1/rules",
                headers=self.__get_headers(),
                timeout=10,
            )
            if response.ok:
                return {"authenticated": True}
            elif response.status_code in (401, 403):
                return {
                    "authenticated": "Authentication failed. Please check your API key."
                }
            else:
                return {
                    "authenticated": f"Failed to connect to SigNoz: HTTP {response.status_code}"
                }
        except requests.exceptions.ConnectionError:
            return {
                "authenticated": "Failed to connect to SigNoz. Please check your endpoint URL."
            }
        except Exception as e:
            return {"authenticated": str(e)}

    def __get_headers(self) -> dict:
        """
        Build authentication headers for SigNoz API.
        """
        return {
            "SIGNOZ-API-KEY": self.authentication_config.signoz_access_token,
            "Content-Type": "application/json",
        }

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull alerts from SigNoz by fetching alert rules and their states.
        """
        self.logger.info("Fetching alert rules from SigNoz")
        alerts_dto = []

        try:
            # Fetch alert rules with their current states
            rules_response = requests.get(
                f"{self.authentication_config.signoz_endpoint}/api/v1/rules",
                headers=self.__get_headers(),
                timeout=30,
            )
            rules_response.raise_for_status()
            rules_data = rules_response.json()

            if rules_data.get("status") != "success":
                self.logger.warning(
                    "SigNoz rules API returned non-success status",
                    extra={"response": rules_data},
                )
                return alerts_dto

            rules = rules_data.get("data", {}).get("rules", [])
            self.logger.info(f"Fetched {len(rules)} alert rules from SigNoz")

            for rule in rules:
                try:
                    alert_dto = self._format_rule(rule)
                    if alert_dto:
                        alerts_dto.append(alert_dto)
                except Exception:
                    self.logger.exception(
                        "Failed to format SigNoz alert rule",
                        extra={"rule_id": rule.get("id")},
                    )
                    continue

        except requests.exceptions.RequestException as e:
            self.logger.error(
                "Failed to fetch alert rules from SigNoz",
                extra={"error": str(e)},
            )
            raise

        # Also fetch currently triggered alerts
        try:
            alerts_response = requests.get(
                f"{self.authentication_config.signoz_endpoint}/api/v1/alerts",
                headers=self.__get_headers(),
                timeout=30,
            )
            alerts_response.raise_for_status()
            alerts_data = alerts_response.json()

            if alerts_data.get("status") == "success":
                triggered_alerts = alerts_data.get("data", {}).get("rules", [])
                self.logger.info(
                    f"Fetched {len(triggered_alerts)} triggered alerts from SigNoz"
                )

                for triggered in triggered_alerts:
                    try:
                        alert_dto = self._format_triggered_alert(triggered)
                        if alert_dto:
                            alerts_dto.append(alert_dto)
                    except Exception:
                        self.logger.exception(
                            "Failed to format SigNoz triggered alert",
                            extra={"alert_id": triggered.get("id")},
                        )
                        continue
        except requests.exceptions.RequestException as e:
            self.logger.warning(
                "Failed to fetch triggered alerts from SigNoz (non-fatal)",
                extra={"error": str(e)},
            )

        self.logger.info(
            f"Total alerts fetched from SigNoz: {len(alerts_dto)}"
        )
        return alerts_dto

    def _format_rule(self, rule: dict) -> Optional[AlertDto]:
        """
        Format a SigNoz alert rule into a Keep AlertDto.

        SigNoz rule structure (from GET /api/v1/rules):
        {
            "id": "1",
            "state": "firing|inactive|pending|nodata|disabled",
            "alert": "Alert Name",
            "alertType": "METRIC_BASED_ALERT",
            "description": "...",
            "labels": {"severity": "warning", ...},
            "annotations": {"description": "..."},
            "disabled": false,
            "createAt": "2024-01-01T00:00:00Z",
            "createBy": "admin@example.com",
            "updateAt": "2024-01-01T00:00:00Z",
            "updateBy": "admin@example.com"
        }
        """
        rule_id = str(rule.get("id", ""))
        state = rule.get("state", "inactive")
        alert_name = rule.get("alert", rule.get("alertName", ""))
        alert_type = rule.get("alertType", "")
        description = rule.get("description", "")
        labels = rule.get("labels", {})
        annotations = rule.get("annotations", {})
        disabled = rule.get("disabled", False)

        if disabled:
            state = "disabled"

        # Skip inactive rules that have never fired to reduce noise
        if state == "inactive":
            return None

        # Map severity
        severity_label = labels.get("severity", "").lower()
        severity = self.SEVERITIES_MAP.get(severity_label, AlertSeverity.INFO)

        # Map status
        status = self.STATUS_MAP.get(state, AlertStatus.FIRING)

        # Get description from annotations if not in the rule itself
        if not description:
            description = annotations.get("description", annotations.get("summary", ""))

        # Build the alert URL if possible
        url = None
        endpoint = str(self.authentication_config.signoz_endpoint)
        if rule_id:
            url = f"{endpoint}/alerts/{rule_id}"

        last_received = (
            rule.get("updateAt")
            or rule.get("createAt")
            or datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        )

        return AlertDto(
            id=rule_id,
            name=alert_name,
            status=status,
            severity=severity,
            lastReceived=last_received,
            description=description,
            source=["signoz"],
            labels=labels,
            annotations=annotations,
            alert_type=alert_type,
            url=url,
        )

    def _format_triggered_alert(self, alert: dict) -> Optional[AlertDto]:
        """
        Format a SigNoz triggered alert into a Keep AlertDto.

        SigNoz triggered alert structure (from GET /api/v1/alerts):
        {
            "labels": {"alertname": "...", "severity": "warning", ...},
            "annotations": {"description": "..."},
            "state": "firing",
            "name": "Alert Name",
            "id": 1
        }
        """
        alert_id = str(alert.get("id", ""))
        state = alert.get("state", "firing")
        name = alert.get("name", "")
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})

        if not name:
            name = labels.get("alertname", "SigNoz Alert")

        # Map severity
        severity_label = labels.get("severity", "").lower()
        severity = self.SEVERITIES_MAP.get(severity_label, AlertSeverity.INFO)

        # Map status
        status = self.STATUS_MAP.get(state, AlertStatus.FIRING)

        # Get description from annotations
        description = annotations.get("description", annotations.get("summary", ""))

        # Build the alert URL if possible
        url = None
        endpoint = str(self.authentication_config.signoz_endpoint)
        if alert_id:
            url = f"{endpoint}/alerts/{alert_id}"

        return AlertDto(
            id=f"triggered-{alert_id}",
            name=name,
            status=status,
            severity=severity,
            lastReceived=datetime.datetime.now(
                tz=datetime.timezone.utc
            ).isoformat(),
            description=description,
            source=["signoz"],
            labels=labels,
            annotations=annotations,
            url=url,
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a SigNoz webhook alert event into Keep AlertDto(s).

        SigNoz can send webhook notifications via its alert channels.
        The webhook payload typically contains alert details from
        the SigNoz alertmanager integration.
        """
        # Handle SigNoz alertmanager-style webhook payloads
        alerts = event.get("alerts", [event])
        formatted_alerts = []

        for alert in alerts:
            labels = alert.get("labels", {})
            annotations = alert.get("annotations", {})
            status_str = alert.get("status", alert.get("state", "firing")).lower()

            alert_name = (
                labels.get("alertname")
                or alert.get("name")
                or alert.get("alert")
                or "SigNoz Alert"
            )

            # Map severity
            severity_label = labels.get("severity", "").lower()
            severity = SignozProvider.SEVERITIES_MAP.get(
                severity_label, AlertSeverity.INFO
            )

            # Map status
            status = SignozProvider.STATUS_MAP.get(status_str, AlertStatus.FIRING)

            # Get description
            description = annotations.get(
                "description", annotations.get("summary", "")
            )

            # Extract fingerprint if available
            fingerprint = alert.get("fingerprint", "")

            # Extract timing info
            starts_at = alert.get("startsAt", "")
            ends_at = alert.get("endsAt", "")

            # Generator URL
            url = alert.get("generatorURL", alert.get("url", None))

            alert_dto = AlertDto(
                id=alert.get("id", fingerprint or alert_name),
                fingerprint=fingerprint or None,
                name=alert_name,
                status=status,
                severity=severity,
                lastReceived=datetime.datetime.now(
                    tz=datetime.timezone.utc
                ).isoformat(),
                description=description,
                source=["signoz"],
                labels=labels,
                annotations=annotations,
                url=url,
                startsAt=starts_at or None,
                endsAt=ends_at or None,
            )

            # Enrich with extra labels
            for label_key, label_value in labels.items():
                if getattr(alert_dto, label_key, None) is None:
                    setattr(alert_dto, label_key, label_value)

            formatted_alerts.append(alert_dto)

        if len(formatted_alerts) == 1:
            return formatted_alerts[0]
        return formatted_alerts


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    signoz_access_token = os.environ.get("SIGNOZ_ACCESS_TOKEN")
    signoz_endpoint = os.environ.get("SIGNOZ_ENDPOINT", "http://localhost:3301")

    provider_config = {
        "authentication": {
            "signoz_access_token": signoz_access_token,
            "signoz_endpoint": signoz_endpoint,
        },
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="signoz",
        provider_type="signoz",
        provider_config=provider_config,
    )
    alerts = provider._get_alerts()
    print(f"Got {len(alerts)} alerts")
