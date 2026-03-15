"""
SolarWinds Provider — pulls active alerts from SolarWinds Orion via SWIS REST API.
"""

import dataclasses
import datetime
import logging
import urllib.parse

import pydantic
import requests
import requests.auth

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SolarwindsProviderAuthConfig:
    """Authentication configuration for SolarWinds Orion (SWIS REST API)."""

    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion server hostname or IP address",
            "hint": "orion.example.com",
            "sensitive": False,
        }
    )
    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds administrator username",
            "sensitive": False,
        }
    )
    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds administrator password",
            "sensitive": True,
        }
    )
    port: int = dataclasses.field(
        default=17778,
        metadata={
            "required": False,
            "description": "SWIS REST API port (default: 17778)",
            "sensitive": False,
        },
    )
    verify_ssl: bool = dataclasses.field(
        default=False,
        metadata={
            "required": False,
            "description": (
                "Verify TLS/SSL certificates. "
                "Set to false when using self-signed certificates (common in Orion deployments)."
            ),
            "sensitive": False,
        },
    )


class SolarwindsProvider(BaseProvider):
    """Pull active alerts from SolarWinds Orion into Keep."""

    PROVIDER_DISPLAY_NAME = "SolarWinds"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["id"]

    # SolarWinds Orion severity levels
    # https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-alerting.htm
    SEVERITY_MAP = {
        1: AlertSeverity.CRITICAL,   # Critical
        2: AlertSeverity.HIGH,       # High
        3: AlertSeverity.WARNING,    # Medium / Warning
        4: AlertSeverity.LOW,        # Low / Informational
    }

    PROVIDER_SCOPES = [
        ProviderScope(
            name="query",
            description="Query SWIS REST API to retrieve active alerts and node status.",
            mandatory=True,
            documentation_url=(
                "https://github.com/solarwinds/OrionSDK/wiki/REST"
            ),
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SolarwindsProviderAuthConfig(
            **self.config.authentication
        )

    def _base_url(self) -> str:
        cfg = self.authentication_config
        return (
            f"https://{cfg.host}:{cfg.port}"
            "/SolarWinds/InformationService/v3/Json"
        )

    def _session(self) -> requests.Session:
        cfg = self.authentication_config
        s = requests.Session()
        s.auth = requests.auth.HTTPBasicAuth(cfg.username, cfg.password)
        s.verify = cfg.verify_ssl
        s.headers.update({"Content-Type": "application/json"})
        return s

    def _swql_query(self, session: requests.Session, swql: str) -> list[dict]:
        """Execute a SWQL query against the SWIS REST endpoint and return rows."""
        url = f"{self._base_url()}/Query"
        encoded = urllib.parse.urlencode({"query": swql})
        resp = session.get(f"{url}?{encoded}", timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])

    def validate_scopes(self) -> dict[str, bool | str]:
        """Verify connectivity to the SWIS API by running a trivial query."""
        try:
            session = self._session()
            rows = self._swql_query(session, "SELECT TOP 1 AlertID FROM Orion.AlertActive")
            return {"query": True}
        except requests.exceptions.ConnectionError as e:
            return {"query": f"Connection failed: {e}"}
        except requests.exceptions.HTTPError as e:
            return {"query": f"HTTP error {e.response.status_code}: {e}"}
        except Exception as e:
            return {"query": str(e)}

    def dispose(self):
        pass

    @staticmethod
    def _iso(dt_str: str | None) -> str:
        """Convert a SolarWinds datetime string to ISO-8601 UTC."""
        if not dt_str:
            return datetime.datetime.now(datetime.timezone.utc).isoformat()
        # Orion returns datetimes like "2024-01-15T10:30:00.000" (local server time, no TZ)
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                naive = datetime.datetime.strptime(dt_str, fmt)
                # Treat as UTC (common Orion deployment default; users should configure Orion TZ)
                return naive.replace(tzinfo=datetime.timezone.utc).isoformat()
            except ValueError:
                continue
        return dt_str  # Return raw string if parsing fails

    def _get_alerts(self) -> list[AlertDto]:
        """Query Orion.AlertActive for all currently firing alerts."""
        self.logger.info("Collecting active alerts from SolarWinds Orion")

        swql = (
            "SELECT AlertID, Name, Severity, Message, Acknowledged, "
            "TriggeredDateTime, AcknowledgedDateTime, "
            "RelatedNodeCaption, RelatedNodeID "
            "FROM Orion.AlertActive "
            "ORDER BY TriggeredDateTime DESC"
        )

        try:
            session = self._session()
            rows = self._swql_query(session, swql)
        except Exception as e:
            self.logger.error("Error fetching alerts from SolarWinds: %s", e)
            raise

        alerts: list[AlertDto] = []
        for row in rows:
            severity_raw = row.get("Severity", 4)
            try:
                severity = self.SEVERITY_MAP.get(int(severity_raw), AlertSeverity.INFO)
            except (TypeError, ValueError):
                severity = AlertSeverity.INFO

            acknowledged = row.get("Acknowledged", False)
            if acknowledged:
                status = AlertStatus.ACKNOWLEDGED
            else:
                status = AlertStatus.FIRING

            node_name = row.get("RelatedNodeCaption") or ""
            alert_name = row.get("Name") or f"Alert {row.get('AlertID', '')}"
            if node_name:
                name = f"{alert_name} — {node_name}"
            else:
                name = alert_name

            alert = AlertDto(
                id=str(row.get("AlertID", "")),
                name=name,
                severity=severity,
                status=status,
                description=row.get("Message", ""),
                lastReceived=self._iso(row.get("TriggeredDateTime")),
                source=["solarwinds"],
            )
            alerts.append(alert)

        self.logger.info("Collected %d alert(s) from SolarWinds", len(alerts))
        return alerts


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    config = ProviderConfig(
        description="SolarWinds Provider",
        authentication={
            "host": os.environ.get("SOLARWINDS_HOST", "localhost"),
            "username": os.environ.get("SOLARWINDS_USERNAME", "admin"),
            "password": os.environ.get("SOLARWINDS_PASSWORD", ""),
            "port": int(os.environ.get("SOLARWINDS_PORT", "17778")),
            "verify_ssl": os.environ.get("SOLARWINDS_VERIFY_SSL", "false").lower() == "true",
        },
    )

    provider = SolarwindsProvider(
        context_manager=context_manager,
        provider_id="solarwinds-test",
        config=config,
    )
    alerts = provider._get_alerts()
    for a in alerts:
        print(a)
