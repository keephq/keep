"""
Nagios Provider is a class that allows to ingest/digest data from Nagios monitoring system.

Nagios is an open-source monitoring system that monitors network services, hosts, and other infrastructure.
This provider supports:
- NRDP (Nagios Remote Data Processor) API
- Nagios Core CGI API

For more information:
- https://www.nagios.org/
- https://github.com/NagiosEnterprises/nrdp
"""

import dataclasses
import datetime
import json
import logging
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    Nagios authentication configuration.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios Host URL",
            "sensitive": False,
            "hint": "https://nagios.example.com",
            "validation": "any_http_url",
        }
    )

    # NRDP API Token (for NRDP API)
    nrdp_token: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "NRDP API Token (for NRDP API)",
            "sensitive": True,
            "hint": "Your NRDP API token",
        },
        default=None,
    )

    # Nagios Core CGI credentials (for CGI API)
    username: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "Nagios CGI Username (for Core CGI API)",
            "sensitive": False,
        },
        default=None,
    )

    password: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "description": "Nagios CGI Password (for Core CGI API)",
            "sensitive": True,
        },
        default=None,
    )

    api_type: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "API Type to use (nrdp or cgi)",
            "sensitive": False,
            "hint": "nrdp (recommended) or cgi",
        },
        default="nrdp",
    )

    verify_ssl: bool = dataclasses.field(
        metadata={
            "required": False,
            "description": "Verify SSL certificates",
            "sensitive": False,
            "hint": "Set to false for self-signed certificates",
        },
        default=True,
    )


class NagiosProvider(BaseProvider):
    """
    Pull alerts from Nagios monitoring system into Keep.
    """

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated with valid credentials",
            mandatory=True,
        ),
    ]

    # Nagios host/service state mapping
    # 0 = OK/UP, 1 = WARNING, 2 = CRITICAL/DOWN, 3 = UNKNOWN/UNREACHABLE
    STATUS_MAP = {
        0: AlertStatus.RESOLVED,
        1: AlertStatus.FIRING,
        2: AlertStatus.FIRING,
        3: AlertStatus.FIRING,
    }

    SEVERITY_MAP = {
        0: AlertSeverity.LOW,
        1: AlertSeverity.WARNING,
        2: AlertSeverity.CRITICAL,
        3: AlertSeverity.INFO,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """
        Validates the configuration of the Nagios provider.
        """
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

        # Validate that at least one auth method is provided
        if self.authentication_config.api_type == "nrdp":
            if not self.authentication_config.nrdp_token:
                raise ProviderException(
                    "NRDP token is required when using NRDP API type"
                )
        elif self.authentication_config.api_type == "cgi":
            if not self.authentication_config.username or not self.authentication_config.password:
                raise ProviderException(
                    "Username and password are required when using CGI API type"
                )
        else:
            raise ProviderException(
                f"Invalid API type: {self.authentication_config.api_type}. Use 'nrdp' or 'cgi'"
            )

    def __get_base_url(self) -> str:
        """Get the base URL for Nagios."""
        url = str(self.authentication_config.host_url)
        if url.endswith("/"):
            url = url[:-1]
        return url

    def __get_nrdp_url(self) -> str:
        """Get the NRDP API URL."""
        return f"{self.__get_base_url()}/nrdp"

    def __get_cgi_url(self) -> str:
        """Get the CGI API URL."""
        return f"{self.__get_base_url()}/cgi-bin"

    def __make_nrdp_request(self, command: str) -> dict:
        """Make a request to the NRDP API."""
        url = self.__get_nrdp_url()
        
        data = {
            "token": self.authentication_config.nrdp_token,
            "cmd": command,
            "json": "1",
        }

        try:
            response = requests.post(
                url,
                data=data,
                verify=self.authentication_config.verify_ssl,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"NRDP API request failed: {e}")
            raise ProviderException(f"NRDP API request failed: {e}")

    def __make_cgi_request(self, endpoint: str, params: dict = None) -> dict:
        """Make a request to the Nagios Core CGI API."""
        url = f"{self.__get_cgi_url()}/{endpoint}"
        
        try:
            response = requests.get(
                url,
                params=params,
                auth=(
                    self.authentication_config.username,
                    self.authentication_config.password,
                ),
                verify=self.authentication_config.verify_ssl,
                timeout=30,
            )
            response.raise_for_status()
            
            # Try to parse as JSON first, some endpoints return JSON
            try:
                return response.json()
            except json.JSONDecodeError:
                # Some endpoints return HTML, extract what we can
                return {"raw": response.text}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"CGI API request failed: {e}")
            raise ProviderException(f"CGI API request failed: {e}")

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate the scopes of the provider by attempting authentication.
        """
        try:
            if self.authentication_config.api_type == "nrdp":
                # Try to get host status to validate credentials
                result = self.__make_nrdp_request("gethosts")
                if result.get("result", {}).get("code") == 0:
                    scopes = {"authenticated": True}
                else:
                    scopes = {
                        "authenticated": f"Authentication failed: {result.get('result', {}).get('message', 'Unknown error')}"
                    }
            else:
                # CGI API - try to access statusjson.cgi
                result = self.__make_cgi_request("statusjson.cgi", {"query": "hostlist"})
                if "data" in result or "raw" in result:
                    scopes = {"authenticated": True}
                else:
                    scopes = {"authenticated": "Authentication failed"}
                    
        except Exception as e:
            scopes = {
                "authenticated": f"Error validating scopes: {e}",
            }

        return scopes

    def __get_host_alerts_nrdp(self) -> list[AlertDto]:
        """Get host alerts using NRDP API."""
        try:
            result = self.__make_nrdp_request("gethosts")
            
            if result.get("result", {}).get("code") != 0:
                raise ProviderException(
                    f"NRDP returned error: {result.get('result', {}).get('message')}"
                )

            hosts = result.get("data", [])
            alerts = []

            for host in hosts:
                state = host.get("current_state", 0)
                # Only include hosts that are not UP (state != 0)
                if state != 0:
                    alerts.append(
                        AlertDto(
                            id=f"host_{host.get('host_name', 'unknown')}",
                            name=host.get("host_name", "Unknown Host"),
                            description=host.get("plugin_output", "No output"),
                            status=self.STATUS_MAP.get(state, AlertStatus.FIRING),
                            severity=self.SEVERITY_MAP.get(state, AlertSeverity.INFO),
                            source=["nagios"],
                            host=host.get("host_name"),
                            lastReceived=datetime.datetime.fromtimestamp(
                                host.get("last_check", 0)
                            ).isoformat(),
                            acknowledged=host.get("problem_has_been_acknowledged", 0) == 1,
                            url=f"{self.__get_base_url()}/cgi-bin/extinfo.cgi?type=1&host={host.get('host_name', '')}",
                        )
                    )

            return alerts

        except Exception as e:
            logger.error(f"Error getting host alerts from NRDP: {e}")
            raise ProviderException(f"Error getting host alerts from NRDP: {e}")

    def __get_service_alerts_nrdp(self) -> list[AlertDto]:
        """Get service alerts using NRDP API."""
        try:
            result = self.__make_nrdp_request("getservicestatus")
            
            if result.get("result", {}).get("code") != 0:
                raise ProviderException(
                    f"NRDP returned error: {result.get('result', {}).get('message')}"
                )

            services = result.get("data", [])
            alerts = []

            for service in services:
                state = service.get("current_state", 0)
                # Only include services that are not OK (state != 0)
                if state != 0:
                    host_name = service.get("host_name", "Unknown")
                    service_desc = service.get("service_description", "Unknown")
                    
                    alerts.append(
                        AlertDto(
                            id=f"service_{host_name}_{service_desc}",
                            name=f"{host_name}: {service_desc}",
                            description=service.get("plugin_output", "No output"),
                            status=self.STATUS_MAP.get(state, AlertStatus.FIRING),
                            severity=self.SEVERITY_MAP.get(state, AlertSeverity.INFO),
                            source=["nagios"],
                            host=host_name,
                            service=service_desc,
                            lastReceived=datetime.datetime.fromtimestamp(
                                service.get("last_check", 0)
                            ).isoformat(),
                            acknowledged=service.get("problem_has_been_acknowledged", 0) == 1,
                            url=f"{self.__get_base_url()}/cgi-bin/extinfo.cgi?type=2&host={host_name}&service={service_desc}",
                        )
                    )

            return alerts

        except Exception as e:
            logger.error(f"Error getting service alerts from NRDP: {e}")
            raise ProviderException(f"Error getting service alerts from NRDP: {e}")

    def _get_alerts(self) -> list[AlertDto]:
        """
        Get all alerts from Nagios.
        """
        alerts = []

        if self.authentication_config.api_type == "nrdp":
            try:
                self.logger.info("Collecting host alerts from Nagios NRDP")
                host_alerts = self.__get_host_alerts_nrdp()
                alerts.extend(host_alerts)
            except Exception as e:
                self.logger.error(f"Error getting host alerts from Nagios: {e}")

            try:
                self.logger.info("Collecting service alerts from Nagios NRDP")
                service_alerts = self.__get_service_alerts_nrdp()
                alerts.extend(service_alerts)
            except Exception as e:
                self.logger.error(f"Error getting service alerts from Nagios: {e}")
        
        else:
            # CGI API implementation - limited support
            self.logger.info("CGI API support is limited. Consider using NRDP API.")
            try:
                result = self.__make_cgi_request("statusjson.cgi", {"query": "hostlist"})
                # Parse CGI response (simplified)
                data = result.get("data", {})
                hostlist = data.get("hostlist", {})
                
                for host_name, host_info in hostlist.items():
                    state = host_info.get("status", 0)
                    if state != 0:
                        alerts.append(
                            AlertDto(
                                id=f"host_{host_name}",
                                name=host_name,
                                description=host_info.get("plugin_output", "No output"),
                                status=self.STATUS_MAP.get(state, AlertStatus.FIRING),
                                severity=self.SEVERITY_MAP.get(state, AlertSeverity.INFO),
                                source=["nagios"],
                                host=host_name,
                            )
                        )
            except Exception as e:
                self.logger.error(f"Error getting alerts from Nagios CGI: {e}")

        return alerts


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    host_url = os.environ.get("NAGIOS_HOST_URL")
    nrdp_token = os.environ.get("NAGIOS_NRDP_TOKEN")
    username = os.environ.get("NAGIOS_USERNAME")
    password = os.environ.get("NAGIOS_PASSWORD")
    api_type = os.environ.get("NAGIOS_API_TYPE", "nrdp")

    if not host_url:
        raise ProviderException("NAGIOS_HOST_URL is required")

    auth_config = {
        "host_url": host_url,
        "api_type": api_type,
    }

    if api_type == "nrdp":
        if not nrdp_token:
            raise ProviderException("NAGIOS_NRDP_TOKEN is required for NRDP API")
        auth_config["nrdp_token"] = nrdp_token
    else:
        if not username or not password:
            raise ProviderException("NAGIOS_USERNAME and NAGIOS_PASSWORD are required for CGI API")
        auth_config["username"] = username
        auth_config["password"] = password

    config = ProviderConfig(
        description="Nagios Provider",
        authentication=auth_config,
    )

    provider = NagiosProvider(
        context_manager,
        provider_id="nagios",
        config=config,
    )

    alerts = provider._get_alerts()
    print(f"Found {len(alerts)} alerts")
    for alert in alerts:
        print(f"- {alert.name}: {alert.status} ({alert.severity})")
