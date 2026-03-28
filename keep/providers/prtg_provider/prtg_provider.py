"""
PrtgProvider integrates PRTG Network Monitor with Keep.

Supports two modes:
  - Pull mode: polls PRTG REST API (/api/table.json) for sensor alerts
  - Push mode: receives PRTG webhook (HTTP notification) payloads

PRTG API authentication uses username + passhash (preferred) or username + password.
The passhash can be obtained from PRTG → Account Settings → My Account.
"""

import dataclasses
import datetime
import logging
from typing import Optional
from urllib.parse import urljoin

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class PrtgProviderAuthConfig:
    """
    PRTG authentication configuration.

    Authentication is via username + passhash (recommended) or username + password.
    The passhash can be found under PRTG → Account Settings → My Account → Passhash.
    """

    url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "PRTG server URL",
            "hint": "https://prtg.example.com",
            "validation": "any_http_url",
        }
    )
    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "PRTG username",
            "hint": "prtgadmin",
            "sensitive": False,
        }
    )
    passhash: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "PRTG passhash (preferred over password)",
            "hint": "Found under Account Settings → My Account → Passhash",
            "sensitive": True,
        },
        default="",
    )
    password: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "PRTG password (used only when passhash is not set)",
            "sensitive": True,
        },
        default="",
    )
    verify_ssl: bool = dataclasses.field(
        metadata={
            "required": False,
            "description": "Verify SSL certificates",
            "hint": "Set to false for self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )


class PrtgProvider(BaseProvider):
    """
    Pull/Push alerts from PRTG Network Monitor into Keep.

    Pull mode: queries PRTG REST API for sensors in error/warning state.
    Push mode: receives JSON payloads sent by PRTG HTTP notifications.
    """

    PROVIDER_DISPLAY_NAME = "PRTG Network Monitor"
    PROVIDER_TAGS = ["monitoring", "network", "infrastructure"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["id"]

    # Webhook instructions shown in Keep UI
    webhook_description = (
        "Receive alerts from PRTG Network Monitor via HTTP notifications"
    )
    webhook_template = ""
    webhook_markdown = """
To send alerts from PRTG to Keep via webhook:

1. In PRTG web interface, go to **Setup** → **Account Settings** → **Notifications**.
2. Click **Add new notification**.
3. Give it a name (e.g. "Send to Keep").
4. Enable **Execute HTTP Action**.
5. Set **URL** to `{keep_webhook_api_url}`.
6. Set **HTTP Method** to `POST`.
7. Set **Content Type** to `application/json`.
8. In the **Payload** field, paste the following template:
```json
{{
  "sensor": "%sensor",
  "device": "%device",
  "group": "%group",
  "probe": "%probe",
  "status": "%status",
  "message": "%message",
  "datetime": "%datetime",
  "sensor_id": "%sensorid",
  "device_id": "%deviceid",
  "group_id": "%groupid",
  "priority": "%priority",
  "lastvalue": "%lastvalue",
  "home": "%home"
}}
```
9. Click **Save**.
10. Assign this notification to sensor **Notification Triggers** as needed.
"""

    PROVIDER_SCOPES = [
        ProviderScope(
            name="api_access",
            description="Read sensor and alert data from PRTG REST API",
            mandatory=True,
            alias="API Access",
            documentation_url="https://www.paessler.com/manuals/prtg/live_api_documentation",
        ),
    ]

    # PRTG sensor status → Keep AlertStatus
    # https://kb.paessler.com/en/topic/653-how-do-i-use-prtg-api
    STATUS_MAP = {
        "up": AlertStatus.RESOLVED,
        "down": AlertStatus.FIRING,
        "down (acknowledged)": AlertStatus.ACKNOWLEDGED,
        "warning": AlertStatus.FIRING,
        "unusual": AlertStatus.FIRING,
        "partial down": AlertStatus.FIRING,
        "paused": AlertStatus.SUPPRESSED,
        "paused by user": AlertStatus.SUPPRESSED,
        "paused by schedule": AlertStatus.SUPPRESSED,
        "paused by dependency": AlertStatus.SUPPRESSED,
        "paused until": AlertStatus.SUPPRESSED,
        "unknown": AlertStatus.PENDING,
    }

    # PRTG sensor status → Keep AlertSeverity
    SEVERITY_MAP = {
        "down": AlertSeverity.CRITICAL,
        "down (acknowledged)": AlertSeverity.CRITICAL,
        "partial down": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "unusual": AlertSeverity.WARNING,
        "paused": AlertSeverity.INFO,
        "paused by user": AlertSeverity.INFO,
        "paused by schedule": AlertSeverity.INFO,
        "paused by dependency": AlertSeverity.INFO,
        "paused until": AlertSeverity.INFO,
        "up": AlertSeverity.INFO,
        "unknown": AlertSeverity.INFO,
    }

    # PRTG numeric priority (1-5 stars) → Keep AlertSeverity
    # Used when webhook sends numeric or star-encoded priority
    PRIORITY_MAP = {
        "1": AlertSeverity.LOW,
        "2": AlertSeverity.INFO,
        "3": AlertSeverity.WARNING,
        "4": AlertSeverity.HIGH,
        "5": AlertSeverity.CRITICAL,
        # star-encoded variants from PRTG %priority placeholder
        "*": AlertSeverity.LOW,
        "**": AlertSeverity.INFO,
        "***": AlertSeverity.WARNING,
        "****": AlertSeverity.HIGH,
        "*****": AlertSeverity.CRITICAL,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    # ------------------------------------------------------------------
    # BaseProvider interface
    # ------------------------------------------------------------------

    def dispose(self):
        pass

    def validate_config(self):
        """Validate and parse PRTG authentication config."""
        self.authentication_config = PrtgProviderAuthConfig(
            **self.config.authentication
        )
        if (
            not self.authentication_config.passhash
            and not self.authentication_config.password
        ):
            raise ValueError(
                "Either 'passhash' or 'password' must be provided for PRTG authentication."
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_auth_params(self) -> dict:
        """Return query params dict for PRTG API authentication."""
        params = {"username": self.authentication_config.username}
        if self.authentication_config.passhash:
            params["passhash"] = self.authentication_config.passhash
        else:
            params["password"] = self.authentication_config.password
        return params

    def _build_url(self, path: str) -> str:
        """Build an absolute PRTG API URL from a relative path."""
        base = str(self.authentication_config.url).rstrip("/") + "/"
        return urljoin(base, path.lstrip("/"))

    def _api_get(self, path: str, params: Optional[dict] = None) -> dict:
        """Perform an authenticated GET request against the PRTG API."""
        url = self._build_url(path)
        all_params = self._get_auth_params()
        if params:
            all_params.update(params)
        response = requests.get(
            url,
            params=all_params,
            verify=self.authentication_config.verify_ssl,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # validate_scopes
    # ------------------------------------------------------------------

    def validate_scopes(self) -> dict:
        """
        Verify that the provided credentials can reach the PRTG API.
        Uses /api/getstatus.json which is a lightweight status endpoint.
        """
        try:
            self._api_get("/api/getstatus.json")
            return {"api_access": True}
        except requests.exceptions.HTTPError as exc:
            self.logger.error(
                "PRTG API authentication failed",
                extra={"status_code": exc.response.status_code if exc.response else None},
            )
            return {"api_access": str(exc)}
        except Exception as exc:
            self.logger.error("PRTG API connectivity failed", extra={"error": str(exc)})
            return {"api_access": str(exc)}

    # ------------------------------------------------------------------
    # Pull mode: _get_alerts
    # ------------------------------------------------------------------

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull sensor alerts from PRTG using the table API.

        Fetches sensors whose status indicates a problem (Down, Warning, Unusual,
        Partial Down) as well as all acknowledged-down sensors.
        """
        self.logger.info("Fetching alerts from PRTG API")
        try:
            data = self._api_get(
                "/api/table.json",
                params={
                    "content": "sensors",
                    "output": "json",
                    "columns": (
                        "objid,sensor,device,group,probe,status,statusraw,"
                        "message,priority,lastvalue,lastup,lastdown,active"
                    ),
                    # Fetch all non-Up and non-Paused sensors
                    "filter_status": [
                        "4",   # Down
                        "5",   # Down (Acknowledged)
                        "7",   # Warning
                        "10",  # Unusual
                        "12",  # Partial Down
                    ],
                },
            )
        except Exception as exc:
            self.logger.error(
                "Failed to fetch sensors from PRTG", extra={"error": str(exc)}
            )
            raise

        sensors = data.get("sensors", [])
        self.logger.info("Retrieved %d problem sensors from PRTG", len(sensors))
        return [self._sensor_to_dto(sensor) for sensor in sensors]

    def _sensor_to_dto(self, sensor: dict) -> AlertDto:
        """Convert a PRTG sensor object (from pull API) to AlertDto."""
        status_raw = (sensor.get("status") or "Unknown").strip()
        status_key = status_raw.lower()
        status = self.STATUS_MAP.get(status_key, AlertStatus.FIRING)
        severity = self.SEVERITY_MAP.get(status_key, AlertSeverity.INFO)

        sensor_id = str(sensor.get("objid", ""))
        sensor_name = sensor.get("sensor", "Unknown Sensor")
        device_name = sensor.get("device", "Unknown Device")
        group_name = sensor.get("group", "")
        probe_name = sensor.get("probe", "")
        priority = str(sensor.get("priority", "3"))
        last_value = sensor.get("lastvalue", "")
        message = (sensor.get("message") or "").strip()

        # Enrich description with last value if available
        description = message
        if last_value and last_value not in ("", "No data"):
            description = f"{message} [Last value: {last_value}]" if message else f"Last value: {last_value}"

        # Determine last_received from lastdown or lastup
        last_received = sensor.get("lastdown") or sensor.get("lastup") or ""

        name = f"{device_name} / {sensor_name}"

        return AlertDto(
            id=sensor_id,
            name=name,
            description=description,
            status=status,
            severity=severity,
            lastReceived=last_received or datetime.datetime.utcnow().isoformat(),
            source=["prtg"],
            service=device_name,
            labels={
                "sensor_id": sensor_id,
                "sensor": sensor_name,
                "device": device_name,
                "group": group_name,
                "probe": probe_name,
                "priority": priority,
                "status_raw": status_raw,
                "last_value": last_value,
            },
        )

    # ------------------------------------------------------------------
    # Push mode: _format_alert (webhook)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "PrtgProvider" = None
    ) -> AlertDto:
        """
        Format a PRTG webhook notification payload into an AlertDto.

        PRTG sends a JSON body built from its notification template placeholders:
          %sensor, %device, %group, %probe, %status, %message,
          %datetime, %sensorid, %deviceid, %groupid, %priority, %lastvalue
        """
        prtg_status = (event.get("status") or "Unknown").strip()
        status_key = prtg_status.lower()

        status = PrtgProvider.STATUS_MAP.get(status_key, AlertStatus.FIRING)
        severity = PrtgProvider.SEVERITY_MAP.get(status_key, AlertSeverity.INFO)

        # Override with priority-based severity when explicitly Down or Warning
        priority = str(event.get("priority", ""))
        if priority and status_key in ("down", "partial down", "warning", "unusual"):
            priority_severity = PrtgProvider.PRIORITY_MAP.get(priority.strip())
            if priority_severity is not None:
                # Only escalate severity, never downgrade.
                # AlertSeverity supports > comparison via severity_order (CRITICAL=5, LOW=1).
                if priority_severity > severity:
                    severity = priority_severity

        sensor = event.get("sensor", "Unknown Sensor")
        device = event.get("device", "Unknown Device")
        group = event.get("group", "")
        probe = event.get("probe", "")
        sensor_id = str(event.get("sensor_id", event.get("sensorid", "")))
        device_id = str(event.get("device_id", event.get("deviceid", "")))
        group_id = str(event.get("group_id", event.get("groupid", "")))
        last_value = event.get("lastvalue", "")
        message = (event.get("message") or "").strip()
        dt_str = event.get("datetime", "")

        description = message
        if last_value and last_value not in ("", "No data"):
            description = f"{message} [Last value: {last_value}]" if message else f"Last value: {last_value}"

        name = f"{device} / {sensor}"
        # Unique id: sensorid + datetime avoids duplicates across repeated firings
        alert_id = f"{sensor_id}-{dt_str}" if sensor_id else f"prtg-{dt_str}"

        return AlertDto(
            id=alert_id,
            name=name,
            description=description,
            status=status,
            severity=severity,
            lastReceived=dt_str or datetime.datetime.utcnow().isoformat(),
            source=["prtg"],
            service=device,
            labels={
                "sensor_id": sensor_id,
                "sensor": sensor,
                "device": device,
                "group": group,
                "probe": probe,
                "device_id": device_id,
                "group_id": group_id,
                "priority": priority,
                "last_value": last_value,
                "status_raw": prtg_status,
            },
        )
