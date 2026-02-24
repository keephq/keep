"""Nagios webhook provider for ingesting host/service notifications into Keep."""

from datetime import datetime, timezone
from typing import Any

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class NagiosProvider(BaseProvider):
    """Get alerts from Nagios into Keep."""

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["id"]

    HOST_STATE_SEVERITY_MAP = {
        "UP": AlertSeverity.INFO,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
        "PENDING": AlertSeverity.INFO,
    }

    HOST_STATE_STATUS_MAP = {
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
        "PENDING": AlertStatus.PENDING,
    }

    SERVICE_STATE_SEVERITY_MAP = {
        "OK": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
        "PENDING": AlertSeverity.INFO,
    }

    SERVICE_STATE_STATUS_MAP = {
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
        "PENDING": AlertStatus.PENDING,
    }

    NOTIFICATION_TYPE_STATUS_MAP = {
        "PROBLEM": AlertStatus.FIRING,
        "RECOVERY": AlertStatus.RESOLVED,
        "ACKNOWLEDGEMENT": AlertStatus.ACKNOWLEDGED,
        "ACKNOWLEDGMENT": AlertStatus.ACKNOWLEDGED,
        "CUSTOM": AlertStatus.ACKNOWLEDGED,
        "FLAPPINGSTART": AlertStatus.FIRING,
        "FLAPPINGSTOP": AlertStatus.RESOLVED,
        "FLAPPINGDISABLED": AlertStatus.RESOLVED,
        "DOWNTIMESTART": AlertStatus.SUPPRESSED,
        "DOWNTIMEEND": AlertStatus.FIRING,
        "DOWNTIMECANCELLED": AlertStatus.FIRING,
    }

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
1. Configure Nagios notifications to call Keep's webhook URL.
2. Send Nagios macros as form fields or JSON keys.
3. Use webhook URL `{keep_webhook_api_url}`.
4. Include at least: `NOTIFICATIONTYPE`, `HOSTNAME`, `HOSTSTATE`/`SERVICESTATE`.
5. Optional but recommended: `HOSTPROBLEMID`/`SERVICEPROBLEMID`, `SHORTDATETIME`.
"""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """Dispose provider resources."""
        pass

    def validate_config(self) -> None:
        """No validation required for Nagios webhook provider."""
        pass

    @staticmethod
    def _get(event: dict, *keys: str) -> Any:
        for key in keys:
            if key in event and event.get(key) not in ("", None):
                return event.get(key)
        return None

    @staticmethod
    def _normalize(value: Any) -> str | None:
        if value is None:
            return None
        return str(value).strip().upper()

    @staticmethod
    def _normalize_notification_type(value: Any) -> str | None:
        normalized = NagiosProvider._normalize(value)
        if not normalized:
            return None
        # Accept values like "DOWNTIME START" / "DOWNTIME_START"
        return normalized.replace(" ", "").replace("_", "")

    @staticmethod
    def _is_service_alert(event: dict, service: str | None) -> bool:
        if service:
            return True

        object_type = NagiosProvider._normalize(
            NagiosProvider._get(event, "objecttype", "object_type", "OBJECTTYPE")
        )
        return object_type == "SERVICE"

    @staticmethod
    def _parse_last_received(event: dict) -> str:
        default = datetime.now(timezone.utc).isoformat()
        raw = NagiosProvider._get(
            event,
            "lastReceived",
            "timestamp",
            "time",
            "datetime",
            "date_time",
            "shortdatetime",
            "SHORTDATETIME",
            "longdatetime",
            "LONGDATETIME",
        )
        if not raw:
            return default

        raw = str(raw).strip()
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat()
        except ValueError:
            pass

        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%a %b %d %H:%M:%S %Z %Y",
            "%a %b %d %H:%M:%S %z %Y",
        ):
            try:
                dt = datetime.strptime(raw, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc).isoformat()
            except ValueError:
                continue

        # Let AlertDto validator perform final validation/conversion attempt.
        return raw

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: BaseProvider = None
    ) -> AlertDto | list[AlertDto]:
        event = event or {}

        service = NagiosProvider._get(
            event,
            "servicedesc",
            "service_desc",
            "service",
            "SERVICEDESC",
        )
        host = NagiosProvider._get(
            event,
            "hostname",
            "host",
            "host_name",
            "HOSTNAME",
            "hostdisplayname",
            "host_display_name",
            "HOSTDISPLAYNAME",
        )

        notification_type = NagiosProvider._normalize_notification_type(
            NagiosProvider._get(
                event,
                "notificationtype",
                "notification_type",
                "NOTIFICATIONTYPE",
            )
        )
        service_state = NagiosProvider._normalize(
            NagiosProvider._get(
                event,
                "servicestate",
                "service_state",
                "SERVICESTATE",
                "state",
            )
        )
        host_state = NagiosProvider._normalize(
            NagiosProvider._get(
                event,
                "hoststate",
                "host_state",
                "HOSTSTATE",
                "state",
            )
        )

        is_service_alert = NagiosProvider._is_service_alert(event, service)
        state = service_state if is_service_alert else host_state

        severity_map = (
            NagiosProvider.SERVICE_STATE_SEVERITY_MAP
            if is_service_alert
            else NagiosProvider.HOST_STATE_SEVERITY_MAP
        )
        status_map = (
            NagiosProvider.SERVICE_STATE_STATUS_MAP
            if is_service_alert
            else NagiosProvider.HOST_STATE_STATUS_MAP
        )

        severity = severity_map.get(state, AlertSeverity.INFO)
        status = NagiosProvider.NOTIFICATION_TYPE_STATUS_MAP.get(
            notification_type, status_map.get(state, AlertStatus.FIRING)
        )

        output = NagiosProvider._get(
            event,
            "serviceoutput",
            "service_output",
            "SERVICEOUTPUT",
            "hostoutput",
            "host_output",
            "HOSTOUTPUT",
            "output",
        )
        long_output = NagiosProvider._get(
            event,
            "longserviceoutput",
            "long_service_output",
            "LONGSERVICEOUTPUT",
            "longhostoutput",
            "long_host_output",
            "LONGHOSTOUTPUT",
            "long_output",
        )

        alert_id = NagiosProvider._get(
            event,
            "id",
            "notificationid",
            "notification_id",
            "NOTIFICATIONID",
            "problemid",
            "serviceproblemid",
            "hostproblemid",
            "problem_id",
        )
        if not alert_id:
            alert_id = ":".join(
                [
                    host or "unknown-host",
                    service or "host",
                    notification_type or "EVENT",
                    state or "UNKNOWN",
                ]
            )

        name = f"{host} - {service}" if service else (host or "Nagios host alert")
        note = NagiosProvider._get(
            event,
            "notificationcomment",
            "notification_comment",
            "comment",
            "SERVICEACKCOMMENT",
            "HOSTACKCOMMENT",
        )
        description = note or output or name

        return AlertDto(
            id=str(alert_id),
            name=name,
            status=status,
            severity=severity,
            lastReceived=NagiosProvider._parse_last_received(event),
            description=description,
            message=output,
            long_output=long_output,
            service=service,
            source=["nagios"],
            pushed=True,
            host=host,
            notification_type=notification_type,
            labels={
                "notification_type": notification_type,
                "state": state,
                "object_type": "service" if is_service_alert else "host",
            },
            note=note,
        )
