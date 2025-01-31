"""
Checkmk is a monitoring tool for Infrastructure and Application Monitoring.
"""

import logging
from datetime import datetime, timezone

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


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
        "ACKNOWLEDGED": AlertStatus.ACKNOWLEDGED,
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
    def convert_to_utc_isoformat(long_date_time: str, default: str) -> str:
        logger.info(f"Converting {long_date_time} to UTC ISO format")
        try:
            # Parse the short_date_time string to a datetime object
            local_dt = datetime.strptime(long_date_time, "%a %b %d %H:%M:%S %Z %Y")

            # Convert to UTC
            # Note: The original code assumes the input is in local time, but your input includes a timezone (CEST).
            # You might need to handle timezone conversion if necessary.
            utc_dt = local_dt.astimezone(timezone.utc)

            # Return the ISO 8601 format
            return utc_dt.isoformat()
        except Exception:
            logger.exception(f"Error converting {long_date_time} to UTC ISO format")
            return default

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

        # Service alerts don't have a status field, so we are mapping the status based on the severity.
        def _set_severity(status):
            if status == "UP":
                return AlertSeverity.INFO
            elif status == "DOWN":
                return AlertSeverity.CRITICAL
            elif status == "UNREACH":
                return AlertSeverity.CRITICAL

        # https://forum.checkmk.com/t/convert-notify-shortdatetime-to-utc-timezone/20158/2
        microtime = _check_values("micro_time")
        logger.info(f"Microtime: {microtime}")
        if microtime:
            ts = int(int(microtime) / 1000000)
            dt_object = datetime.fromtimestamp(ts)
            last_received = dt_object.isoformat()
        else:
            last_received = CheckmkProvider.convert_to_utc_isoformat(
                _check_values("long_date_time"), _check_values("short_date_time")
            )

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
            service=_check_values("service"),
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
            lastReceived=last_received,
            long_date=_check_values("long_date_time"),
        )

        return alert


if __name__ == "__main__":
    pass
