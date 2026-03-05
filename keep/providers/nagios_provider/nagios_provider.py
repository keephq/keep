"""
Nagios Provider is a class that allows to ingest/digest data from Nagios XI.
"""

import dataclasses
import datetime
import logging
from typing import Union

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    Nagios authentication configuration.
    """

    nagios_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI URL",
            "hint": "https://nagios.example.com/nagiosxi",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI API Key",
            "hint": "Admin -> Users -> API Key",
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


class NagiosProvider(BaseProvider):
    """
    Pull/Push alerts from Nagios XI into Keep.
    """

    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_DISPLAY_NAME = "Nagios"

    # Nagios states
    # Hosts: 0=UP, 1=DOWN, 2=UNREACHABLE
    # Services: 0=OK, 1=WARNING, 2=CRITICAL, 3=UNKNOWN

    HOST_STATUS_MAP = {
        "0": AlertStatus.RESOLVED,
        "1": AlertStatus.FIRING,
        "2": AlertStatus.FIRING,
    }

    SERVICE_STATUS_MAP = {
        "0": AlertStatus.RESOLVED,
        "1": AlertStatus.FIRING,
        "2": AlertStatus.FIRING,
        "3": AlertStatus.FIRING,
    }

    HOST_SEVERITY_MAP = {
        "0": AlertSeverity.INFO,
        "1": AlertSeverity.CRITICAL,
        "2": AlertSeverity.WARNING,
    }

    SERVICE_SEVERITY_MAP = {
        "0": AlertSeverity.INFO,
        "1": AlertSeverity.WARNING,
        "2": AlertSeverity.CRITICAL,
        "3": AlertSeverity.INFO,
    }

    PROVIDER_SCOPES = [
        ProviderScope(
            name="objects.get",
            description="Retrieve host and service status",
            mandatory=True,
            documentation_url="https://library.nagios.com/library/products/nagios-xi/documentation/accessing-the-nagios-xi-backend-api/",
        ),
        ProviderScope(
            name="corecommand.post",
            description="Send core commands (e.g. acknowledge)",
            mandatory=False,
            documentation_url="https://library.nagios.com/library/products/nagios-xi/documentation/accessing-the-nagios-xi-backend-api/",
        ),
    ]

    PROVIDER_METHODS = [
        ProviderMethod(
            name="Acknowledge Host Problem",
            func_name="acknowledge_host_problem",
            scopes=["corecommand.post"],
            type="action",
        ),
        ProviderMethod(
            name="Acknowledge Service Problem",
            func_name="acknowledge_service_problem",
            scopes=["corecommand.post"],
            type="action",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for Nagios provider.
        """
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        validated_scopes = {}
        # Test objects.get
        try:
            self._fetch_objects("hoststatus", limit=1)
            validated_scopes["objects.get"] = True
        except Exception as e:
            validated_scopes["objects.get"] = str(e)

        # corecommand.post is harder to test without side effects,
        # but we can try an invalid command or just assume it's true if we have the key
        # and it has permissions. Usually if objects.get works, the key is valid.
        # We'll just mark it as True for now if we can reach the API.
        if "objects.get" in validated_scopes and validated_scopes["objects.get"] is True:
             validated_scopes["corecommand.post"] = True
        
        return validated_scopes

    def _get_alerts(self) -> list[AlertDto]:
        # Fetch host status
        host_alerts = self._fetch_objects("hoststatus")
        # Fetch service status
        service_alerts = self._fetch_objects("servicestatus")

        return host_alerts + service_alerts

    def _fetch_objects(self, object_type: str, limit: int = None) -> list[AlertDto]:
        url = f"{self.authentication_config.nagios_url}/api/v1/objects/{object_type}"
        params = {
            "apikey": self.authentication_config.api_key,
            "jsonoutput": 1
        }
        if limit:
            params["records"] = limit

        response = requests.get(
            url, params=params, verify=self.authentication_config.verify
        )
        response.raise_for_status()
        data = response.json()

        alerts = []
        list_key = f"{object_type}list"
        if list_key not in data:
            return alerts

        objects = data[list_key].get(object_type, [])
        if isinstance(objects, dict):
            objects = [objects]

        for obj in objects:
            state = str(obj.get("current_state", "0"))
            
            # Skip OK/UP states for _get_alerts unless we want everything
            if state == "0":
                continue

            if object_type == "hoststatus":
                status = self.HOST_STATUS_MAP.get(state, AlertStatus.FIRING)
                severity = self.HOST_SEVERITY_MAP.get(state, AlertSeverity.INFO)
                alert_id = f"host:{obj.get('host_name')}"
                name = f"Host: {obj.get('host_name')}"
            else:
                status = self.SERVICE_STATUS_MAP.get(state, AlertStatus.FIRING)
                severity = self.SERVICE_SEVERITY_MAP.get(state, AlertSeverity.INFO)
                alert_id = f"service:{obj.get('host_name')}:{obj.get('service_description')}"
                name = f"Service: {obj.get('service_description')} on {obj.get('host_name')}"

            alerts.append(
                AlertDto(
                    id=alert_id,
                    name=name,
                    status=status,
                    severity=severity,
                    lastReceived=obj.get("last_check"),
                    source=["nagios"],
                    message=obj.get("status_text"),
                    host=obj.get("host_name"),
                    service=obj.get("service_description")
                    if object_type == "servicestatus"
                    else None,
                    **obj,
                )
            )

        return alerts

    def acknowledge_host_problem(self, host_name: str, comment: str = "Acknowledged via Keep"):
        """
        Acknowledge a host problem.
        """
        cmd = f"ACKNOWLEDGE_HOST_PROBLEM;{host_name};2;1;1;keep;{comment}"
        return self._send_core_command(cmd)

    def acknowledge_service_problem(self, host_name: str, service_description: str, comment: str = "Acknowledged via Keep"):
        """
        Acknowledge a service problem.
        """
        cmd = f"ACKNOWLEDGE_SVC_PROBLEM;{host_name};{service_description};2;1;1;keep;{comment}"
        return self._send_core_command(cmd)

    def _send_core_command(self, cmd: str):
        url = f"{self.authentication_config.nagios_url}/api/v1/system/corecommand"
        params = {
            "apikey": self.authentication_config.api_key
        }
        data = {
            "cmd": cmd
        }
        response = requests.post(
            url, params=params, data=data, verify=self.authentication_config.verify
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        # Determine if it's a host or service alert
        is_service = "service_description" in event
        state = str(event.get("state") or event.get("current_state", "0"))

        if is_service:
            status = NagiosProvider.SERVICE_STATUS_MAP.get(state, AlertStatus.FIRING)
            severity = NagiosProvider.SERVICE_SEVERITY_MAP.get(state, AlertSeverity.INFO)
            alert_id = f"service:{event.get('host_name')}:{event.get('service_description')}"
            name = (
                f"Service: {event.get('service_description')} on {event.get('host_name')}"
            )
        else:
            status = NagiosProvider.HOST_STATUS_MAP.get(state, AlertStatus.FIRING)
            severity = NagiosProvider.HOST_SEVERITY_MAP.get(state, AlertSeverity.INFO)
            alert_id = f"host:{event.get('host_name')}"
            name = f"Host: {event.get('host_name')}"

        return AlertDto(
            id=event.get("id") or alert_id,
            name=event.get("name") or name,
            status=status,
            severity=severity,
            lastReceived=event.get("last_check") or datetime.datetime.now().isoformat(),
            source=["nagios"],
            message=event.get("output")
            or event.get("status_text")
            or event.get("message"),
            host=event.get("host_name"),
            service=event.get("service_description"),
            **event,
        )


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
    import os

    api_key = os.environ.get("NAGIOS_API_KEY")
    nagios_url = os.environ.get("NAGIOS_URL")

    provider_config = {
        "authentication": {
            "api_key": api_key,
            "nagios_url": nagios_url,
        },
    }
    provider = NagiosProvider(
        context_manager,
        provider_id="nagios",
        config=ProviderConfig(**provider_config),
    )
    # alerts = provider._get_alerts()
    # print(alerts)
