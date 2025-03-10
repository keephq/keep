"""
LibreNMS Provider is a class that provides a way to receive alerts from LibreNMS using API endpoints as well as webhooks.
"""

import dataclasses

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class LibreNmsProviderAuthConfig:
    """
    LibreNmsProviderAuthConfig is a class that allows you to authenticate in LibreNMS.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "LibreNMS Host URL",
            "hint": "e.g. https://librenms.example.com",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "LibreNMS API Key",
            "sensitive": True,
        }
    )


class LibreNmsProvider(BaseProvider):
    """
    Get alerts from LibreNMS into Keep.
    """

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
💡 For more details on how to configure LibreNMS to send alerts to Keep, see the [Keep documentation](https://docs.keephq.dev/providers/documentation/libre_nms-provider).

To send alerts from LibreNMS to Keep, Use the following webhook url to configure LibreNMS send alerts to Keep:

1. In LibreNMS Dashboard, go to Alerts > Alert Transports
2. Create transport with type API and POST method
3. Give a Transport Name and select Transport Type as API
4. Select the API Method as POST
3. Enter the Keep webhook URL: {keep_webhook_api_url}
4. Add header "X-API-KEY" with your Keep API key (webhook role)
5. For JSON body format, refer to [Keep documentation](https://docs.keephq.dev/providers/documentation/libre_nms-provider)
6. Save the transport
    """

    PROVIDER_DISPLAY_NAME = "LibreNMS"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read alerts from LibreNMS",
        ),
    ]

    STATUS_MAP = {
        "0": AlertStatus.RESOLVED,
        "1": AlertStatus.FIRING,
        "2": AlertStatus.ACKNOWLEDGED
    }

    SEVERITY_MAP = {
        "ok": AlertSeverity.INFO,
        "warning": AlertSeverity.WARNING,
        "critical": AlertSeverity.CRITICAL
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for LibreNMS provider.
        """
        self.authentication_config = LibreNmsProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        """
        Validate scopes for the provider
        """
        self.logger.info("Validating LibreNMS provider")
        try:
            response = requests.get(
                url=self._get_url("alerts"),
                headers=self._get_auth_headers()
            )

            if response.status_code != 200:
                response.raise_for_status()

            self.logger.info("Successfully validated scopes",
                             extra={"response": response.json()})

            return {"read_alerts": True}

        except Exception as e:
            self.logger.exception(
                "Failed to validate scopes", extra={"error": e})
            return {"read_alerts": str(e)}

    def _get_url(self, endpoint: str):
        return f"{self.authentication_config.host_url}/api/v0/{endpoint}"

    def _get_auth_headers(self):
        return {
            "X-Auth-Token": self.authentication_config.api_key
        }

    def _get_alerts(self) -> list[AlertDto]:
        """
        Get alerts from LibreNMS.
        """
        self.logger.info("Getting alerts from LibreNMS")

        try:
            response = requests.get(
                url=self._get_url("alerts"),
                headers=self._get_auth_headers()
            )

            if response.status_code != 200:
                response.raise_for_status()

            alerts = response.json()["alerts"]

            return [
                AlertDto(
                    id=alert.get("id"),
                    name=alert.get("rule_name", "Could not fetch rule name"),
                    hostname=alert.get("hostname", "Could not fetch hostname"),
                    device_id=alert.get(
                        "device_id", "Could not fetch device id"),
                    rule_id=alert.get("rule_id", "Could not fetch rule id"),
                    status=LibreNmsProvider.STATUS_MAP.get(
                        alert.get("state"), AlertStatus.FIRING),
                    alerted=alert.get("alerted", "Could not fetch alerted"),
                    open=alert.get("open", "Could not fetch open"),
                    note=alert.get("note", "Could not fetch note"),
                    timestamp=alert.get(
                        "timestamp", "Could not fetch timestamp"),
                    lastReceived=alert.get(
                        "timestamp", "Could not fetch last received"),
                    info=alert.get("info", "Could not fetch info"),
                    severity=LibreNmsProvider.SEVERITY_MAP.get(
                        alert.get("severity"), AlertSeverity.INFO),
                    source=["libre_nms"]
                ) for alert in alerts
            ]

        except Exception as e:
            self.logger.exception("Failed to get alerts from LibreNMS")
            raise Exception(f"Failed to get alerts from LibreNMS: {str(e)}")

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        
        if event.get("description") == "":
            description = event.get("title", "Could not fetch description")
        else:
            description = event.get("description", "Could not fetch description")

        alert = AlertDto(
            id=event.get("id"),
            name=event.get("name", "Could not fetch rule name"),
            status=LibreNmsProvider.STATUS_MAP.get(
                event.get("state"), AlertStatus.FIRING),
            severity=LibreNmsProvider.SEVERITY_MAP.get(
                event.get("severity"), AlertSeverity.INFO),
            timestamp=event.get("timestamp"),
            lastReceived=event.get("timestamp"),
            title=event.get("title", "Could not fetch title"),
            hostname=event.get("hostname", "Could not fetch hostname"),
            device_id=event.get("device_id", "Could not fetch device id"),
            sysDescr=event.get("sysDescr", "Could not fetch sysDescr"),
            sysName=event.get("sysName", "Could not fetch sysName"),
            sysContact=event.get("sysContact", "Could not fetch sysContact"),
            host_os=event.get("os", "Could not fetch host_os"),
            host_type=event.get("type", "Could not fetch host_type"),
            ip=event.get("ip", "Could not fetch ip"),
            display=event.get("display", "Could not fetch display"),
            version=event.get("version", "Could not fetch version"),
            hardware=event.get("hardware", "Could not fetch hardware"),
            features=event.get("features", "Could not fetch features"),
            serial=event.get("serial", "Could not fetch serial"),
            status_reason=event.get(
                "status_reason", "Could not fetch status_reason"),
            location=event.get("location", "Could not fetch location"),
            description=description,
            notes=event.get("notes", "Could not fetch notes"),
            uptime=event.get("uptime", "Could not fetch uptime"),
            uptime_sort=event.get(
                "uptime_sort", "Could not fetch uptime_sort"),
            uptime_long=event.get(
                "uptime_long", "Could not fetch uptime_long"),
            elapsed=event.get("elapsed", "Could not fetch elapsed"),
            alerted=event.get("alerted", "Could not fetch alerted"),
            alert_id=event.get("alert_id", "Could not fetch alert_id"),
            alert_notes=event.get(
                "alert_notes", "Could not fetch alert_notes"),
            proc=event.get("proc", "Could not fetch proc"),
            rule_id=event.get("rule_id", "Could not fetch rule_id"),
            faults=event.get("faults", "Could not fetch faults"),
            uid=event.get("uid", "Could not fetch uid"),
            rule=event.get("rule", "Could not fetch rule"),
            builder=event.get("builder", "Could not fetch builder"),
            source=["libre_nms"]
        )

        return alert


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[
                        logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    librenms_api_key = os.getenv("LIBRENMS_API_KEY")

    config = ProviderConfig(
        description="LibreNMS Provider",
        authentication={
            "host_url": "https://librenms.example.com",
            "api_key": librenms_api_key
        }
    )

    provider = LibreNmsProvider(context_manager, "libre_nms", config)

    alerts = provider.get_alerts()
    print(alerts)
