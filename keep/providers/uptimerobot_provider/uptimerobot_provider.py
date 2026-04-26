"""
UptimeRobotProvider is a class that integrates Keep with UptimeRobot,
a cloud-based uptime monitoring service. Supports pulling monitor statuses
as alerts and receiving real-time alerts via webhooks.
"""

import dataclasses
import datetime
from typing import List

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class UptimerobotProviderAuthConfig:
    """
    UptimerobotProviderAuthConfig holds the API key for UptimeRobot authentication.
    """

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "UptimeRobot API Key (Main or Monitor-specific)",
            "sensitive": True,
            "hint": "Find it in UptimeRobot Dashboard → My Settings → API Settings",
        },
    )


class UptimerobotProvider(BaseProvider):
    """Pull monitor statuses from UptimeRobot as Keep alerts."""

    PROVIDER_DISPLAY_NAME = "UptimeRobot"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_monitors",
            description="Read monitor statuses from UptimeRobot",
            mandatory=True,
        ),
    ]

    # UptimeRobot monitor status codes → Keep AlertStatus
    # 0 = Paused, 1 = Not checked yet, 2 = Up, 8 = Seems down, 9 = Down
    STATUS_MAP = {
        0: AlertStatus.SUPPRESSED,
        1: AlertStatus.PENDING,
        2: AlertStatus.RESOLVED,
        8: AlertStatus.FIRING,
        9: AlertStatus.FIRING,
    }

    # UptimeRobot alert type codes → Keep AlertSeverity
    # 1 = Down, 2 = Up, 3 = SSL expiry, 4 = Response time anomaly
    ALERT_TYPE_SEVERITY = {
        1: AlertSeverity.CRITICAL,   # Monitor is down
        2: AlertSeverity.INFO,       # Monitor recovered
        3: AlertSeverity.WARNING,    # SSL expiry warning
        4: AlertSeverity.WARNING,    # Response time anomaly
    }

    UPTIMEROBOT_API_URL = "https://api.uptimerobot.com/v2"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = UptimerobotProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _post(self, endpoint: str, payload: dict) -> dict:
        """Make a POST request to UptimeRobot API (their API uses POST for all calls)."""
        payload["api_key"] = self.authentication_config.api_key
        payload["format"] = "json"
        response = requests.post(
            f"{self.UPTIMEROBOT_API_URL}/{endpoint}",
            data=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            data = self._post("getAccountDetails", {})
            if data.get("stat") == "ok":
                return {"read_monitors": True}
            else:
                return {
                    "read_monitors": data.get("error", {}).get(
                        "message", "Unknown error from UptimeRobot"
                    )
                }
        except Exception as e:
            self.logger.error("Error validating UptimeRobot scopes: %s", e)
            return {"read_monitors": str(e)}

    def _get_alerts(self) -> List[AlertDto]:
        """Pull all monitors from UptimeRobot and convert to AlertDto."""
        alerts = []
        offset = 0
        limit = 50

        try:
            while True:
                data = self._post(
                    "getMonitors",
                    {
                        "offset": offset,
                        "limit": limit,
                        "logs": 1,
                        "response_times": 0,
                    },
                )

                if data.get("stat") != "ok":
                    error_msg = data.get("error", {}).get("message", "Unknown error")
                    self.logger.error(
                        "UptimeRobot API error: %s", error_msg
                    )
                    raise Exception(f"UptimeRobot API error: {error_msg}")

                monitors = data.get("monitors", [])
                if not monitors:
                    break

                for monitor in monitors:
                    alert = self._monitor_to_alert(monitor)
                    alerts.append(alert)

                pagination = data.get("pagination", {})
                total = pagination.get("total", 0)
                offset += limit
                if offset >= total:
                    break

        except Exception as e:
            self.logger.error("Error fetching monitors from UptimeRobot: %s", e)
            raise

        self.logger.info("Fetched %d monitors from UptimeRobot", len(alerts))
        return alerts

    def _monitor_to_alert(self, monitor: dict) -> AlertDto:
        status_code = monitor.get("status", 2)
        status = self.STATUS_MAP.get(status_code, AlertStatus.FIRING)

        # Determine severity from status
        if status == AlertStatus.FIRING:
            severity = AlertSeverity.CRITICAL
        elif status == AlertStatus.RESOLVED:
            severity = AlertSeverity.INFO
        else:
            severity = AlertSeverity.LOW

        # Use the last log entry timestamp if available
        logs = monitor.get("logs", [])
        if logs:
            last_ts = logs[0].get("datetime", 0)
            last_received = datetime.datetime.fromtimestamp(
                last_ts, tz=datetime.timezone.utc
            ).isoformat()
        else:
            last_received = datetime.datetime.utcnow().isoformat()

        monitor_url = monitor.get("url", "")
        monitor_name = monitor.get("friendly_name", monitor.get("url", "Unknown"))

        return AlertDto(
            id=str(monitor["id"]),
            name=monitor_name,
            description=f"UptimeRobot monitor: {monitor_url}",
            severity=severity,
            status=status,
            lastReceived=last_received,
            source=["uptimerobot"],
            monitor_id=monitor.get("id"),
            monitor_url=monitor_url,
            monitor_type=monitor.get("type"),
            interval=monitor.get("interval"),
            uptime_ratio=monitor.get("custom_uptime_ratio"),
            url=f"https://uptimerobot.com/dashboard#{monitor['id']}",
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Parse an UptimeRobot webhook payload.

        UptimeRobot sends webhook payloads with fields like:
        monitorID, monitorURL, monitorFriendlyName, alertType, alertTypeFriendlyName,
        alertDetails, alertDuration, monitorAlertContacts, alertDateTime
        """
        alert_type = int(event.get("alertType", 1))
        severity = UptimerobotProvider.ALERT_TYPE_SEVERITY.get(
            alert_type, AlertSeverity.WARNING
        )

        # alertType 2 = recovery
        if alert_type == 2:
            status = AlertStatus.RESOLVED
        else:
            status = AlertStatus.FIRING

        monitor_id = event.get("monitorID", "")
        monitor_url = event.get("monitorURL", "")
        monitor_name = event.get("monitorFriendlyName", monitor_url)

        # alertDateTime is a Unix timestamp
        alert_datetime = event.get("alertDateTime")
        if alert_datetime:
            try:
                last_received = datetime.datetime.fromtimestamp(
                    int(alert_datetime), tz=datetime.timezone.utc
                ).isoformat()
            except (ValueError, TypeError):
                last_received = datetime.datetime.utcnow().isoformat()
        else:
            last_received = datetime.datetime.utcnow().isoformat()

        return AlertDto(
            id=str(monitor_id),
            name=monitor_name,
            description=event.get(
                "alertDetails",
                event.get("alertTypeFriendlyName", "UptimeRobot alert"),
            ),
            severity=severity,
            status=status,
            lastReceived=last_received,
            source=["uptimerobot"],
            monitor_id=monitor_id,
            monitor_url=monitor_url,
            alert_type=event.get("alertTypeFriendlyName"),
            alert_duration=event.get("alertDuration"),
            url=f"https://uptimerobot.com/dashboard#{monitor_id}",
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    api_key = os.environ.get("UPTIMEROBOT_API_KEY")
    if not api_key:
        raise Exception("UPTIMEROBOT_API_KEY is required")

    config = ProviderConfig(
        description="UptimeRobot Provider",
        authentication={"api_key": api_key},
    )

    provider = UptimerobotProvider(
        context_manager=context_manager,
        provider_id="uptimerobot",
        config=config,
    )

    scopes = provider.validate_scopes()
    print("Scopes:", scopes)

    alerts = provider.get_alerts()
    print(f"Got {len(alerts)} monitors")
    for alert in alerts[:5]:
        print(alert)
