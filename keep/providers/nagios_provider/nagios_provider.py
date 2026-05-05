"""
Nagios is an open-source monitoring system for hosts, services and network resources.
"""

import logging
from datetime import datetime, timezone

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

logger = logging.getLogger(__name__)


class NagiosProvider(BaseProvider):
    """Get alerts from Nagios into Keep via custom notification command."""

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
  1. Nagios supports custom notification commands.
  2. Copy the `webhook-keep.py` script onto the Nagios server (e.g. `/usr/local/nagios/libexec/webhook-keep.py`) and make it executable.
  3. Define a new command in `commands.cfg` that runs the script for both host and service notifications. Pass `{keep_webhook_api_url}` and `{api_key}` as macros (e.g. via `$ARG1$` and `$ARG2$`) so they are forwarded to the script as environment variables (`KEEP_WEBHOOK_URL`, `KEEP_API_KEY`).
  4. Reference the new command in your contact's `host_notification_commands` and `service_notification_commands`.
  5. Reload Nagios configuration. New host/service problems and recoveries will now reach Keep.
  """

    # Nagios service states (from $SERVICESTATE$): OK, WARNING, UNKNOWN, CRITICAL
    # Nagios host states (from $HOSTSTATE$):     UP, DOWN, UNREACHABLE
    SEVERITIES_MAP = {
        "OK": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "UNKNOWN": AlertSeverity.INFO,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UP": AlertSeverity.INFO,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.CRITICAL,
    }

    # Nagios notification types (from $NOTIFICATIONTYPE$):
    # PROBLEM, RECOVERY, ACKNOWLEDGEMENT, FLAPPINGSTART, FLAPPINGSTOP,
    # FLAPPINGDISABLED, DOWNTIMESTART, DOWNTIMEEND, DOWNTIMECANCELLED, CUSTOM
    STATUS_MAP = {
        "PROBLEM": AlertStatus.FIRING,
        "RECOVERY": AlertStatus.RESOLVED,
        "ACKNOWLEDGEMENT": AlertStatus.ACKNOWLEDGED,
        "FLAPPINGSTART": AlertStatus.FIRING,
        "FLAPPINGSTOP": AlertStatus.RESOLVED,
        "FLAPPINGDISABLED": AlertStatus.RESOLVED,
        "DOWNTIMESTART": AlertStatus.SUPPRESSED,
        "DOWNTIMEEND": AlertStatus.FIRING,
        "DOWNTIMECANCELLED": AlertStatus.FIRING,
        "CUSTOM": AlertStatus.FIRING,
    }

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["host", "service"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config():
        """Nagios uses webhook-only ingestion; no provider-side config to validate."""
        pass

    @staticmethod
    def _safe_get(event: dict, key: str, default=None):
        value = event.get(key)
        if value is None or value == "":
            return default
        return value

    @staticmethod
    def _parse_timestamp(value: str | None) -> str:
        """Parse Nagios $LONGDATETIME$ / $SHORTDATETIME$ to UTC ISO 8601.

        Falls back to current UTC if the value is missing or unparseable.
        Nagios common formats:
          - $LONGDATETIME$:  "Sun Mar 15 14:23:42 UTC 2026"
          - $SHORTDATETIME$: "03-15-2026 14:23:42"
          - epoch:           "1710512622"
        """
        if not value:
            return datetime.now(timezone.utc).isoformat()

        # Epoch seconds
        if value.isdigit():
            try:
                return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
            except (ValueError, OSError):
                pass

        formats = [
            "%a %b %d %H:%M:%S %Z %Y",  # LONGDATETIME with named zone
            "%a %b %d %H:%M:%S %z %Y",  # LONGDATETIME with offset
            "%m-%d-%Y %H:%M:%S",        # SHORTDATETIME (date_format=us)
            "%d-%m-%Y %H:%M:%S",        # SHORTDATETIME (date_format=euro)
            "%Y-%m-%d %H:%M:%S",        # SHORTDATETIME (date_format=iso8601)
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(value, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc).isoformat()
            except ValueError:
                continue

        logger.warning("Could not parse Nagios timestamp %r; using current UTC", value)
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: BaseProvider = None
    ) -> AlertDto | list[AlertDto]:
        """Map a Nagios notification payload to an AlertDto.

        The webhook script forwards Nagios environment variables as a flat dict.
        Both host and service notifications are supported; service notifications
        take precedence when both `service_description` and host fields are set.
        """
        get = NagiosProvider._safe_get

        notification_type = get(event, "notification_type", "PROBLEM")
        is_service = bool(get(event, "service_description"))

        if is_service:
            state = get(event, "service_state", "UNKNOWN")
            output = get(event, "service_output")
            long_output = get(event, "long_service_output")
            check_command = get(event, "service_check_command")
            problem_id = get(event, "service_problem_id")
            duration = get(event, "service_duration")
            attempt = get(event, "service_attempt")
            url = get(event, "service_action_url") or get(event, "service_notes_url")
        else:
            state = get(event, "host_state", "UP")
            output = get(event, "host_output")
            long_output = get(event, "long_host_output")
            check_command = get(event, "host_check_command")
            problem_id = get(event, "host_problem_id")
            duration = get(event, "host_duration")
            attempt = get(event, "host_attempt")
            url = get(event, "host_action_url") or get(event, "host_notes_url")

        last_received = NagiosProvider._parse_timestamp(
            get(event, "long_date_time") or get(event, "short_date_time")
        )

        # Severity follows the underlying state; recoveries are mapped to INFO.
        severity_key = state if notification_type != "RECOVERY" else "OK" if is_service else "UP"
        severity = NagiosProvider.SEVERITIES_MAP.get(severity_key, AlertSeverity.WARNING)
        status = NagiosProvider.STATUS_MAP.get(notification_type, AlertStatus.FIRING)

        host = get(event, "host_name") or get(event, "host")
        service = get(event, "service_description") or get(event, "service")

        # Stable id: prefer Nagios-provided problem_id, fall back to host[/service]+timestamp
        alert_id = problem_id or f"{host}-{service or 'host'}-{last_received}"
        name = service or host or "nagios-alert"

        return AlertDto(
            id=alert_id,
            name=name,
            description=output,
            severity=severity,
            status=status,
            host=host,
            address=get(event, "host_address"),
            alias=get(event, "host_alias"),
            service=service,
            source=["nagios"],
            output=output,
            long_output=long_output,
            check_command=check_command,
            current_attempt=attempt,
            duration=duration,
            notification_type=notification_type,
            contact_name=get(event, "contact_name"),
            contact_email=get(event, "contact_email"),
            contact_pager=get(event, "contact_pager"),
            path_url=url,
            lastReceived=last_received,
        )


if __name__ == "__main__":
    pass
