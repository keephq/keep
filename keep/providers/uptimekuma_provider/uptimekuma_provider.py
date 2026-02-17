"""
Uptime Kuma provider for Keep.

Uptime Kuma is a self-hosted monitoring tool that supports HTTP(s), TCP, Ping,
DNS and other monitor types. This provider supports both pulling alerts via the
Socket.IO API (using the uptime-kuma-api Python wrapper) and receiving webhook
push notifications from Uptime Kuma.

Uptime Kuma heartbeat status codes:
    0 = DOWN
    1 = UP
    2 = PENDING
    3 = MAINTENANCE
"""

import dataclasses
import datetime
import logging

import pydantic
from socketio.exceptions import BadNamespaceError

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class UptimekumaProviderAuthConfig:
    """
    Authentication configuration for the Uptime Kuma provider.

    Requires the host URL, username and password for the Uptime Kuma instance.
    These credentials are used to connect via the Socket.IO API.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Uptime Kuma Host URL (e.g. http://localhost:3001)",
            "sensitive": False,
            "validation": "any_http_url",
        },
    )

    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Uptime Kuma Username",
            "sensitive": False,
        },
    )

    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Uptime Kuma Password",
            "sensitive": True,
        },
    )


class UptimekumaProvider(BaseProvider):
    """
    Pull alerts and receive webhooks from Uptime Kuma.

    - **Pull mode**: Connects to the Uptime Kuma Socket.IO API, retrieves all
      monitors and their latest heartbeat to build a list of alerts.
    - **Webhook mode**: Receives push notifications sent by Uptime Kuma's
      built-in Webhook notification type.
    """

    PROVIDER_DISPLAY_NAME = "Uptime Kuma"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["monitor_id"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="alerts",
            description="Read alerts from Uptime Kuma",
        )
    ]

    # Uptime Kuma heartbeat status → Keep alert status
    STATUS_MAP = {
        0: AlertStatus.FIRING,
        1: AlertStatus.RESOLVED,
        2: AlertStatus.PENDING,
        3: AlertStatus.MAINTENANCE,
        "0": AlertStatus.FIRING,
        "1": AlertStatus.RESOLVED,
        "2": AlertStatus.PENDING,
        "3": AlertStatus.MAINTENANCE,
        "down": AlertStatus.FIRING,
        "up": AlertStatus.RESOLVED,
        "pending": AlertStatus.PENDING,
        "maintenance": AlertStatus.MAINTENANCE,
    }

    # Uptime Kuma heartbeat status → Keep severity
    SEVERITY_MAP = {
        0: AlertSeverity.CRITICAL,
        1: AlertSeverity.INFO,
        2: AlertSeverity.WARNING,
        3: AlertSeverity.INFO,
        "0": AlertSeverity.CRITICAL,
        "1": AlertSeverity.INFO,
        "2": AlertSeverity.WARNING,
        "3": AlertSeverity.INFO,
        "down": AlertSeverity.CRITICAL,
        "up": AlertSeverity.INFO,
        "pending": AlertSeverity.WARNING,
        "maintenance": AlertSeverity.INFO,
    }

    webhook_description = "Receive alerts from Uptime Kuma via webhook"
    webhook_markdown = """
## Uptime Kuma Webhook Integration

To send alerts from Uptime Kuma to Keep:

1. In Uptime Kuma, go to **Settings** → **Notifications** → **Setup Notification**.
2. Select **Notification Type**: **Webhook**.
3. Set **URL** to: `{keep_webhook_api_url}`.
4. Set **Request Method** to **POST**.
5. Set **Content Type** to **application/json**.
6. Optionally add an additional header: `X-API-KEY` with value `{api_key}`.
7. Click **Test** to verify the connection.
8. Click **Save**.
9. Assign this notification to the monitors you want to track.

The webhook payload from Uptime Kuma contains:
- `heartbeat`: Object with status, time, msg, ping, duration, etc.
- `monitor`: Object with id, name, url, type, etc.
- `msg`: A human-readable summary message.
"""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """Clean up resources."""
        pass

    def validate_config(self):
        """Validate that the authentication configuration is complete."""
        self.authentication_config = UptimekumaProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate that the credentials can successfully authenticate
        against the Uptime Kuma instance.
        """
        try:
            from uptime_kuma_api import UptimeKumaApi

            api = UptimeKumaApi(str(self.authentication_config.host_url))
            response = api.login(
                self.authentication_config.username,
                self.authentication_config.password,
            )
            api.disconnect()
            if "token" in response:
                return {"alerts": True}
            return {"alerts": "Login succeeded but no token returned"}
        except Exception as e:
            self.logger.error("Error validating scopes for Uptime Kuma: %s", e)
            return {"alerts": str(e)}

    def _get_api(self):
        """
        Create a new authenticated UptimeKumaApi connection.

        Returns:
            UptimeKumaApi: An authenticated API instance.
        """
        from uptime_kuma_api import UptimeKumaApi

        api = UptimeKumaApi(str(self.authentication_config.host_url))
        api.login(
            self.authentication_config.username,
            self.authentication_config.password,
        )
        return api

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull alerts from Uptime Kuma by fetching all monitors and their
        latest heartbeats via the Socket.IO API.

        Returns:
            list[AlertDto]: A list of alerts representing the latest
                heartbeat for each monitor.
        """
        self.logger.info("Collecting alerts (heartbeats) from Uptime Kuma")
        alerts = []
        api = None

        try:
            api = self._get_api()
            heartbeats = api.get_heartbeats()

            if not heartbeats:
                self.logger.info("No heartbeats found in Uptime Kuma")
                return []

            # Build a monitor ID → name/url lookup from the monitors list
            monitors = {}
            try:
                for monitor in api.get_monitors():
                    monitors[monitor["id"]] = monitor
            except (BadNamespaceError, Exception) as e:
                self.logger.warning(
                    "Could not bulk-fetch monitors, will fetch individually: %s", e
                )

            for monitor_id_key in heartbeats:
                heartbeat_list = heartbeats[monitor_id_key]
                if not heartbeat_list:
                    continue

                # Take the latest heartbeat
                heartbeat = heartbeat_list[-1]
                monitor_id = heartbeat.get("monitor_id", heartbeat.get("monitorID"))

                # Resolve monitor details
                monitor_data = monitors.get(monitor_id)
                if not monitor_data:
                    try:
                        monitor_data = api.get_monitor(monitor_id)
                    except BadNamespaceError:
                        # Connection dropped — single retry
                        try:
                            api.disconnect()
                        except Exception:
                            pass
                        api = self._get_api()
                        try:
                            monitor_data = api.get_monitor(monitor_id)
                        except Exception as exc:
                            self.logger.warning(
                                "Could not fetch monitor %s after retry: %s",
                                monitor_id,
                                exc,
                            )
                            monitor_data = {}
                    except Exception as exc:
                        self.logger.warning(
                            "Could not fetch monitor %s: %s", monitor_id, exc
                        )
                        monitor_data = {}

                monitor_name = monitor_data.get("name", f"Monitor {monitor_id}")
                monitor_url = monitor_data.get("url")
                monitor_type = monitor_data.get("type")
                # Convert enum types to string if needed
                if hasattr(monitor_type, "value"):
                    monitor_type = monitor_type.value

                status_raw = heartbeat.get("status")
                # MonitorStatus enum → int
                if hasattr(status_raw, "value"):
                    status_raw = status_raw.value

                last_received = self._parse_heartbeat_time(heartbeat.get("time"))

                alert = AlertDto(
                    id=str(heartbeat.get("id", monitor_id)),
                    name=monitor_name,
                    status=self.STATUS_MAP.get(status_raw, AlertStatus.FIRING),
                    severity=self.SEVERITY_MAP.get(status_raw, AlertSeverity.WARNING),
                    lastReceived=last_received,
                    description=heartbeat.get("msg", ""),
                    monitor_id=monitor_id,
                    monitor_url=monitor_url,
                    monitor_type=monitor_type,
                    ping=heartbeat.get("ping"),
                    duration=heartbeat.get("duration"),
                    source=["uptimekuma"],
                )
                alert.fingerprint = self.get_alert_fingerprint(
                    alert, self.FINGERPRINT_FIELDS
                )
                alerts.append(alert)

        except Exception as e:
            self.logger.error("Error getting alerts from Uptime Kuma: %s", e)
            raise
        finally:
            if api:
                try:
                    api.disconnect()
                except Exception:
                    pass

        self.logger.info("Collected %d alerts from Uptime Kuma", len(alerts))
        return alerts

    @staticmethod
    def _parse_heartbeat_time(time_str: str | None) -> str:
        """
        Parse a heartbeat time string from Uptime Kuma into ISO 8601 format.

        Uptime Kuma stores heartbeat times as local datetime strings like
        ``'2024-01-15 12:30:45.123'``. We parse them and return ISO format.
        If parsing fails, fall back to the current UTC time.

        Args:
            time_str: The time string from a heartbeat record.

        Returns:
            An ISO 8601 formatted datetime string.
        """
        if not time_str:
            return datetime.datetime.now(datetime.timezone.utc).isoformat()

        try:
            # Uptime Kuma uses format like '2024-01-15 12:30:45.123'
            dt = datetime.datetime.fromisoformat(str(time_str))
            # If no timezone info, treat as UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt.isoformat()
        except (ValueError, TypeError):
            return datetime.datetime.now(datetime.timezone.utc).isoformat()

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a webhook event from Uptime Kuma into an AlertDto.

        Uptime Kuma's Webhook notification sends a JSON payload with:
        - ``heartbeat``: dict with ``status``, ``time``, ``msg``, ``ping``,
          ``duration``, ``monitorID``, etc.
        - ``monitor``: dict with ``id``, ``name``, ``url``, ``type``, etc.
        - ``msg``: A human-readable summary string.

        Args:
            event: The raw webhook payload from Uptime Kuma.
            provider_instance: Optional provider instance for context.

        Returns:
            An AlertDto representing the incoming alert.
        """
        heartbeat = event.get("heartbeat", {})
        monitor = event.get("monitor", {})
        msg = event.get("msg", "")

        # Extract heartbeat status
        status_raw = heartbeat.get("status")
        if hasattr(status_raw, "value"):
            status_raw = status_raw.value

        # Determine monitor ID from heartbeat or monitor payload
        monitor_id = heartbeat.get("monitorID") or monitor.get("id")

        # Parse time
        last_received = UptimekumaProvider._parse_heartbeat_time(
            heartbeat.get("time")
        )

        # Determine monitor URL — may be in 'url' or 'hostname' depending on type
        monitor_url = monitor.get("url") or monitor.get("hostname")

        # Get monitor type as string
        monitor_type = monitor.get("type")
        if hasattr(monitor_type, "value"):
            monitor_type = monitor_type.value

        alert = AlertDto(
            id=str(monitor_id) if monitor_id else None,
            name=monitor.get("name", msg or "Uptime Kuma Alert"),
            status=UptimekumaProvider.STATUS_MAP.get(
                status_raw, AlertStatus.FIRING
            ),
            severity=UptimekumaProvider.SEVERITY_MAP.get(
                status_raw, AlertSeverity.WARNING
            ),
            lastReceived=last_received,
            description=msg or heartbeat.get("msg", ""),
            monitor_id=monitor_id,
            monitor_url=monitor_url,
            monitor_type=monitor_type,
            ping=heartbeat.get("ping"),
            duration=heartbeat.get("duration"),
            message=heartbeat.get("msg"),
            source=["uptimekuma"],
        )

        if monitor_id:
            alert.fingerprint = UptimekumaProvider.get_alert_fingerprint(
                alert, UptimekumaProvider.FINGERPRINT_FIELDS
            )

        return alert


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    uptimekuma_host = os.environ.get("UPTIMEKUMA_HOST")
    uptimekuma_username = os.environ.get("UPTIMEKUMA_USERNAME")
    uptimekuma_password = os.environ.get("UPTIMEKUMA_PASSWORD")

    if not uptimekuma_host:
        raise SystemExit("UPTIMEKUMA_HOST is required")
    if not uptimekuma_username:
        raise SystemExit("UPTIMEKUMA_USERNAME is required")
    if not uptimekuma_password:
        raise SystemExit("UPTIMEKUMA_PASSWORD is required")

    config = ProviderConfig(
        description="Uptime Kuma Provider",
        authentication={
            "host_url": uptimekuma_host,
            "username": uptimekuma_username,
            "password": uptimekuma_password,
        },
    )

    provider = UptimekumaProvider(
        context_manager=context_manager,
        provider_id="uptimekuma",
        config=config,
    )

    alerts = provider.get_alerts()
    for a in alerts:
        print(a)
