"""
PrtgProvider is a class that provides a way to interact with PRTG Network Monitor.
"""

import dataclasses
import datetime
import logging

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
    PRTG Network Monitor authentication configuration.
    """

    prtg_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "PRTG server URL",
            "hint": "https://prtg.example.com",
            "sensitive": False,
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
            "required": True,
            "description": "PRTG passhash (from PRTG Settings > My Account > API Token / Passhash)",
            "hint": "Find it under Setup > My Account",
            "sensitive": True,
        }
    )
    verify: bool = dataclasses.field(
        metadata={
            "description": "Verify SSL certificates",
            "hint": "Set to false to allow self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )


class PrtgProvider(BaseProvider):
    """Pull sensor alerts from PRTG Network Monitor into Keep."""

    PROVIDER_DISPLAY_NAME = "PRTG"
    PROVIDER_CATEGORY = ["Monitoring", "Network"]
    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="sensors:read",
            description="Read sensor status from the PRTG API",
            mandatory=True,
            documentation_url="https://www.paessler.com/manuals/prtg/application_programming_interface_api_definition",
        ),
    ]

    # PRTG sensor status codes
    # https://kb.paessler.com/en/topic/67869-what-does-the-json-status-value-mean
    PRTG_STATUS_MAP = {
        1: ("Unknown", AlertStatus.FIRING, AlertSeverity.INFO),
        2: ("Collecting", AlertStatus.FIRING, AlertSeverity.INFO),
        3: ("Up", AlertStatus.RESOLVED, AlertSeverity.INFO),
        4: ("Warning", AlertStatus.FIRING, AlertSeverity.WARNING),
        5: ("Down", AlertStatus.FIRING, AlertSeverity.CRITICAL),
        6: ("No Probe", AlertStatus.FIRING, AlertSeverity.HIGH),
        7: ("Paused by User", AlertStatus.SUPPRESSED, AlertSeverity.INFO),
        8: ("Paused by Time", AlertStatus.SUPPRESSED, AlertSeverity.INFO),
        9: ("Paused by Dependency", AlertStatus.SUPPRESSED, AlertSeverity.INFO),
        10: ("Paused by License", AlertStatus.SUPPRESSED, AlertSeverity.INFO),
        11: ("Paused until", AlertStatus.SUPPRESSED, AlertSeverity.INFO),
        12: ("Error", AlertStatus.FIRING, AlertSeverity.HIGH),
        13: ("Disconnected", AlertStatus.FIRING, AlertSeverity.CRITICAL),
        14: ("Down (Acknowledged)", AlertStatus.ACKNOWLEDGED, AlertSeverity.CRITICAL),
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for PRTG provider.
        """
        self.authentication_config = PrtgProviderAuthConfig(
            **self.config.authentication
        )

    def _base_params(self) -> dict:
        return {
            "username": self.authentication_config.username,
            "passhash": self.authentication_config.passhash,
            "output": "json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes: dict[str, bool | str] = {"sensors:read": False}
        try:
            url = f"{self.authentication_config.prtg_url}/api/table.json"
            params = {
                **self._base_params(),
                "content": "sensors",
                "columns": "objid,name,status",
                "count": 1,
            }
            response = requests.get(
                url,
                params=params,
                verify=self.authentication_config.verify,
                timeout=10,
            )
            if response.status_code == 200 and "sensors" in response.json():
                scopes["sensors:read"] = True
            else:
                scopes["sensors:read"] = f"HTTP {response.status_code}: {response.text[:200]}"
        except Exception as e:
            scopes["sensors:read"] = str(e)
        return scopes

    def _get_alerts(self) -> list[AlertDto]:
        """Pull non-OK sensors from PRTG."""
        url = f"{self.authentication_config.prtg_url}/api/table.json"
        params = {
            **self._base_params(),
            "content": "sensors",
            "columns": "objid,name,device,group,status,statusid,message,lastvalue,lastcheck,tags",
            # filter to non-OK sensors (status 4=Warning, 5=Down, 6=No Probe, 12=Error, 13=Disconnected, 14=Down Ack)
            "filter_status": "4,5,6,12,13,14",
            "count": 2500,
        }
        response = requests.get(
            url,
            params=params,
            verify=self.authentication_config.verify,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        sensors = data.get("sensors", [])

        alerts = []
        for sensor in sensors:
            dto = self._format_alert(sensor)
            if isinstance(dto, list):
                alerts.extend(dto)
            else:
                alerts.append(dto)
        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        sensor_id = str(event.get("objid", ""))
        sensor_name = event.get("name", "unknown")
        device = event.get("device", "")
        group = event.get("group", "")
        status_id = int(event.get("statusid", 3))
        message = event.get("message", "")
        last_value = event.get("lastvalue", "")
        last_check_raw = event.get("lastcheck", "")
        tags_raw = event.get("tags", "")

        status_tuple = PrtgProvider.PRTG_STATUS_MAP.get(
            status_id, ("Unknown", AlertStatus.FIRING, AlertSeverity.INFO)
        )
        status_name, status, severity = status_tuple

        # Parse PRTG datetime format: "01/01/2024 12:00:00 AM"
        try:
            last_received = datetime.datetime.strptime(
                last_check_raw.strip(), "%m/%d/%Y %I:%M:%S %p"
            ).replace(tzinfo=datetime.timezone.utc).isoformat()
        except (ValueError, AttributeError):
            last_received = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

        tags = [t.strip() for t in tags_raw.split(" ") if t.strip()] if tags_raw else []
        labels = {"device": device, "group": group, "tags": ",".join(tags)}

        description = message or f"Sensor '{sensor_name}' on {device} is {status_name}"
        if last_value:
            description = f"{description} (last value: {last_value})"

        alert = AlertDto(
            id=sensor_id,
            name=sensor_name,
            description=description,
            severity=severity,
            status=status,
            lastReceived=last_received,
            source=["prtg"],
            service=device,
            environment=group,
            labels=labels,
            payload=event,
        )
        alert.fingerprint = PrtgProvider.get_alert_fingerprint(
            alert, fingerprint_fields=["id"]
        )
        return alert

    def dispose(self):
        pass

    def notify(self, **kwargs):
        raise NotImplementedError("PRTG provider does not support notify()")


if __name__ == "__main__":
    import os

    config = ProviderConfig(
        authentication={
            "prtg_url": os.environ.get("PRTG_URL", "https://prtg.example.com"),
            "username": os.environ.get("PRTG_USERNAME", "prtgadmin"),
            "passhash": os.environ.get("PRTG_PASSHASH", ""),
        }
    )
    from keep.contextmanager.contextmanager import ContextManager

    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")
    provider = PrtgProvider(context_manager, "prtg-prod", config)
    print(provider.get_alerts())
