"""
Wazuh is a security platform that provides unified XDR and SIEM protection for endpoints and cloud workloads
"""

from keep.api.models.alert import AlertDto, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class WazuhProvider(BaseProvider):
    """Get alerts from Wazuh into Keep"""

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
  💡 For more details on how to configure Wazuh to send alerts to Keep, see the [Keep documentation](https://docs.keephq.dev/providers/documentation/wazuh-provider).
  1. Wazuh supports custom integration scripts.
  2. Install Keep integration scripts following the [Keep documentation](https://docs.keephq.dev/providers/documentation/wazuh-provider).
  3. Open the Wazuh configuration file
  4. You will need to parameters: Webhook URL of Keep which is {keep_webhook_api_url}.
  5. And the second parameter: API Key of Keep which is {api_key}.
  6. Add `<integration>` including proper `api_key` and `webhook_url` block in Wazuh configuration according to the the [Keep documentation](https://docs.keephq.dev/providers/documentation/wazuh-provider)
  7. Restart Wazuh.
  8. Now Wazuh will be able to send alerts to Keep.
  """

    PROVIDER_DISPLAY_NAME = "Wazuh"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["id"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config():
        """
        No validation required for Wazuh provider.
        """
        pass

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: BaseProvider = None
    ) -> AlertDto | list[AlertDto]:
        alert = AlertDto(
            name=event["message"],
            description=event["description"],
            severity=event["severity"],
            # @TODO: handle alert resolve
            status=AlertStatus.FIRING,
            source=["wazuh"],
            lastReceived=event["created_at"],
        )
        alert.fingerprint =WazuhProvider.get_alert_fingerprint(
            alert, fingerprint_fields=WazuhProvider.FINGERPRINT_FIELDS
        )

        return alert


if __name__ == "__main__":
    pass
