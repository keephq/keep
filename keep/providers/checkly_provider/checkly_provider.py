"""
ChecklyProvider is a class that allows you to receive alerts from Checkly using API endpoints as well as webhooks.
"""

import dataclasses

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

@pydantic.dataclasses.dataclass
class ChecklyProviderAuthConfig:
    """
    ChecklyProviderAuthConfig is a class that allows you to authenticate in Checkly.
    """

    checklyApiKey: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Checkly API Key",
            "sensitive": True,
        },
    )

    accountId: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Checkly Account ID",
            "sensitive": True,
        },
    )

class ChecklyProvider(BaseProvider):
    """
    Get alerts from Checkly into Keep.
    """
    
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
💡 For more details on how to configure Checkly to send alerts to Keep, see the [Keep documentation](https://docs.keephq.dev/providers/documentation/checkly-provider).

To send alerts from Checkly to Keep, Use the following webhook url to configure Checkly send alerts to Keep:

1. In Checkly dashboard open "Alerts" tab.
2. Click on "Add more channels".
3. Select "Webhook" from the list.
4. Enter a name for the webhook, select the method as "POST" and enter the webhook URL as {keep_webhook_api_url}.
5. Copy the Body template from the [Keep documentation](https://docs.keephq.dev/providers/documentation/checkly-provider) and paste it in the Body field of the webhook.
6. Add a request header with the key "X-API-KEY" and the value as {api_key}.
7. Save the webhook.
    """

    PROVIDER_DISPLAY_NAME = "Checkly"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read alerts from Checkly",
        ),
    ]

    # Based on the Alert states in Checkly, we map them to the AlertStatus and AlertSeverity in Keep.
    STATUS_MAP = {
        "NO_ALERT": AlertStatus.RESOLVED,
        "ALERT_DEGRADED": AlertStatus.FIRING,
        "ALERT_FAILURE": AlertStatus.FIRING,
        "ALERT_DEGRADED_REMAIN": AlertStatus.ACKNOWLEDGED,
        "ALERT_DEGRADED_RECOVERY": AlertStatus.RESOLVED,
        "ALERT_DEGRADED_FAILURE": AlertStatus.FIRING,
        "ALERT_FAILURE_REMAIN": AlertStatus.ACKNOWLEDGED,
        "ALERT_FAILURE_DEGRADED": AlertStatus.ACKNOWLEDGED,
        "ALERT_RECOVERY": AlertStatus.RESOLVED
    }

    SEVERITY_MAP = {
        "NO_ALERT": AlertSeverity.INFO,
        "ALERT_DEGRADED": AlertSeverity.WARNING,
        "ALERT_FAILURE": AlertSeverity.CRITICAL,
        "ALERT_DEGRADED_REMAIN": AlertSeverity.WARNING,
        "ALERT_DEGRADED_RECOVERY": AlertSeverity.INFO,
        "ALERT_DEGRADED_FAILURE": AlertSeverity.HIGH,
        "ALERT_FAILURE_REMAIN": AlertSeverity.CRITICAL,
        "ALERT_FAILURE_DEGRADED": AlertSeverity.WARNING,
        "ALERT_RECOVERY": AlertSeverity.INFO
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
        Validates required configuration for ilert provider.
        """
        self.authentication_config = ChecklyProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        """
        Validate scopes for the provider
        """
        self.logger.info("Validating Checkly provider scopes")
        try:
            response = requests.get(
                self.__get_url(),
                headers=self.__get_auth_headers(),
            )

            if response.status_code != 200:
                response.raise_for_status()

            self.logger.info("Successfully validated scopes", extra={"response": response.json()})

            return {"read_alerts": True}
            
        except Exception as e:
            self.logger.exception("Failed to validate scopes", extra={"error": e})
            return {"read_alerts": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        """
        Get alerts from Checkly.
        """
        self.logger.info("Getting alerts from Checkly")
        alerts = self.__get_paginated_data()
        return [
            AlertDto(
                id=alert["id"],
                name=alert["name"],
                status=ChecklyProvider.STATUS_MAP[alert["alertType"]],
                severity=ChecklyProvider.SEVERITY_MAP[alert["alertType"]],
                lastReceivedAt=alert["created_at"],
                alertType=alert["alertType"],
                checkId=alert["checkId"],
                checkType=alert["checkType"],
                runLocation=alert["runLocation"],
                responseTime=alert["responseTime"],
                error=alert["error"],
                statusCode=alert["statusCode"],
                created_at=alert["created_at"],
                startedAt=alert["startedAt"],
                source=["checkly"]
            ) for alert in alerts
        ]
    
    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        alert = AlertDto(
            id=event["uuid"],
            name=event["check_name"],
            description=event["event"],
            status=ChecklyProvider.STATUS_MAP[event["alert_type"]],
            severity=ChecklyProvider.SEVERITY_MAP[event["alert_type"]],
            lastReceived=event["started_at"],
            alertType=event["alert_type"],
            groupName=event["group_name"],
            checkId=event["check_id"],
            checkType=event["check_type"],
            checkResultId=event["check_result_id"],
            checkErrorMessage=event["check_error_message"],
            responseTime=event["response_time"],
            apiCheckResponseStatus=event["api_check_response_status_code"],
            apiCheckResponseStatusText=event["api_check_response_status_text"],
            runLocation=event["run_location"],
            sslDaysRemaining=event["ssl_days_remaining"],
            sslCheckDomain=event["ssl_check_domain"],
            startedAt=event["started_at"],
            tags=event["tags"],
            url=event["link"],
            region=event["region"],
            source=["checkly"]
        )

        return alert

        
    def __get_auth_headers(self):
        return {
            "Authorization": f"Bearer {self.authentication_config.checklyApiKey}",
            "X-Checkly-Account": self.authentication_config.accountId,
            "accept": "application/json"
        }
    
    def __get_paginated_data(self, query_params: dict = {}) -> list:
        data = []
        page = 1

        while True:
            self.logger.info(f"Getting data from page {page}")
            query_params["page"] = page
            try:
                url = self.__get_url(query_params)
                headers = self.__get_auth_headers()
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                page_data = response.json()
                if not page_data:
                    break
                self.logger.info(f"Got {len(page_data)} data from page {page}")
                data.extend(page_data)
                page += 1
            except Exception as e:
                self.logger.error(f"Error getting data from page {page}: {e}")
                break
        return data
    
    def __get_url(self, query_params: dict = {}):
        url = f"https://api.checklyhq.com/v1/check-alerts"
        if query_params:
          url += "?"
          for key, value in query_params.items():
            url += f"{key}={value}&"
          url = url[:-1]
        return url
    
if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    checkly_api_key = os.getenv("CHECKLY_API_KEY")
    checkly_account_id = os.getenv("CHECKLY_ACCOUNT_ID")

    config = ProviderConfig(
        description="Checkly Provider",
        authentication={
            "checklyApiKey": checkly_api_key,
            "accountId": checkly_account_id,
        }
    )

    provider = ChecklyProvider(context_manager, "checkly", config)

    alerts = provider.get_alerts()
    print(alerts)
