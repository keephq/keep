"""
Site24x7Provider is a class that allows to install webhooks and get alerts in Site24x7.
"""

import dataclasses
from typing import List
from urllib.parse import urlencode, urljoin

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


class ResourceAlreadyExists(Exception):
    def __init__(self, *args):
        super().__init__(*args)


@pydantic.dataclasses.dataclass
class Site24X7ProviderAuthConfig:
    """
    Site24x7 authentication configuration.
    """

    zohoRefreshToken: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zoho Refresh Token",
            "hint": "Refresh token for Zoho authentication",
            "sensitive": True,
        },
    )
    zohoClientId: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zoho Client Id",
            "hint": "Client Secret for Zoho authentication.",
            "sensitive": True,
        },
    )
    zohoClientSecret: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zoho Client Secret",
            "hint": "Password associated with yur account",
            "sensitive": True,
        },
    )
    zohoAccountTLD: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zoho Account's TLD (.com | .eu | .com.cn | .in | .au | .jp)",
            "hint": "Possible: .com | .eu | .com.cn | .in | .com.au | .jp",
            "validation": "tld"
        },
    )


class Site24X7Provider(BaseProvider):
    """Install Webhooks and receive alerts from Site24x7."""

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is Authenticated",
            mandatory=True,
            mandatory_for_webhook=True,
            alias="Rules Reader",
        ),
        ProviderScope(
            name="valid_tld",
            description="TLD is amongst the list [.com | .eu | .com.cn | .in | .com.au | .jp]",
            mandatory=True,
            mandatory_for_webhook=True,
            alias="Valid TLD",
        ),
    ]
    PROVIDER_CATEGORY = ["Monitoring"]
    SEVERITIES_MAP = {
        "DOWN": AlertSeverity.WARNING,
        "TROUBLE": AlertSeverity.HIGH,
        "UP": AlertSeverity.INFO,
        "CRITICAL": AlertSeverity.CRITICAL,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Site24x7 provider.
        """
        self.authentication_config = Site24X7ProviderAuthConfig(
            **self.config.authentication
        )

    def __get_url(self, paths: List[str] = [], query_params: dict = None, **kwargs):
        """
        Helper method to build the url for Site24x7 api requests.

        Example:

        paths = ["issue", "createmeta"]
        query_params = {"projectKeys": "key1"}
        url = __get_url("test", paths, query_params)

        # url = https://site24x7.com/api/2/issue/createmeta?projectKeys=key1
        """

        url = urljoin(
            f"https://www.site24x7{self.authentication_config.zohoAccountTLD}/api/",
            "/".join(str(path) for path in paths),
        )

        # add query params
        if query_params:
            url = f"{url}?{urlencode(query_params)}"

        return url

    def __get_headers(self):
        """
        Getting the access token from Zoho API using the permanent refresh token.
        """
        data = {
            "client_id": self.authentication_config.zohoClientId,
            "client_secret": self.authentication_config.zohoClientSecret,
            "refresh_token": self.authentication_config.zohoRefreshToken,
            "grant_type": "refresh_token",
        }
        response = requests.post(
            f"https://accounts.zoho{self.authentication_config.zohoAccountTLD}/oauth/v2/token",
            data=data,
        ).json()
        return {
            "Authorization": f'Bearer {response["access_token"]}',
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        valid_tlds = [".com", ".eu", ".com.cn", ".in", ".com.au", ".jp"]
        valid_tld_scope = "TLD not in [.com | .eu | .com.cn | .in | .com.au | .jp]"
        authentication_scope = "Validate TLD first"
        if self.authentication_config.zohoAccountTLD in valid_tlds:
            valid_tld_scope = True
            response = requests.get(
                f'{self.__get_url(paths=["monitors"])}', headers=self.__get_headers()
            )
            if response.status_code == 401:
                authentication_scope = response.json()
                self.logger.error(
                    "Failed to authenticate user", extra=authentication_scope
                )
            elif response.status_code == 200:
                authentication_scope = True
                self.logger.info("Authenticated user successfully")
            else:
                authentication_scope = (
                    f"Error while authenticating user, {response.status_code}"
                )
                self.logger.error(
                    "Error while authenticating user",
                    extra={"status_code": response.status_code},
                )
        return {
            "authenticated": authentication_scope,
            "valid_tld": valid_tld_scope,
        }

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        webhook_data = {
            "method": "P",
            "down_alert": True,
            "is_poller_webhook": False,
            "type": 8,
            "alert_tags_id": [],
            "custom_headers": [{"name": "X-API-KEY", "value": api_key}],
            "url": keep_api_url,
            "timeout": 30,
            "selection_type": 0,
            "send_in_json_format": True,
            "auth_method": "B",
            "trouble_alert": True,
            "critical_alert": True,
            "send_incident_parameters": True,
            "service_status": 0,
            "name": "KeepWebhook",
            "manage_tickets": False,
        }
        response = requests.post(
            self.__get_url(paths=["integration/webhooks"]),
            json=webhook_data,
            headers=self.__get_headers(),
        )
        if not response.ok:
            response_json = response.json()
            self.logger.error("Error while creating webhook", extra=response_json)
            raise Exception(response_json["message"])
        else:
            self.logger.info("Webhook created successfully")

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        return AlertDto(
            url=event.get("MONITORURL", ""),
            lastReceived=event.get("INCIDENT_TIME", ""),
            description=event.get("INCIDENT_REASON", ""),
            name=event.get("MONITORNAME", ""),
            id=event.get("MONITOR_ID", ""),
            severity=Site24X7Provider.SEVERITIES_MAP.get(event.get("STATUS", "DOWN")),
        )

    def _get_alerts(self) -> list[AlertDto]:
        response = requests.get(
            self.__get_url(paths=["alert_logs"]), headers=self.__get_headers()
        )
        if response.status_code == 200:
            alerts = []
            response = response.json()
            for alert in response["data"]:
                alerts.append(
                    AlertDto(
                        name=alert["display_name"],
                        title=alert["msg"],
                        startedAt=alert["sent_time"],
                    )
                )
            return alerts
        else:
            self.logger.error("Failed to get alerts", extra=response.json())
            raise Exception("Could not get alerts")
