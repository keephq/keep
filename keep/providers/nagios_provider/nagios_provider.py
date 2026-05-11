"""
Nagios Provider is a class that allows to ingest/digest alerts from Nagios XI and Nagios Core.

Nagios sends notifications via user-defined commands. To push alerts into Keep, configure
a Nagios contact that runs a curl command (or script) posting to Keep's webhook endpoint:

  keep_api_url  = https://<keep-host>/alerts/event/nagios
  keep_api_key  = <your Keep API key>

Example Nagios commands (nagios.cfg / commands.cfg):

  # Host notification
  define command {
      command_name  notify-host-by-keep
      command_line  /usr/bin/curl -s -X POST "$KEEP_API_URL$" \
          -H "Content-Type: application/json" \
          -H "X-API-KEY: $KEEP_API_KEY$" \
          -d '{"notification_type":"$NOTIFICATIONTYPE$","hostname":"$HOSTNAME$","hoststate":"$HOSTSTATE$","hostaddress":"$HOSTADDRESS$","hostoutput":"$HOSTOUTPUT$","timestamp":"$LONGDATETIME$"}'
  }

  # Service notification
  define command {
      command_name  notify-service-by-keep
      command_line  /usr/bin/curl -s -X POST "$KEEP_API_URL$" \
          -H "Content-Type: application/json" \
          -H "X-API-KEY: $KEEP_API_KEY$" \
          -d '{"notification_type":"$NOTIFICATIONTYPE$","hostname":"$HOSTNAME$","hostaddress":"$HOSTADDRESS$","servicedesc":"$SERVICEDESC$","servicestate":"$SERVICESTATE$","serviceoutput":"$SERVICEOUTPUT$","timestamp":"$LONGDATETIME$"}'
  }

For Nagios XI, you can also enable the built-in webhook / outbound notification feature
in Admin → Outbound Notifications and point it at the Keep endpoint above.
"""

import dataclasses
import datetime
import logging

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    Nagios authentication configuration.

    For webhook-only mode (Nagios Core) all fields are optional — Keep simply
    receives POSTs from Nagios notification commands and no outbound API calls
    are made.

    For Nagios XI, supply ``nagios_url`` and ``api_key`` to enable Keep to pull
    active alerts via the Nagios XI REST API.
    """

    nagios_url: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Base URL of the Nagios XI instance (e.g. https://nagios.example.com/nagiosxi)",
            "hint": "https://nagios.example.com/nagiosxi",
            "sensitive": False,
            "validation": "any_http_url",
        },
        default="",
    )
    api_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Nagios XI API key (Admin → Account Info → API Key)",
            "hint": "Found in Nagios XI under Admin → Account Info",
            "sensitive": True,
        },
        default="",
    )
    verify_ssl: bool = dataclasses.field(
        metadata={
            "description": "Verify SSL certificates when contacting the Nagios XI API",
            "hint": "Set to false to allow self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )


class NagiosProvider(BaseProvider):
    """
    Ingest host/service alerts from Nagios XI and Nagios Core into Keep.

    Webhook mode (Nagios Core & XI):
        Configure Nagios notification commands to POST JSON payloads to
        ``/alerts/event/nagios``.  See the module docstring for example
        command definitions.

    Pull mode (Nagios XI only):
        Supply ``nagios_url`` and ``api_key`` in the provider configuration.
        Keep will poll ``/api/v1/objects/hoststatus`` and
        ``/api/v1/objects/servicestatus`` to retrieve current alert state.
    """

    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_DISPLAY_NAME = "Nagios"
    WEBHOOK_INSTALLATION_REQUIRED = False

    PROVIDER_SCOPES = [
        ProviderScope(
            name="api_access",
            description="Access the Nagios XI REST API to pull host/service status.",
            mandatory=False,
            mandatory_for_webhook=False,
            documentation_url="https://assets.nagios.com/downloads/nagiosxi/docs/Nagios-XI-REST-API-Reference-Guide.pdf",
        ),
    ]

    # Nagios service/host state → AlertSeverity
    SEVERITIES_MAP: dict = {
        # Service states
        "ok": AlertSeverity.INFO,
        "warning": AlertSeverity.WARNING,
        "critical": AlertSeverity.CRITICAL,
        "unknown": AlertSeverity.INFO,
        # Host states
        "up": AlertSeverity.INFO,
        "down": AlertSeverity.CRITICAL,
        "unreachable": AlertSeverity.HIGH,
    }

    # Nagios notification_type / state → AlertStatus
    STATUS_MAP: dict = {
        # notification_type values
        "problem": AlertStatus.FIRING,
        "recovery": AlertStatus.RESOLVED,
        "acknowledgement": AlertStatus.ACKNOWLEDGED,
        "flappingstart": AlertStatus.FIRING,
        "flappingstop": AlertStatus.RESOLVED,
        "downtimestart": AlertStatus.SUPPRESSED,
        "downtimeend": AlertStatus.RESOLVED,
        "downtimecancelled": AlertStatus.RESOLVED,
        # Explicit host/service state names (used in pull mode)
        "up": AlertStatus.RESOLVED,
        "ok": AlertStatus.RESOLVED,
        "down": AlertStatus.FIRING,
        "unreachable": AlertStatus.FIRING,
        "warning": AlertStatus.FIRING,
        "critical": AlertStatus.FIRING,
        "unknown": AlertStatus.FIRING,
    }

    FINGERPRINT_FIELDS = ["hostname", "servicedesc"]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self) -> None:
        """Parse and validate the provider authentication configuration."""
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self) -> None:
        """No persistent connections to clean up."""
        pass

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Verify that the configured Nagios XI API key has read access.

        Returns a mapping of scope name → True on success or an error string.
        """
        scopes: dict[str, bool | str] = {}
        if not self.authentication_config.nagios_url or not self.authentication_config.api_key:
            scopes["api_access"] = "nagios_url and api_key are not configured (webhook-only mode)"
            return scopes

        try:
            url = (
                f"{self.authentication_config.nagios_url.rstrip('/')}"
                f"/api/v1/objects/hoststatus"
            )
            response = requests.get(
                url,
                params={"apikey": self.authentication_config.api_key, "pretty": "1"},
                verify=self.authentication_config.verify_ssl,
                timeout=10,
            )
            response.raise_for_status()
            scopes["api_access"] = True
        except requests.exceptions.HTTPError as e:
            scopes["api_access"] = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        except Exception as e:
            scopes["api_access"] = str(e)

        return scopes

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull current host and service alert status from the Nagios XI REST API.

        Returns an empty list when running in webhook-only mode (no ``nagios_url``
        / ``api_key`` configured).
        """
        if not self.authentication_config.nagios_url or not self.authentication_config.api_key:
            self.logger.debug(
                "nagios_url / api_key not configured — skipping pull-based alert retrieval"
            )
            return []

        alerts: list[AlertDto] = []
        base = self.authentication_config.nagios_url.rstrip("/")
        params = {"apikey": self.authentication_config.api_key, "pretty": "1"}

        # Host status
        try:
            resp = requests.get(
                f"{base}/api/v1/objects/hoststatus",
                params=params,
                verify=self.authentication_config.verify_ssl,
                timeout=30,
            )
            resp.raise_for_status()
            for host in resp.json().get("hoststatus", []):
                alert = self._host_status_to_alert_dto(host)
                if alert:
                    alerts.append(alert)
        except Exception:
            self.logger.exception("Failed to retrieve Nagios XI host status")

        # Service status
        try:
            resp = requests.get(
                f"{base}/api/v1/objects/servicestatus",
                params=params,
                verify=self.authentication_config.verify_ssl,
                timeout=30,
            )
            resp.raise_for_status()
            for svc in resp.json().get("servicestatus", []):
                alert = self._service_status_to_alert_dto(svc)
                if alert:
                    alerts.append(alert)
        except Exception:
            self.logger.exception("Failed to retrieve Nagios XI service status")

        return alerts

    # ------------------------------------------------------------------
    # Helpers for pull mode (Nagios XI API responses)
    # ------------------------------------------------------------------

    def _host_status_to_alert_dto(self, host: dict) -> AlertDto | None:
        """Convert a Nagios XI hoststatus API object to an AlertDto."""
        try:
            state_raw = (host.get("current_state") or "0")
            # Nagios XI encodes state as integer: 0=UP, 1=DOWN, 2=UNREACHABLE
            host_state_map = {"0": "up", "1": "down", "2": "unreachable"}
            state_str = host_state_map.get(str(state_raw), "unknown")

            hostname = host.get("name", "unknown")
            last_check = host.get("last_check") or datetime.datetime.now(
                tz=datetime.timezone.utc
            ).isoformat()

            return AlertDto(
                id=f"nagios-host-{hostname}",
                name=hostname,
                status=self.STATUS_MAP.get(state_str, AlertStatus.FIRING),
                severity=self.SEVERITIES_MAP.get(state_str, AlertSeverity.INFO),
                lastReceived=str(last_check),
                source=["nagios"],
                description=host.get("status_information", ""),
                hostname=hostname,
                hoststate=state_str.upper(),
                pushed=False,
            )
        except Exception:
            self.logger.exception("Failed to convert host status to AlertDto", extra={"host": host})
            return None

    def _service_status_to_alert_dto(self, svc: dict) -> AlertDto | None:
        """Convert a Nagios XI servicestatus API object to an AlertDto."""
        try:
            state_raw = (svc.get("current_state") or "0")
            # 0=OK, 1=WARNING, 2=CRITICAL, 3=UNKNOWN
            svc_state_map = {"0": "ok", "1": "warning", "2": "critical", "3": "unknown"}
            state_str = svc_state_map.get(str(state_raw), "unknown")

            hostname = svc.get("host_name", "unknown")
            servicedesc = svc.get("name", "unknown")
            last_check = svc.get("last_check") or datetime.datetime.now(
                tz=datetime.timezone.utc
            ).isoformat()

            return AlertDto(
                id=f"nagios-svc-{hostname}-{servicedesc}",
                name=f"{hostname}/{servicedesc}",
                status=self.STATUS_MAP.get(state_str, AlertStatus.FIRING),
                severity=self.SEVERITIES_MAP.get(state_str, AlertSeverity.INFO),
                lastReceived=str(last_check),
                source=["nagios"],
                description=svc.get("status_information", ""),
                hostname=hostname,
                servicedesc=servicedesc,
                servicestate=state_str.upper(),
                pushed=False,
            )
        except Exception:
            self.logger.exception(
                "Failed to convert service status to AlertDto", extra={"svc": svc}
            )
            return None

    # ------------------------------------------------------------------
    # Webhook ingestion
    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Convert an incoming Nagios webhook notification payload to an AlertDto.

        Nagios sends host and service notifications as separate payloads.  The
        distinguishing field is ``servicedesc`` — present for service checks,
        absent (or empty) for host checks.

        Expected payload keys (all optional; graceful fallbacks applied):
            notification_type  – PROBLEM, RECOVERY, ACKNOWLEDGEMENT, …
            hostname           – monitored host name
            hoststate          – UP, DOWN, UNREACHABLE  (host notifications)
            hostaddress        – host IP / FQDN
            hostoutput         – first line of host plugin output
            servicedesc        – service description (service notifications only)
            servicestate       – OK, WARNING, CRITICAL, UNKNOWN
            serviceoutput      – first line of service plugin output
            timestamp          – human-readable datetime from $LONGDATETIME$
        """
        notification_type = (event.get("notification_type") or "problem").lower()
        hostname = event.get("hostname", "unknown")
        host_address = event.get("hostaddress", "")
        servicedesc = event.get("servicedesc", "")
        timestamp_raw = event.get("timestamp") or datetime.datetime.now(
            tz=datetime.timezone.utc
        ).isoformat()

        is_service = bool(servicedesc)

        if is_service:
            state_raw = (event.get("servicestate") or "unknown").lower()
            output = event.get("serviceoutput", "")
            alert_name = f"{hostname}/{servicedesc}"
            alert_id = f"nagios-svc-{hostname}-{servicedesc}"
        else:
            state_raw = (event.get("hoststate") or "unknown").lower()
            output = event.get("hostoutput", "")
            alert_name = hostname
            alert_id = f"nagios-host-{hostname}"

        # Derive severity from state (recovery/ack overrides → low severity)
        severity = NagiosProvider.SEVERITIES_MAP.get(state_raw, AlertSeverity.INFO)

        # Derive status: notification_type takes priority over raw state
        status = NagiosProvider.STATUS_MAP.get(
            notification_type,
            NagiosProvider.STATUS_MAP.get(state_raw, AlertStatus.FIRING),
        )

        # Parse the Nagios long-date timestamp ($LONGDATETIME$ = "Mon Jan  1 00:00:00 UTC 2024")
        last_received = NagiosProvider._parse_nagios_timestamp(timestamp_raw)

        alert = AlertDto(
            id=alert_id,
            name=alert_name,
            status=status,
            severity=severity,
            lastReceived=last_received,
            source=["nagios"],
            message=output,
            description=output,
            hostname=hostname,
            hostaddress=host_address,
            servicedesc=servicedesc if is_service else None,
            servicestate=state_raw.upper() if is_service else None,
            hoststate=state_raw.upper() if not is_service else event.get("hoststate", ""),
            notification_type=notification_type.upper(),
            pushed=True,
        )

        alert.fingerprint = NagiosProvider.get_alert_fingerprint(
            alert, NagiosProvider.FINGERPRINT_FIELDS
        )
        return alert

    @staticmethod
    def _parse_nagios_timestamp(timestamp_raw: str) -> str:
        """
        Parse a Nagios ``$LONGDATETIME$`` string such as
        ``"Mon Jan  1 00:00:00 UTC 2024"`` into an ISO-8601 string.

        Falls back to the input string unchanged if it cannot be parsed so
        that downstream code always receives a non-None value.
        """
        if not timestamp_raw:
            return datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

        # Already ISO-8601 (from tests or XI API)
        if "T" in timestamp_raw or timestamp_raw.count("-") >= 2:
            return timestamp_raw

        # Nagios Core $LONGDATETIME$ format: "Mon Jan  1 00:00:00 UTC 2024"
        for fmt in (
            "%a %b %d %H:%M:%S %Z %Y",
            "%a %b  %d %H:%M:%S %Z %Y",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                dt = datetime.datetime.strptime(timestamp_raw.strip(), fmt)
                return dt.replace(tzinfo=datetime.timezone.utc).isoformat()
            except ValueError:
                continue

        # Cannot parse — return raw value so callers still get a string
        return timestamp_raw


if __name__ == "__main__":
    import logging
    import os

    from keep.contextmanager.contextmanager import ContextManager
    from keep.providers.models.provider_config import ProviderConfig
    from keep.providers.providers_factory import ProvidersFactory

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")

    provider_config = {
        "authentication": {
            "nagios_url": os.environ.get("NAGIOS_URL", ""),
            "api_key": os.environ.get("NAGIOS_API_KEY", ""),
        }
    }

    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="nagios",
        provider_type="nagios",
        provider_config=provider_config,
    )

    alerts = provider._get_alerts()
    for alert in alerts:
        print(alert)
