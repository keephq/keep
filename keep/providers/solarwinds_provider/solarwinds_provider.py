"""
Solarwinds Provider is a class that allows to ingest alerts from SolarWinds Orion Platform.

Supports both pull-based alert fetching via the SWIS REST API (SWQL) and
push-based alert ingestion via webhooks.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import pydantic
import requests
from requests.auth import HTTPBasicAuth

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class SolarwindsProviderAuthConfig:
    """
    Solarwinds Orion authentication configuration.

    Supports authentication via:
    - Username + Password (HTTP Basic Auth to SWIS API)
    - API Token (Bearer token auth)
    """

    host_url: pydantic.AnyHttpUrl = pydantic.Field(
        metadata={
            "required": True,
            "description": "SolarWinds Orion SWIS API base URL",
            "hint": "e.g. https://solarwinds.example.com:17778/SolarWinds/InformationService/v3/Json",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    username: Optional[str] = pydantic.Field(
        default=None,
        metadata={
            "description": "SolarWinds Orion username (for basic auth)",
            "hint": "Leave empty if using API token",
            "sensitive": False,
        },
    )
    password: Optional[str] = pydantic.Field(
        default=None,
        metadata={
            "description": "SolarWinds Orion password (for basic auth)",
            "hint": "Leave empty if using API token",
            "sensitive": True,
        },
    )
    api_token: Optional[str] = pydantic.Field(
        default=None,
        metadata={
            "description": "SolarWinds Orion API token (if token-based auth is used)",
            "hint": "Alternative to username/password",
            "sensitive": True,
        },
    )
    verify_ssl: bool = pydantic.Field(
        default=True,
        metadata={
            "description": "Verify SSL certificates",
            "hint": "Set to false for self-signed certificates",
            "sensitive": False,
        },
    )


class SolarwindsProvider(BaseProvider):
    """
    Pull/Push alerts from SolarWinds Orion Platform into Keep.

    SolarWinds Orion uses the SolarWinds Information Service (SWIS) API
    which accepts SWQL (SolarWinds Query Language) queries to fetch alerts,
    nodes, and other monitored objects.

    SWIS API docs: https://documentation.solarwinds.com/en/success_center/orionplatform/content/api-swis.htm
    """

    PROVIDER_DISPLAY_NAME = "Solarwinds"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]
    FINGERPRINT_FIELDS = ["id"]

    WEBHOOK_INSTALLATION_REQUIRED = False

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read active alerts from SolarWinds Orion",
            mandatory=True,
            documentation_url="https://documentation.solarwinds.com/en/success_center/orionplatform/content/api-swis.htm",
        ),
    ]

    # SolarWinds alert severity/object severity mapping to Keep
    # SolarWinds uses: 0=Unknown, 1=Information, 2=Warning, 3=Minor, 4=Major, 5=Critical, 14=Notice
    SWIS_SEVERITY_MAP = {
        0: AlertSeverity.LOW,
        1: AlertSeverity.INFO,
        2: AlertSeverity.WARNING,
        3: AlertSeverity.WARNING,
        4: AlertSeverity.HIGH,
        5: AlertSeverity.CRITICAL,
        14: AlertSeverity.INFO,
    }

    # Node status mapping
    # SolarWinds node status: 0=Unknown, 1=Up, 2=Down, 3=Warning, 4=Critical, 5=Shutdown, 9=Unmanaged, 10=Unplugged
    NODE_STATUS_MAP = {
        0: AlertStatus.FIRING,
        1: AlertStatus.RESOLVED,
        2: AlertStatus.FIRING,
        3: AlertStatus.FIRING,
        4: AlertStatus.FIRING,
        5: AlertStatus.RESOLVED,
        9: AlertStatus.RESOLVED,
        10: AlertStatus.FIRING,
    }

    # Webhook status string mapping
    WEBHOOK_STATUS_MAP = {
        "up": AlertStatus.RESOLVED,
        "down": AlertStatus.FIRING,
        "warning": AlertStatus.FIRING,
        "critical": AlertStatus.FIRING,
        "shutdown": AlertStatus.RESOLVED,
        "unmanaged": AlertStatus.RESOLVED,
        "unplugged": AlertStatus.FIRING,
        "unknown": AlertStatus.FIRING,
    }

    WEBHOOK_SEVERITY_MAP = {
        "up": AlertSeverity.INFO,
        "down": AlertSeverity.CRITICAL,
        "warning": AlertSeverity.WARNING,
        "critical": AlertSeverity.CRITICAL,
        "shutdown": AlertSeverity.INFO,
        "unmanaged": AlertSeverity.INFO,
        "unplugged": AlertSeverity.WARNING,
        "unknown": AlertSeverity.LOW,
    }

    webhook_description = "SolarWinds Orion webhook for alert notifications"
    webhook_template = ""
    webhook_markdown = """
To send alerts from SolarWinds Orion to Keep:

1. In SolarWinds Orion Web Console, go to **Settings > All Settings > Alerting, Reports, and Events > Alert Actions**.
2. Click **Add New Alert Action** and select **Execute an External Program** or **Send a Webhook** (if available in your version).
3. Configure the alert action:
   - **Webhook URL**: `{keep_webhook_api_url}`
   - **HTTP Method**: POST
   - **Headers**: Add `X-API-KEY: {api_key}`
4. Configure the alert trigger body to include at minimum:
   - `NodeName` - the node that triggered the alert
   - `AlertName` - the alert definition name
   - `Severity` - alert severity level
   - `Message` - alert description
   - `Status` - current status (Up, Down, Warning, Critical)
5. Assign the alert action to the desired alerts or alert rules.
6. Test the alert action to verify Keep receives the alerts.

**Alternative: Using SolarWinds Alerting with REST API:**

If your SolarWinds version supports REST-based alert actions, configure:
- URL: `{keep_webhook_api_url}`
- Method: POST
- Content-Type: application/json
- Header: `X-API-KEY: {api_key}`
- Body template: See SolarWinds documentation for variable substitution.
    """

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """Dispose the provider."""
        pass

    def validate_config(self):
        """
        Validates required configuration for Solarwinds provider.

        Requires either (username + password) or api_token.
        """
        self.authentication_config = SolarwindsProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.api_token and not (
            self.authentication_config.username
            and self.authentication_config.password
        ):
            raise ValueError(
                "SolarWinds provider requires either api_token or (username + password)"
            )

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate that the credentials can access the SWIS API."""
        validated_scopes = {}
        try:
            # Try a simple query to verify access
            response = self.__query_swis("SELECT TOP 1 AlertObjectID FROM Orion.AlertActive")
            if response is not None:
                validated_scopes["read_alerts"] = True
            else:
                validated_scopes["read_alerts"] = "No response from SWIS API"
        except Exception as e:
            validated_scopes["read_alerts"] = str(e)
        return validated_scopes

    def __get_auth(self) -> tuple[requests.auth.AuthBase, dict[str, str]]:
        """Return authentication tuple and extra headers based on config."""
        headers = {"Content-Type": "application/json"}
        if self.authentication_config.api_token:
            headers["Authorization"] = f"Bearer {self.authentication_config.api_token}"
            return None, headers
        else:
            auth = HTTPBasicAuth(
                self.authentication_config.username,
                self.authentication_config.password,
            )
            return auth, headers

    def __query_swis(self, swql: str, params: dict = None) -> list[dict]:
        """
        Execute a SWQL query against the SolarWinds Information Service API.

        Args:
            swql: The SWQL query string.
            params: Optional parameters for parameterized queries.

        Returns:
            List of result dictionaries.
        """
        url = f"{self.authentication_config.host_url.rstrip('/')}/Query"
        auth, headers = self.__get_auth()
        payload = {"query": swql}
        if params:
            payload["parameters"] = params

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            auth=auth,
            verify=self.authentication_config.verify_ssl,
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        return result.get("results", [])

    def _get_alerts(self) -> list[AlertDto]:
        """
        Fetch active alerts from SolarWinds Orion via SWIS API.

        Queries the Orion.AlertActive view for currently active alerts
        and maps them to Keep AlertDto objects.
        """
        swql = """
            SELECT
                a.AlertObjectID,
                a.AlertDefID,
                a.ObjectName,
                a.EntityCaption,
                a.EntityNetObjectID,
                a.AlertMessage,
                a.Severity,
                a.TriggeredDateTime,
                a.LastTriggeredDateTime,
                a.Acknowledged,
                a.LastNote,
                ad.Name AS AlertDefName,
                n.Caption AS NodeCaption,
                n.IP_Address AS NodeIP,
                n.Status AS NodeStatus,
                n.CustomProperties.NodeGroup AS NodeGroup
            FROM Orion.AlertActive a
            LEFT JOIN Orion.AlertDefinition ad ON a.AlertDefID = ad.AlertDefID
            LEFT JOIN Orion.Nodes n ON a.RelatedNodeID = n.NodeID
            ORDER BY a.TriggeredDateTime DESC
        """

        try:
            rows = self.__query_swis(swql)
        except requests.exceptions.ConnectionError:
            self.logger.error(
                "Failed to connect to SolarWinds SWIS API",
                extra={
                    "host": self.authentication_config.host_url,
                    "tenant_id": self.context_manager.tenant_id,
                },
            )
            raise
        except requests.exceptions.HTTPError as e:
            self.logger.error(
                "SWIS API returned HTTP error",
                extra={
                    "error": str(e),
                    "tenant_id": self.context_manager.tenant_id,
                },
            )
            raise

        alerts = []
        for row in rows:
            alert_id = str(row.get("AlertObjectID", ""))
            if not alert_id:
                continue

            severity = self.SWIS_SEVERITY_MAP.get(
                row.get("Severity", 0), AlertSeverity.INFO
            )

            # Determine status from acknowledged state
            if row.get("Acknowledged"):
                status = AlertStatus.ACKNOWLEDGED
            else:
                node_status = row.get("NodeStatus", 0)
                status = self.NODE_STATUS_MAP.get(node_status, AlertStatus.FIRING)

            # Parse timestamps
            triggered_at = row.get("TriggeredDateTime") or row.get(
                "LastTriggeredDateTime"
            )
            last_received = triggered_at
            if triggered_at:
                try:
                    # SolarWinds returns timestamps in various formats
                    if isinstance(triggered_at, str):
                        dt = datetime.fromisoformat(triggered_at.replace("Z", "+00:00"))
                        last_received = dt.isoformat()
                    elif isinstance(triggered_at, (int, float)):
                        # Sometimes returns as Unix timestamp in milliseconds
                        ts = triggered_at / 1000 if triggered_at > 1e12 else triggered_at
                        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                        last_received = dt.isoformat()
                except (ValueError, OSError) as e:
                    self.logger.warning(
                        f"Failed to parse SolarWinds timestamp: {triggered_at}",
                        extra={"error": str(e)},
                    )
                    last_received = datetime.now(tz=timezone.utc).isoformat()
            else:
                last_received = datetime.now(tz=timezone.utc).isoformat()

            # Build alert name
            alert_def_name = row.get("AlertDefName", "")
            entity_caption = row.get("EntityCaption", "")
            node_caption = row.get("NodeCaption", "")
            name = alert_def_name or entity_caption or node_caption or "SolarWinds Alert"

            alert_dto = AlertDto(
                id=alert_id,
                name=name,
                status=status,
                severity=severity,
                lastReceived=last_received,
                description=row.get("AlertMessage", ""),
                source=["solarwinds"],
                hostname=node_caption,
                ip_address=row.get("NodeIP"),
                service=entity_caption,
                message=row.get("AlertMessage", ""),
                labels={
                    "alert_definition": alert_def_name,
                    "node_group": row.get("NodeGroup", ""),
                    "object_name": row.get("ObjectName", ""),
                    "net_object_id": row.get("EntityNetObjectID", ""),
                },
                annotations={
                    "last_note": row.get("LastNote", ""),
                    "last_triggered": row.get("LastTriggeredDateTime", ""),
                },
            )
            alerts.append(alert_dto)

        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format incoming SolarWinds webhook payload into a Keep AlertDto.

        Supports common webhook payloads from SolarWinds alert actions.
        Field names are matched case-insensitively for flexibility.

        Expected payload fields (at minimum):
            - NodeName / node / node_name: The node that triggered the alert
            - AlertName / alert_name / alert: The alert definition name
            - Severity / severity: Alert severity (Critical, Warning, Down, Up, etc.)
            - Message / message / description: Alert description
            - Status / status: Node/alert status

        Optional fields:
            - timestamp / DateTime: When the alert was triggered
            - ip_address / IPAddress: Node IP address
            - url / URL: Link to the alert in SolarWinds
        """
        def _get(keys: list[str], default=None):
            """Get a value from the event trying multiple possible key names."""
            for key in keys:
                # Try exact match first
                if key in event:
                    return event[key]
                # Try case-insensitive match
                lower_event = {k.lower(): v for k, v in event.items()}
                if key.lower() in lower_event:
                    return lower_event[key.lower()]
            return default

        node_name = _get(["NodeName", "node", "node_name", "Node", "hostname"], "")
        alert_name = _get(["AlertName", "alert_name", "alert", "AlertDefName", "Name"], "")
        message = _get(["Message", "message", "description", "AlertMessage", "Details"], "")
        status_raw = _get(["Status", "status", "NodeStatus", "state"], "unknown")
        severity_raw = _get(["Severity", "severity", "alert_severity"], "")
        timestamp = _get(["timestamp", "DateTime", "TriggeredDateTime", "lastReceived"])
        ip_address = _get(["ip_address", "IPAddress", "IP_Address", "NodeIP"])
        url = _get(["url", "URL", "AlertURL", "DetailsUrl"])
        entity = _get(["EntityCaption", "entity", "object_name", "ComponentName"])

        # Normalize status and severity strings
        status_normalized = str(status_raw).strip().lower()
        severity_normalized = str(severity_raw).strip().lower()

        # Determine status
        if status_normalized in SolarwindsProvider.WEBHOOK_STATUS_MAP:
            status = SolarwindsProvider.WEBHOOK_STATUS_MAP[status_normalized]
        else:
            # Try severity as status fallback (e.g., "Down" as both status and severity)
            if severity_normalized in SolarwindsProvider.WEBHOOK_STATUS_MAP:
                status = SolarwindsProvider.WEBHOOK_STATUS_MAP[severity_normalized]
            else:
                status = AlertStatus.FIRING

        # Determine severity
        if severity_normalized in SolarwindsProvider.WEBHOOK_SEVERITY_MAP:
            severity = SolarwindsProvider.WEBHOOK_SEVERITY_MAP[severity_normalized]
        elif status_normalized in SolarwindsProvider.WEBHOOK_SEVERITY_MAP:
            severity = SolarwindsProvider.WEBHOOK_SEVERITY_MAP[status_normalized]
        else:
            severity = AlertSeverity.INFO

        # Parse timestamp
        last_received = None
        if timestamp:
            try:
                if isinstance(timestamp, str):
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    last_received = dt.isoformat()
                elif isinstance(timestamp, (int, float)):
                    ts = timestamp / 1000 if timestamp > 1e12 else timestamp
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                    last_received = dt.isoformat()
            except (ValueError, OSError):
                last_received = None

        if not last_received:
            last_received = datetime.now(tz=timezone.utc).isoformat()

        # Build alert name
        name = alert_name or node_name or "SolarWinds Alert"

        # Build fingerprint-compatible id
        alert_id = event.get("id") or event.get("AlertObjectID") or event.get("alert_id")
        if alert_id:
            alert_id = str(alert_id)
        else:
            # Generate a stable id from node + alert name
            alert_id = f"solarwinds:{node_name}:{alert_name}"

        return AlertDto(
            id=alert_id,
            name=name,
            status=status,
            severity=severity,
            lastReceived=last_received,
            description=message or "",
            source=["solarwinds"],
            hostname=node_name,
            ip_address=ip_address,
            service=entity,
            message=message or "",
            url=url,
            pushed=True,
        )


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    import os

    provider_config = {
        "authentication": {
            "host_url": os.environ.get("SOLARWINDS_HOST_URL", "https://localhost:17778/SolarWinds/InformationService/v3/Json"),
            "username": os.environ.get("SOLARWINDS_USERNAME", "admin"),
            "password": os.environ.get("SOLARWINDS_PASSWORD", ""),
        },
    }
    provider = SolarwindsProvider(
        context_manager,
        provider_id="solarwinds",
        config=ProviderConfig(**provider_config),
    )
    alerts = provider.get_alerts()
    for alert in alerts:
        print(alert)
