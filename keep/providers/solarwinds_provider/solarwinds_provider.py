"""
SolarWinds provider for Keep.
Integrates with the SolarWinds Information Service (SWIS) REST API
to pull active alerts from SolarWinds Orion / NPM.
"""

import dataclasses
import datetime
import logging

import pydantic
import requests
from requests.auth import HTTPBasicAuth

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SolarwindsProviderAuthConfig:
    """
    Authentication configuration for SolarWinds SWIS API.

    SolarWinds uses Basic Auth against the SWIS (SolarWinds Information Service)
    REST endpoint, typically on port 17778.
    """

    hostname: str = dataclasses.field(
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
            "description": "SolarWinds admin username",
            "hint": "admin",
            "sensitive": False,
        }
    )
    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SolarWinds admin password",
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
            "description": "Verify SSL certificates (disable for self-signed certs)",
            "sensitive": False,
        },
    )


class SolarwindsProvider(BaseProvider):
    """
    Pull active alerts from SolarWinds Orion via the SWIS REST API.

    SolarWinds Information Service (SWIS) exposes a SWQL query interface
    that this provider uses to retrieve current alerts and node status.
    """

    PROVIDER_DISPLAY_NAME = "SolarWinds"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["id"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="Successfully authenticated against SWIS API",
            mandatory=True,
            documentation_url="https://github.com/solarwinds/OrionSDK/wiki/REST",
        ),
    ]

    SEVERITY_MAP = {
        1: AlertSeverity.INFO,       # Information
        2: AlertSeverity.WARNING,    # Warning
        3: AlertSeverity.CRITICAL,   # Critical
        4: AlertSeverity.CRITICAL,   # Emergency
    }

    STATUS_MAP = {
        True: AlertStatus.FIRING,
        False: AlertStatus.RESOLVED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """Validate and parse authentication configuration."""
        self.authentication_config = SolarwindsProviderAuthConfig(
            **self.config.authentication
        )

    def _get_swis_base_url(self) -> str:
        cfg = self.authentication_config
        return (
            f"https://{cfg.hostname}:{cfg.port}"
            "/SolarWinds/InformationService/v3/Json"
        )

    def _swis_query(self, swql: str) -> list[dict]:
        """Execute a SWQL query against the SWIS REST API."""
        url = f"{self._get_swis_base_url()}/Query"
        auth = HTTPBasicAuth(
            self.authentication_config.username,
            self.authentication_config.password,
        )
        try:
            response = requests.get(
                url,
                params={"query": swql},
                auth=auth,
                verify=self.authentication_config.verify_ssl,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except requests.exceptions.ConnectionError as e:
            raise ProviderException(
                f"Cannot connect to SolarWinds at {self.authentication_config.hostname}:{self.authentication_config.port}: {e}"
            ) from e
        except requests.exceptions.HTTPError as e:
            raise ProviderException(
                f"SolarWinds SWIS API error (HTTP {response.status_code}): {response.text}"
            ) from e
        except Exception as e:
            raise ProviderException(f"Unexpected error querying SolarWinds: {e}") from e

    def validate_scopes(self) -> dict[str, bool | str]:
        """Verify we can authenticate and query the SWIS API."""
        try:
            # Simple query to verify connectivity and auth
            self._swis_query("SELECT TOP 1 NodeID FROM Orion.Nodes")
            return {"authenticated": True}
        except ProviderException as e:
            return {"authenticated": str(e)}
        except Exception as e:
            return {"authenticated": f"Unexpected error: {e}"}

    def _get_active_alerts(self) -> list[AlertDto]:
        """Fetch active alerts from Orion.AlertActive."""
        swql = (
            "SELECT AlertActiveID, AlertObjectID, TriggeredDateTime, "
            "Acknowledged, AcknowledgedDateTime, AcknowledgedBy, "
            "AlertID, Name, Message, Severity, ObjectType, RelatedNodeCaption "
            "FROM Orion.AlertActive"
        )
        try:
            rows = self._swis_query(swql)
        except Exception as e:
            self.logger.error("Failed to fetch active alerts: %s", e)
            return []

        alerts = []
        for row in rows:
            alert_id = str(row.get("AlertActiveID", ""))
            name = row.get("Name") or row.get("AlertID", "Unknown Alert")
            message = row.get("Message", "")
            severity_raw = row.get("Severity", 1)
            severity = self.SEVERITY_MAP.get(int(severity_raw), AlertSeverity.INFO)

            # Parse timestamp
            triggered_raw = row.get("TriggeredDateTime")
            if triggered_raw:
                try:
                    last_received = datetime.datetime.fromisoformat(
                        triggered_raw.replace("Z", "+00:00")
                    ).isoformat()
                except (ValueError, AttributeError):
                    last_received = triggered_raw
            else:
                last_received = datetime.datetime.utcnow().isoformat()

            acknowledged = bool(row.get("Acknowledged", False))
            if acknowledged:
                status = AlertStatus.ACKNOWLEDGED
            else:
                status = AlertStatus.FIRING

            alerts.append(
                AlertDto(
                    id=alert_id,
                    name=name,
                    description=message,
                    severity=severity,
                    status=status,
                    source=["solarwinds"],
                    lastReceived=last_received,
                    host=row.get("RelatedNodeCaption"),
                    object_type=row.get("ObjectType"),
                    acknowledged=acknowledged,
                    acknowledged_by=row.get("AcknowledgedBy"),
                )
            )

        self.logger.info(
            "Fetched %d active alerts from SolarWinds", len(alerts)
        )
        return alerts

    def _get_node_alerts(self) -> list[AlertDto]:
        """Fetch down/warning nodes from Orion.Nodes as additional alerts."""
        swql = (
            "SELECT NodeID, Caption, IPAddress, Status, StatusDescription, "
            "LastBoot, MachineType, Vendor "
            "FROM Orion.Nodes "
            "WHERE Status != 1"  # 1 = Up
        )
        try:
            rows = self._swis_query(swql)
        except Exception as e:
            self.logger.error("Failed to fetch node status: %s", e)
            return []

        # SolarWinds node status codes: 1=Up, 2=Down, 3=Warning, 14=Shutdown, ...
        NODE_SEVERITY_MAP = {
            2: AlertSeverity.CRITICAL,   # Down
            3: AlertSeverity.WARNING,    # Warning
            14: AlertSeverity.INFO,      # Shutdown
        }
        NODE_STATUS_MAP = {
            2: AlertStatus.FIRING,
            3: AlertStatus.FIRING,
            14: AlertStatus.RESOLVED,
        }

        alerts = []
        for row in rows:
            node_id = str(row.get("NodeID", ""))
            caption = row.get("Caption", "Unknown Node")
            status_code = int(row.get("Status", 2))
            severity = NODE_SEVERITY_MAP.get(status_code, AlertSeverity.WARNING)
            status = NODE_STATUS_MAP.get(status_code, AlertStatus.FIRING)
            description = row.get("StatusDescription") or f"Node status: {status_code}"

            alerts.append(
                AlertDto(
                    id=f"node-{node_id}",
                    name=f"Node {caption} is {description}",
                    description=description,
                    severity=severity,
                    status=status,
                    source=["solarwinds"],
                    lastReceived=datetime.datetime.utcnow().isoformat(),
                    host=caption,
                    ip_address=row.get("IPAddress"),
                    machine_type=row.get("MachineType"),
                    vendor=row.get("Vendor"),
                )
            )

        self.logger.info(
            "Fetched %d node alerts from SolarWinds", len(alerts)
        )
        return alerts

    def _get_alerts(self) -> list[AlertDto]:
        """Pull all active alerts and down nodes from SolarWinds."""
        alerts = []

        try:
            self.logger.info("Fetching active alerts from SolarWinds")
            active_alerts = self._get_active_alerts()
            alerts.extend(active_alerts)
        except Exception as e:
            self.logger.error("Error fetching active alerts: %s", e)

        try:
            self.logger.info("Fetching node status alerts from SolarWinds")
            node_alerts = self._get_node_alerts()
            alerts.extend(node_alerts)
        except Exception as e:
            self.logger.error("Error fetching node alerts: %s", e)

        return alerts


if __name__ == "__main__":
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    config = ProviderConfig(
        description="SolarWinds provider test",
        authentication={
            "hostname": os.environ.get("SOLARWINDS_HOST", "localhost"),
            "username": os.environ.get("SOLARWINDS_USER", "admin"),
            "password": os.environ.get("SOLARWINDS_PASSWORD", ""),
            "port": int(os.environ.get("SOLARWINDS_PORT", "17778")),
            "verify_ssl": False,
        },
    )

    provider = SolarwindsProvider(
        context_manager,
        provider_id="solarwinds-test",
        config=config,
    )

    provider.validate_config()
    print("Scopes:", provider.validate_scopes())
    alerts = provider._get_alerts()
    print(f"Alerts: {len(alerts)}")
    for alert in alerts[:5]:
        print(f"  {alert}")
