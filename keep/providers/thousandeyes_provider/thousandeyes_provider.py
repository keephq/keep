"""
Thousandseyes provider is a class that allows you to retrieve alerts from Thousandeyes using API endpoints as well as webhooks.
"""

import dataclasses

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

@pydantic.dataclasses.dataclass
class ThousandeyesProviderAuthConfig:
    """
    ThousandeyesProviderAuthConfig is a class that allows
    you to authenticate in Thousandeyes.
    """

    oauth2_token: str = dataclasses.field(
      metadata={
        "required": True,
        "description": "OAuth2 Bearer Token",
        "sensitive": True,
      },
    )

class ThousandeyesProvider(BaseProvider):
    """
    Get alerts from Thousandeyes into Keep.
    """

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
💡 For more details on how to configure ThousandEyes to send alerts to Keep, see the [Keep documentation](https://docs.keephq.dev/providers/documentation/thousandeyes-provider).

To send alerts from ThousandEyes to Keep, Use the following webhook url to configure ThousandEyes send alerts to Keep:

1. In ThousandEyes Dashboard, go to Network & App Synthetics > Agent Settings
2. Go to Notifications under Enterprise Agents and click on Notifications
3. Go to Notifications and create a new webhook notification
4. Give it a name and set the URL as {keep_webhook_api_url}&api_key={api_key}
5. Select Auth Type as None and Add New Webhook
6. Now, you have successfully configured ThousandEyes to send alerts to Keep
    """

    PROVIDER_DISPLAY_NAME = "ThousandEyes"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring", "Incident Management", "Cloud Infrastructure"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is Authenticated",
        )
    ]

    SEVERITY_MAP = {
        "info": AlertSeverity.INFO,
        "minor": AlertSeverity.WARNING,
        "major": AlertSeverity.HIGH,
        "critical": AlertSeverity.CRITICAL,
    }

    # Thousandeyes only supports severity. We map severity to status.
    STATUS_MAP = {
        "info": AlertStatus.PENDING,
        "minor": AlertStatus.ACKNOWLEDGED,
        "major": AlertStatus.FIRING,
        "critical": AlertStatus.FIRING
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
        Validates required configuration for Thousandeyes provider.
        """
        self.authentication_config = ThousandeyesProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        """
        Validates required scopes for Thousandeyes provider.
        """
        self.logger.info("Validating scopes for Thousandeyes provider")
        try:
            response = requests.get(
                "https://api.thousandeyes.com/v7/alerts",
                headers=self._generate_auth_headers()
            )

            response.raise_for_status()
            if response.status_code == 200:
                self.logger.info("Successfully validated scopes for Thousandeyes provider")
                return {"authenticated": True}

        except requests.exceptions.HTTPError as e:
            self.logger.exception("Error while validating scopes", extra={"error": str(e)})
            return {"authenticated": str(e)}

    def _generate_auth_headers(self):
        """
        Generate authentication headers for Thousandeyes.
        """
        return {
            "Authorization": "Bearer " + self.authentication_config.oauth2_token
        }
    
    def _get_alerts(self) -> list[AlertDto]:
        """
        Get alerts from Thousandeyes
        """

        self.logger.info("Getting alerts from Thousandeyes")
        try:
            response = requests.get(
                "https://api.thousandeyes.com/v7/alerts",
                headers=self._generate_auth_headers()
            )

            response.raise_for_status()
            if response.status_code == 200:
                alerts = response.json().get("alerts", [])

                alertDtos = []

                for alert in alerts:
                    id = alert.get("id")
                    alertId = alert.get("alertId")
                    name = alert.get("id")
                    description = alert.get("id")
                    ruleId = alert.get("ruleId")
                    alertRuleId = alert.get("alertRuleId")
                    state = alert.get("state", "Unable to fetch state")
                    alertState = alert.get("alertState", "Unable to fetch alert state")
                    dateStart = alert.get("dateStart")
                    startDate = alert.get("startDate")
                    startedAt = alert.get("startDate")
                    lastReceived = alert.get("startDate")
                    alertType = alert.get("alertType", "Unable to fetch alert type")
                    severity = ThousandeyesProvider.SEVERITY_MAP.get(alert.get("alertSeverity"), AlertSeverity.INFO)
                    status = ThousandeyesProvider.STATUS_MAP.get(alert.get("alertSeverity"), AlertStatus.PENDING)
                    violationCount = alert.get("violationCount", "Unable to fetch violation count")
                    duration = alert.get("duration", "Unable to fetch duration")
                    apiLinks = alert.get("apiLinks", [])
                    url = apiLinks[0].get("href", "http://unable-to-fetch-url") if apiLinks else "http://unable-to-fetch-url"
                    url2 = apiLinks[1].get("href", "http://unable-to-fetch-url") if len(apiLinks) > 1 else "http://unable-to-fetch-url"
                    permalink = alert.get("permalink", "Unable to fetch permalink")
                    suppressed = alert.get("suppressed", "Unable to fetch suppressed")
                    meta = alert.get("meta", {})
                    links = alert.get("_links", {})

                    alertDto = AlertDto(
                        id=id,
                        alertId=alertId,
                        name=name,
                        description=description,
                        ruleId=ruleId,
                        alertRuleId=alertRuleId,
                        state=state,
                        alertState=alertState,
                        dateStart=dateStart,
                        startDate=startDate,
                        startedAt=startedAt,
                        lastReceived=lastReceived,
                        alertType=alertType,
                        severity=severity,
                        status=status,
                        violationCount=violationCount,
                        duration=duration,
                        apiLinks=apiLinks,
                        url=url,
                        url2=url2,
                        permalink=permalink,
                        suppressed=suppressed,
                        meta=meta,
                        links=links,
                        source=["thousandeyes"]
                    )

                    alertDtos.append(alertDto)

                return alertDtos
            
        except Exception as e:
            self.logger.exception("Error while getting alerts")
            raise Exception("Error while getting alerts from Thousandeyes", str(e))
        
    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format alert from Thousandeyes.
        """

        alertData = event.get("alert", {})

        id = event.get("eventId")
        description = alertData.get("ruleExpression", "Unable to fetch description")
        severity_value = alertData.get("severity", "info").lower()
        severity = ThousandeyesProvider.SEVERITY_MAP.get(severity_value, AlertSeverity.INFO)
        status = ThousandeyesProvider.STATUS_MAP.get(severity_value, AlertStatus.PENDING)
        name = alertData.get("ruleName", "Unable to fetch test name")
        dateStartZoned = alertData.get("dateStartZoned", "Unable to fetch date start zoned")
        agentId = alertData.get("agent", {}).get("agentId", "Unable to fetch agent id")
        ipAddress = alertData.get("ipAddress", "Unable to fetch ip address")
        agentName = alertData.get("agentName", "Unable to fetch agent name")
        ruleExpression = alertData.get("ruleExpression", "Unable to fetch rule expression")
        alert_type = alertData.get("type", "Unable to fetch alert type")
        ruleAid = alertData.get("ruleAid", "Unable to fetch rule aid")
        hostname = alertData.get("hostname", "Unable to fetch hostname")
        dateStart = alertData.get("dateStart", "Unable to fetch date start")
        ruleName = alertData.get("ruleName", "Unable to fetch rule name")
        ruleId = alertData.get("ruleId", "Unable to fetch rule id")
        alertId = alertData.get("alertId", "Unable to fetch alert id")
        eventType = event.get("eventType", "Unable to fetch event type")
        apiLinks = alertData.get("apiLinks", [])
        url = apiLinks[0].get("href", "http://unable-to-fetch-url") if apiLinks else "http://unable-to-fetch-url"
        url2 = apiLinks[1].get("href", "http://unable-to-fetch-url") if len(apiLinks) > 1 else "http://unable-to-fetch-url"
        testLabels = alertData.get("testLabels", [])
        active = alertData.get("active", "Unable to fetch active")
        dateEnd = alertData.get("dateEnd", "Unable to fetch date end")
        agents = alertData.get("agents", [])
        testTargetsDescription = alertData.get("testTargetsDescription", [])
        violationCount = alertData.get("violationCount", "Unable to fetch violation count")
        dateEndZoned = alertData.get("dateEndZoned", "Unable to fetch date end zoned")
        testId = alertData.get("testId", "Unable to fetch test id")
        permalink = alertData.get("permalink", "Unable to fetch permalink")
        testName = alertData.get("testName", "Unable to fetch test name")

        alert = AlertDto(
            id=id,
            description=description,
            severity=severity,
            status=status,
            name=name,
            dateStartZoned=dateStartZoned,
            agentId=agentId,
            ipAddress=ipAddress,
            agentName=agentName,
            ruleExpression=ruleExpression,
            alert_type=alert_type,
            ruleAid=ruleAid,
            hostname=hostname,
            dateStart=dateStart,
            ruleName=ruleName,
            ruleId=ruleId,
            alertId=alertId,
            eventType=eventType,
            apiLinks=apiLinks,
            url=url,
            url2=url2,
            testLabels=testLabels,
            active=active,
            dateEnd=dateEnd,
            agents=agents,
            testTargetsDescription=testTargetsDescription,
            violationCount=violationCount,
            dateEndZoned=dateEndZoned,
            testId=testId,
            permalink=permalink,
            testName=testName,
            source=["thousandeyes"]
        )

        return alert
    
if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[
        logging.StreamHandler()
    ])

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    oauth2_token = os.getenv("THOUSANDEYES_OAUTH2_TOKEN")

    config = ProviderConfig(
        description="Thousandeyes provider",
        authentication={
            "oauth2_token": oauth2_token
        }
    )

    provider = ThousandeyesProvider(context_manager, "thousandeyes", config)

    alerts = provider.get_alerts()
    print(alerts)
