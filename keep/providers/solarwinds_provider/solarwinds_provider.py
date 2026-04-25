import dataclasses
import datetime

import pydantic
import requests
from requests.auth import HTTPBasicAuth

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider, ProviderHealthMixin
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class SolarwindsProviderAuthConfig:
    orion_hostname: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion hostname or IP",
            "sensitive": False,
            "hint": "orion.example.com",
        },
    )
    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds username",
            "sensitive": False,
        },
    )
    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds password",
            "sensitive": True,
        },
    )
    port: int = dataclasses.field(
        metadata={
            "required": False,
            "description": "SolarWinds Orion port",
            "sensitive": False,
        },
        default=17778,
    )


class SolarwindsProvider(BaseProvider, ProviderHealthMixin):
    PROVIDER_DISPLAY_NAME = "SolarWinds"
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["alert_id"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="alerts_read",
            description="Read alerts from SolarWinds",
            mandatory=True,
        )
    ]

    SEVERITY_MAP = {
        "Critical": AlertSeverity.CRITICAL,
        "Warning": AlertSeverity.WARNING,
        "Informational": AlertSeverity.INFO,
        "Serious": AlertSeverity.HIGH,
        "Notice": AlertSeverity.INFO,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SolarwindsProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        try:
            url = self._get_api_url("Query")
            params = {"query": "SELECT TOP 1 1 FROM Orion.AlertActive"}
            response = requests.get(
                url,
                params=params,
                auth=HTTPBasicAuth(
                    self.authentication_config.username,
                    self.authentication_config.password,
                ),
                verify=False,
                timeout=10,
            )
            if response.ok:
                return {"alerts_read": True}
            return {"alerts_read": f"Failed: {response.status_code}"}
        except Exception as e:
            return {"alerts_read": str(e)}

    def dispose(self):
        pass

    def _get_api_url(self, endpoint: str) -> str:
        hostname = self.authentication_config.orion_hostname
        port = self.authentication_config.port
        return f"https://{hostname}:{port}/SolarWinds/InformationService/v3/Json/{endpoint}"

    def _get_alerts(self) -> list[AlertDto]:
        try:
            self.logger.info("Pulling alerts from SolarWinds")
            url = self._get_api_url("Query")
            params = {"query": "SELECT AlertID, AlertObjectID, Name, Message, Severity, TriggerTimeStamp, LastExecutedTime FROM Orion.AlertActive"}
            
            response = requests.get(
                url,
                params=params,
                auth=HTTPBasicAuth(
                    self.authentication_config.username,
                    self.authentication_config.password,
                ),
                verify=False,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])
            
            alerts = []
            for alert_data in results:
                alert = self._format_alert(alert_data)
                if alert:
                    alerts.append(alert)
            
            self.logger.info(f"Pulled {len(alerts)} alerts from SolarWinds")
            return alerts
        except Exception as e:
            self.logger.error(f"Error pulling alerts from SolarWinds: {e}")
            raise

    def _format_alert(self, alert_data: dict) -> AlertDto | None:
        alert_id = alert_data.get("AlertID")
        alert_object_id = alert_data.get("AlertObjectID")
        
        if not alert_id:
            return None

        severity_str = alert_data.get("Severity", "Informational")
        severity = self.SEVERITY_MAP.get(severity_str, AlertSeverity.INFO)

        trigger_time = alert_data.get("TriggerTimeStamp")
        last_received = None
        if trigger_time:
            try:
                last_received = datetime.datetime.fromisoformat(trigger_time.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                last_received = datetime.datetime.now(tz=datetime.timezone.utc)
        else:
            last_received = datetime.datetime.now(tz=datetime.timezone.utc)

        return AlertDto(
            id=str(alert_id),
            alert_id=str(alert_id),
            alert_object_id=str(alert_object_id) if alert_object_id else None,
            name=alert_data.get("Name", "Unknown"),
            message=alert_data.get("Message", ""),
            severity=severity,
            status=AlertStatus.FIRING,
            lastReceived=last_received.isoformat(),
            source=["solarwinds"],
        )
