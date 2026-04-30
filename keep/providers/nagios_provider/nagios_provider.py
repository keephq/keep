"""
Nagios Provider is a class that allows fetching alerts from Nagios as Keep alerts.
"""

import dataclasses
import datetime
import logging
import typing
import uuid

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    Nagios authentication configuration.
    """

    host: str = dataclasses.field(
        default="localhost",
        metadata={
            "required": True,
            "description": "Nagios server hostname or IP address",
            "hint": "nagios.example.com",
        },
    )
    port: int = dataclasses.field(
        default=80,
        metadata={
            "required": False,
            "description": "Nagios server port",
            "hint": "80 (HTTP) or 443 (HTTPS)",
        },
    )
    use_https: bool = dataclasses.field(
        default=False,
        metadata={
            "required": False,
            "description": "Use HTTPS for connection",
            "hint": "True for HTTPS, False for HTTP",
        },
    )
    username: str = dataclasses.field(
        default="",
        metadata={
            "required": True,
            "description": "Nagios CGI username",
            "hint": "nagiosadmin",
        },
    )
    password: str = dataclasses.field(
        default="",
        metadata={
            "required": True,
            "description": "Nagios CGI password",
            "sensitive": True,
        },
    )
    # Path prefix if Nagios is behind a reverse proxy
    url_prefix: str = dataclasses.field(
        default="/nagios",
        metadata={
            "required": False,
            "description": "URL prefix for Nagios CGI path",
            "hint": "/nagios",
        },
    )


class NagiosProvider(BaseProvider):
    """
    Nagios provider class that polls Nagios for host and service alerts
    and pushes them as Keep alerts.
    """

    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read alerts from Nagios",
            mandatory=True,
            alias="Read Alerts",
        )
    ]
    PROVIDER_TAGS = ["monitoring", "nagios"]

    # Nagios state severity mapping
    SEVERITY_MAP = {
        "CRITICAL": "critical",
        "DOWN": "critical",
        "UNREACHABLE": "critical",
        "WARNING": "warning",
        "UNKNOWN": "info",
        "UP": "info",
        "OK": "info",
        "RECOVERY": "info",
        "PENDING": "low",
    }

    STATUS_MAP = {
        "CRITICAL": "firing",
        "DOWN": "firing",
        "UNREACHABLE": "firing",
        "WARNING": "firing",
        "UNKNOWN": "firing",
        "UP": "resolved",
        "OK": "resolved",
        "RECOVERY": "resolved",
        "PENDING": "pending",
    }

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

    def _get_base_url(self) -> str:
        """Build the base URL for Nagios CGI endpoints."""
        scheme = "https" if self.authentication_config.use_https else "http"
        host = self.authentication_config.host
        port = self.authentication_config.port
        prefix = self.authentication_config.url_prefix.rstrip("/")

        if (self.authentication_config.use_https and port == 443) or (
            not self.authentication_config.use_https and port == 80
        ):
            return f"{scheme}://{host}{prefix}"
        return f"{scheme}://{host}:{port}{prefix}"

    def validate_scopes(self) -> dict:
        """
        Validate that the Nagios provider can connect and read alerts.
        """
        scopes = {"read_alerts": True}
        try:
            url = f"{self._get_base_url()}/cgi-bin/statusjson.cgi?query=hostlist"
            response = requests.get(
                url,
                auth=(
                    self.authentication_config.username,
                    self.authentication_config.password,
                ),
                timeout=10,
                verify=False,
            )
            if response.status_code == 401:
                self.err = "Authentication failed: invalid credentials"
                scopes["read_alerts"] = self.err
            elif response.status_code != 200:
                self.err = f"Unexpected status code: {response.status_code}"
                scopes["read_alerts"] = self.err
        except requests.exceptions.ConnectionError as e:
            self.err = f"Connection error: {str(e)[:200]}"
            scopes["read_alerts"] = self.err
        except Exception as e:
            self.err = f"Error validating Nagios connection: {str(e)[:200]}"
            scopes["read_alerts"] = self.err

        return scopes

    def dispose(self):
        """No resources to dispose."""
        pass

    def _query(self, **kwargs) -> typing.List[dict]:
        """
        Query Nagios for host and service problems.
        Returns a list of alert dicts.
        """
        base_url = self._get_base_url()
        auth = (
            self.authentication_config.username,
            self.authentication_config.password,
        )
        alerts = []

        # Fetch host problems
        try:
            host_url = f"{base_url}/cgi-bin/statusjson.cgi?query=hostlist&hoststatus=1"
            response = requests.get(host_url, auth=auth, timeout=30, verify=False)
            if response.status_code == 200:
                data = response.json()
                host_list = data.get("data", {}).get("hostlist", {})
                for host_name, host_info in host_list.items():
                    alert = self._format_host_alert(host_name, host_info)
                    if alert:
                        alerts.append(alert)
        except Exception as e:
            self.logger.warning(f"Error fetching Nagios host alerts: {e}")

        # Fetch service problems
        try:
            service_url = f"{base_url}/cgi-bin/statusjson.cgi?query=servicelist&servicestatus=1"
            response = requests.get(service_url, auth=auth, timeout=30, verify=False)
            if response.status_code == 200:
                data = response.json()
                service_list = data.get("data", {}).get("servicelist", {})
                for host_name, services in service_list.items():
                    for service_name, service_info in services.items():
                        alert = self._format_service_alert(
                            host_name, service_name, service_info
                        )
                        if alert:
                            alerts.append(alert)
        except Exception as e:
            self.logger.warning(f"Error fetching Nagios service alerts: {e}")

        return alerts

    def _format_host_alert(self, host_name: str, host_info: dict) -> dict:
        """Format a Nagios host alert into Keep alert format."""
        host_state = host_info.get("status", "UP")
        severity = self.SEVERITY_MAP.get(host_state, "info")
        status = self.STATUS_MAP.get(host_state, "firing")

        # Only push non-OK alerts
        if status == "resolved" and host_state not in ("DOWN", "UNREACHABLE"):
            return None

        return {
            "id": f"nagios-host-{host_name}",
            "name": f"Host {host_state}: {host_name}",
            "status": status,
            "severity": severity,
            "lastReceived": host_info.get("last_check", datetime.datetime.now(datetime.timezone.utc).isoformat()),
            "environment": "production",
            "service": "infrastructure",
            "source": ["nagios"],
            "message": host_info.get(
                "status_information", f"Host {host_name} is {host_state}"
            ),
            "description": host_info.get(
                "plugin_output", f"Nagios host {host_name} status: {host_state}"
            ),
            "nagios": {
                "host_name": host_name,
                "host_state": host_state,
                "host_address": host_info.get("address", ""),
                "last_check": host_info.get("last_check", ""),
                "current_attempt": host_info.get("current_attempt", ""),
                "state_type": host_info.get("state_type", ""),
            },
        }

    def _format_service_alert(
        self, host_name: str, service_name: str, service_info: dict
    ) -> dict:
        """Format a Nagios service alert into Keep alert format."""
        service_state = service_info.get("status", "OK")
        severity = self.SEVERITY_MAP.get(service_state, "info")
        status = self.STATUS_MAP.get(service_state, "firing")

        # Only push non-OK alerts
        if status == "resolved":
            return None

        return {
            "id": f"nagios-service-{host_name}-{service_name}",
            "name": f"Service {service_state}: {service_name} on {host_name}",
            "status": status,
            "severity": severity,
            "lastReceived": service_info.get("last_check", datetime.datetime.now(datetime.timezone.utc).isoformat()),
            "environment": "production",
            "service": service_name.lower(),
            "source": ["nagios"],
            "message": service_info.get(
                "status_information",
                f"Service {service_name} on {host_name} is {service_state}",
            ),
            "description": service_info.get(
                "plugin_output",
                f"Nagios service {service_name} on {host_name}: {service_state}",
            ),
            "nagios": {
                "host_name": host_name,
                "service_description": service_name,
                "service_state": service_state,
                "host_address": service_info.get("host_address", ""),
                "last_check": service_info.get("last_check", ""),
                "current_attempt": service_info.get("current_attempt", ""),
                "state_type": service_info.get("state_type", ""),
            },
        }

    @staticmethod
    def _format_alert(event: dict) -> dict:
        """Format a webhook/push alert from Nagios into Keep alert format."""
        # Nagios can send notifications via URL-encoded POST or JSON
        severity = NagiosProvider.SEVERITY_MAP.get(
            event.get("NOTIFICATIONTYPE", event.get("hoststate", event.get("servicestate", ""))),
            "info",
        )
        status = NagiosProvider.STATUS_MAP.get(
            event.get("NOTIFICATIONTYPE", event.get("hoststate", event.get("servicestate", ""))),
            "firing",
        )

        host_name = event.get("HOSTNAME", event.get("host_name", "unknown"))
        service_desc = event.get("SERVICEDESC", event.get("service_description", ""))

        if service_desc:
            name = f"Service {event.get('SERVICESTATE', event.get('servicestate', 'UNKNOWN'))}: {service_desc} on {host_name}"
        else:
            name = f"Host {event.get('HOSTSTATE', event.get('hoststate', 'UNKNOWN'))}: {host_name}"

        return {
            "id": event.get("NOTIFICATIONID", str(uuid.uuid4())),
            "name": name,
            "status": status,
            "severity": severity,
            "lastReceived": event.get(
                "LONGDATETIME", datetime.datetime.now(datetime.timezone.utc).isoformat()
            ),
            "environment": "production",
            "service": service_desc.lower() if service_desc else "infrastructure",
            "source": ["nagios"],
            "message": event.get(
                "NOTIFICATIONCOMMENT",
                event.get("HOSTOUTPUT", event.get("SERVICEOUTPUT", "")),
            ),
            "description": event.get(
                "HOSTOUTPUT",
                event.get(
                    "SERVICEOUTPUT",
                    event.get("NOTIFICATIONMESSAGE", ""),
                ),
            ),
        }


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    os.environ["KEEP_API_URL"] = "http://localhost:8080"

    from keep.api.core.dependencies import SINGLE_TENANT_UUID
    from keep.providers.providers_factory import ProvidersFactory

    context_manager = ContextManager(tenant_id=SINGLE_TENANT_UUID)
    config = {
        "authentication": {
            "host": "nagios.example.com",
            "port": 80,
            "use_https": False,
            "username": "nagiosadmin",
            "password": "password",
        }
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="nagios-keephq",
        provider_type="nagios",
        provider_config=config,
    )
    alerts = provider._query()
    print(f"Found {len(alerts)} alerts")
    for alert in alerts:
        print(alert)