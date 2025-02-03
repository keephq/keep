"""
Dash0 Provider allows to receive alerts from Dash0 using Webhook.
"""

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

class Dash0Provider(BaseProvider):
  """
  Get alerts from Dash0 into Keep.
  """

  webhook_description = ""
  webhook_template = ""
  webhook_markdown = """
💡 For more details on how to configure Dash0 to send alerts to Keep, see the [Keep documentation](https://docs.keephq.dev/providers/documentation/dash0-provider).

To send alerts from Dash0 to Keep, Use the following webhook url to configure Dash0 send alerts to Keep:

1. In Dash0, go to Organization settings.
2. Go to Notification Channels and create a New notification channel with type Webhook.
3. Give a name to the notification channel and use {keep_webhook_api_url} as the URL.
4. Add a request header with the key "x-api-key" and the value as {api_key}.
5. Save the configuration.
6. Go to Notifications under Alerting in the left sidebar and create a New notification rule if required or change the Notification channel to webhook created in step 3 for an existing Notification Rule.
7. Go to Checks under Alerting in the left sidebar and create a New Check Rule according to your requirements and assign the Notification Rule.
"""

  STATUS_MAP = {
    "critical": AlertStatus.FIRING,
    "degraded": AlertStatus.FIRING,
    "resolved": AlertStatus.RESOLVED,
  }

  # Dash0 doesn't have severity levels, so we map status to severity levels manually.
  SEVERITIES_MAP = {
    "critical": AlertSeverity.CRITICAL,
    "degraded": AlertSeverity.WARNING,
    "resolved": AlertSeverity.INFO,
  }

  PROVIDER_DISPLAY_NAME = "Dash0"
  PROVIDER_TAGS = ["alert"]
  PROVIDER_CATEGORY = ["Monitoring"]

  def __init__(
      self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
  ):
      super().__init__(context_manager, provider_id, config)

  def validate_config(self):
      """
      Validates required configuration for Dash0's provider.
      """
      pass
  
  @staticmethod
  def _format_alert(
     event: dict, provider_instance: "BaseProvider" = None
  ) -> AlertDto:

    data = event.get("data")
    issue = data.get("issue")

    alert = AlertDto(
       id=issue.get("id"),
       name=issue.get("summary", "Could not fetch summary"),
       type=event.get("type", "Could not fetch type"),
       description=issue.get("description", "Could not fetch description"),
       summary=issue.get("summary", "Could not fetch summary"),
       url=issue.get("url"),
       status=Dash0Provider.STATUS_MAP.get(issue.get("status"), AlertStatus.FIRING),
       severity=Dash0Provider.SEVERITIES_MAP.get(issue.get("status"), AlertSeverity.CRITICAL),
       lastReceived=issue.get("end", issue.get("start")),
       startedAt=issue.get("start", issue.get("end")),
       labels=issue.get("labels", []),
       checkrules=issue.get("checkrules", []),
       source=["dash0"],
    )

    return alert

if __name__ == "__main__":
    pass
