"""
LogzProvider is a class that allows to get triggered alerts from Logz.io.
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
class LogzProviderAuthConfig:
    """
    LogzProviderAuthConfig is a class that allows to authenticate in Logz.io.
    """

    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Logz.io API Token",
            "hint": "Found under your Logz.io account → Settings → API tokens",
            "sensitive": True,
        },
    )

    region: str = dataclasses.field(
        default="us",
        metadata={
            "required": False,
            "description": "Logz.io region (e.g. us, eu, au, ca, uk, nl, wa)",
            "hint": "Your account region — defaults to 'us'",
            "sensitive": False,
        },
    )


class LogzProvider(BaseProvider):
    """Pull triggered alerts from Logz.io."""

    PROVIDER_DISPLAY_NAME = "Logz.io"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring", "Cloud Infrastructure"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated with Logz.io API",
            mandatory=True,
            alias="authenticated",
        ),
    ]

    SEVERITIES_MAP = {
        "HIGH": AlertSeverity.HIGH,
        "MEDIUM": AlertSeverity.WARNING,
        "LOW": AlertSeverity.INFO,
        "SEVERE": AlertSeverity.CRITICAL,
        "INFO": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "TRIGGERED": AlertStatus.FIRING,
        "RESOLVED": AlertStatus.RESOLVED,
        "SUPPRESSED": AlertStatus.SUPPRESSED,
    }

    REGION_ENDPOINTS = {
        "us": "https://api.logz.io",
        "eu": "https://api-eu.logz.io",
        "au": "https://api-au.logz.io",
        "ca": "https://api-ca.logz.io",
        "uk": "https://api-uk.logz.io",
        "nl": "https://api-nl.logz.io",
        "wa": "https://api-wa.logz.io",
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = LogzProviderAuthConfig(
            **self.config.authentication
        )

    def __get_base_url(self) -> str:
        region = self.authentication_config.region.lower()
        return self.REGION_ENDPOINTS.get(region, self.REGION_ENDPOINTS["us"])

    def __get_headers(self):
        return {
            "X-API-TOKEN": self.authentication_config.api_token,
            "Content-Type": "application/json",
        }

    def __get_url(self, path: str) -> str:
        return urljoin(self.__get_base_url() + "/", path.lstrip("/"))

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {}
        try:
            response = requests.get(
                self.__get_url("/v1/alerts"),
                headers=self.__get_headers(),
                timeout=10,
            )
            if response.status_code == 200:
                scopes["authenticated"] = True
            elif response.status_code == 401:
                scopes["authenticated"] = "Invalid API token"
            else:
                scopes["authenticated"] = (
                    f"Unexpected status code: {response.status_code}"
                )
        except Exception as e:
            self.logger.error("Error validating Logz.io scopes: %s", e)
            scopes["authenticated"] = str(e)
        return scopes

    def __get_triggered_alerts(self) -> List[AlertDto]:
        try:
            response = requests.get(
                self.__get_url("/v2/alerts/triggered-alerts"),
                headers=self.__get_headers(),
                params={"size": 200, "from": 0},
                timeout=15,
            )
            if not response.ok:
                self.logger.error(
                    "Failed to get triggered alerts from Logz.io: %s", response.text
                )
                return []

            data = response.json()
            alerts_raw = data.get("results", [])
            alerts = []

            for alert in alerts_raw:
                severity = self.SEVERITIES_MAP.get(
                    alert.get("severity", "LOW"), AlertSeverity.INFO
                )
                status = self.STATUS_MAP.get(
                    alert.get("status", "TRIGGERED"), AlertStatus.FIRING
                )

                triggered_at = alert.get("alertTriggeredAt", "")
                if triggered_at:
                    try:
                        triggered_at = datetime.datetime.fromisoformat(
                            triggered_at.replace("Z", "+00:00")
                        ).isoformat()
                    except Exception:
                        pass

                alerts.append(
                    AlertDto(
                        id=str(alert.get("alertId", "")),
                        name=alert.get("alertTitle", "Logz.io Alert"),
                        description=alert.get("alertDescription", ""),
                        severity=severity,
                        status=status,
                        lastReceived=triggered_at,
                        source=["logz"],
                        labels={
                            "groupBy": ", ".join(alert.get("groupBy", [])),
                            "tags": ", ".join(alert.get("tags", [])),
                        },
                    )
                )
            return alerts

        except Exception as e:
            self.logger.error("Error getting triggered alerts from Logz.io: %s", e)
            return []

    def _get_alerts(self) -> List[AlertDto]:
        self.logger.info("Collecting triggered alerts from Logz.io")
        return self.__get_triggered_alerts()

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """Format a Logz.io webhook payload into an AlertDto."""
        severity_map = {
            "HIGH": AlertSeverity.HIGH,
            "MEDIUM": AlertSeverity.WARNING,
            "LOW": AlertSeverity.INFO,
            "SEVERE": AlertSeverity.CRITICAL,
        }

        severity = severity_map.get(
            event.get("alert_severity", "LOW"), AlertSeverity.INFO
        )

        last_received = event.get("alert_timeframe_start", "")
        if last_received:
            try:
                last_received = datetime.datetime.fromisoformat(
                    last_received.replace("Z", "+00:00")
                ).isoformat()
            except Exception:
                pass

        return AlertDto(
            id=str(event.get("alert_id", "")),
            name=event.get("alert_title", "Logz.io Alert"),
            description=event.get("alert_description", ""),
            severity=severity,
            status=AlertStatus.FIRING,
            lastReceived=last_received,
            url=event.get("alert_app_url", ""),
            source=["logz"],
            labels={
                "account_id": str(event.get("account_id", "")),
                "account_name": event.get("account_name", ""),
                "tags": ", ".join(event.get("alert_tags", [])),
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

    api_token = os.environ.get("LOGZ_API_TOKEN")
    region = os.environ.get("LOGZ_REGION", "us")

    if not api_token:
        raise Exception("LOGZ_API_TOKEN must be set")

    config = ProviderConfig(
        description="Logz.io Provider",
        authentication={
            "api_token": api_token,
            "region": region,
        },
    )

    provider = LogzProvider(
        context_manager,
        provider_id="logz",
        config=config,
    )

    alerts = provider._get_alerts()
    print(alerts)
