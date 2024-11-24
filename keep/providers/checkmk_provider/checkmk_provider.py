"""
Checkmk is a monitoring tool for Infrastructure and Application Monitoring.
"""

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class CheckmkProvider(BaseProvider):
    """Get alerts from Checkmk into Keep"""

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
  💡 For more details on how to configure Checkmk to send alerts to Keep, see the [Keep documentation](https://docs.keephq.dev/providers/documentation/checkmk-provider).
  1. Checkmk supports custom notification scripts.
  2. Install Keep webhook script following the [Keep documentation](https://docs.keephq.dev/providers/documentation/checkmk-provider).
  3. In Checkmk WebUI, go to Setup.
  4. Click on Add rule.
  5. In the Notifications method section, select Webhook - KeepHQ and choose "Call with the following parameters:".
  6. Configure the Rule properties, Contact selections, and Conditions according to your requirements.
  7. The first parameter is the Webhook URL of Keep which is {keep_webhook_api_url}.
  8. The second parameter is the API Key of Keep which is {api_key}.
  9. Click on Save.
  10. Now Checkmk will be able to send alerts to Keep.
  """

    SEVERITIES_MAP = {
        "OK": AlertSeverity.INFO,
        "WARN": AlertSeverity.WARNING,
        "CRIT": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACH": AlertStatus.FIRING,
    }

    PROVIDER_DISPLAY_NAME = "Checkmk"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["id"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config():
        """
        No validation required for Checkmk provider.
        """
        pass

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: BaseProvider = None
    ) -> AlertDto | list[AlertDto]:
        """
        Service alerts and Host alerts have different fields, so we are mapping the fields based on the event type.
        """

        def _check_values(value):
            if value not in event or event.get(value) == "":
                return None
            return event.get(value)

        """
    Service alerts don't have a status field, so we are mapping the status based on the severity.
    """

        def _set_severity(status):
            if status == "UP":
                return AlertSeverity.INFO
            elif status == "DOWN":
                return AlertSeverity.CRITICAL
            elif status == "UNREACH":
                return AlertSeverity.CRITICAL

        alert = AlertDto(
            id=_check_values("id"),
            name=_check_values("check_command"),
            description=_check_values("summary"),
            severity=CheckmkProvider.SEVERITIES_MAP.get(
                event.get("severity"), _set_severity(event.get("status"))
            ),
            status=CheckmkProvider.STATUS_MAP.get(
                event.get("status"), AlertStatus.FIRING
            ),
            host=_check_values("host"),
            alias=_check_values("alias"),
            address=_check_values("address"),
            service_name=_check_values("service"),
            source=["checkmk"],
            current_event=_check_values("event"),
            output=_check_values("output"),
            long_output=_check_values("long_output"),
            path_url=_check_values("url"),
            perf_data=_check_values("perf_data"),
            site=_check_values("site"),
            what=_check_values("what"),
            notification_type=_check_values("notification_type"),
            contact_name=_check_values("contact_name"),
            contact_email=_check_values("contact_email"),
            contact_pager=_check_values("contact_pager"),
            date=_check_values("date"),
            lastReceived=_check_values("short_date_time"),
            long_date=_check_values("long_date_time"),
        )

        return alert


if __name__ == "__main__":
    pass
