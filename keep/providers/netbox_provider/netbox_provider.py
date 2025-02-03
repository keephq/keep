"""
NetBox combines IP address management (IPAM) and datacenter infrastructure management (DCIM) with powerful APIs and extensions, serving as the ideal "source of truth" for network automation. Thousands of organizations worldwide rely on NetBox for their infrastructure.
"""

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

class NetboxProvider(BaseProvider):
  """
  Get alerts from NetBox into Keep.
  """

  webhook_description = ""
  webhook_template = ""
  webhook_markdown = """
  💡 For more details on how to configure NetBox to send alerts to Keep, see the [Keep documentation](https://docs.keephq.dev/providers/documentation/netbox-provider).

  To send alerts from NetBox to Keep, Use the following webhook url to configure NetBox send alerts to Keep:

  1. In NetBox, go to Webhooks under Operations.
  2. Create a new webhook with URL as {keep_webhook_api_url} and request method as POST.
  3. Disable SSL verification.
  4. Add 'X-API-KEY' as the request header with the value as {api_key}.
  5. Save the webhook.
  6. Go to Event Rules and create a new rule and select the webhook created in step 2 to receive alerts.
  """

  PROVIDER_DISPLAY_NAME = "NetBox"
  PROVIDER_TAGS = ["topology", "alert"]
  PROVIDER_CATEGORY = ["Cloud Infrastructure", "Monitoring"]

  def __init__(
      self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
  ):
      super().__init__(context_manager, provider_id, config)

  def validate_config(self):
      """
      Validates required configuration for NetBox's provider.
      """
      pass
  
  @staticmethod
  def _format_alert(
     event: dict, provider_instance: "BaseProvider" = None
  ) -> AlertDto:
     
     data = event.get("data", {})
     snapshots = event.get("snapshots", {})

     alert = AlertDto(
        name=data.get("name", "Could not fetch name"),
        lastReceived=event.get("timestamp"),
        startedAt=data.get("created"),
        model=event.get("model", "Could not fetch model"),
        username=event.get("username", "Could not fetch username"),
        id=event.get("request_id"),
        data=data,
        description=event.get("event", "Could not fetch event"),
        snapshots=snapshots,
        source=["netbox"]
     )
     
     return alert
  
if __name__ == "__main__":
  pass
